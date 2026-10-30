"""Ciclo de monitoramento: coleta, pontua, guarda e alerta."""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

from . import scoring, sources, telegram
from .config import telegram_configurado
from .store import Store
from .texto import parecido, tokens

class Monitor:
    def __init__(self, cfg: dict, store: Store, log):
        self.cfg = cfg
        self.store = store
        self.log = log
        self._lock = threading.RLock()
        self._parar = threading.Event()
        self._thread: threading.Thread | None = None

        self.status = {
            "ativo": False,
            "iniciado_em": None,
            "ultimo_ciclo": None,
            "proximo_ciclo": None,
            "ultimo_resultado": None,
            "fontes": [],
            "telegram": telegram_configurado(cfg),
            "erro": None,
        }

    # -- status ------------------------------------------------------------
    def snapshot(self) -> dict:
        with self._lock:
            st = dict(self.status)
            st["fontes"] = [dict(f) for f in self.status["fontes"]]
        st["totais"] = self.store.estatisticas()
        return st

    # -- coleta ------------------------------------------------------------
    def _coletar(self) -> tuple[list[dict], list[dict]]:
        timeout = self.cfg["coleta"]["timeout_segundos"]
        fontes = sources.todas_as_fontes(self.cfg, timeout)
        itens: list[dict] = []
        relatorio: list[dict] = []

        with ThreadPoolExecutor(max_workers=min(8, len(fontes))) as pool:
            futuros = {pool.submit(fn): nome for nome, fn in fontes}
            for futuro in as_completed(futuros):
                nome = futuros[futuro]
                try:
                    coletados = futuro.result()
                    itens.extend(coletados)
                    relatorio.append({
                        "nome": nome, "ok": True, "itens": len(coletados),
                        "erro": None, "visto_em": _agora_iso(),
                    })
                except Exception as e:
                    relatorio.append({
                        "nome": nome, "ok": False, "itens": 0,
                        "erro": f"{type(e).__name__}: {e}", "visto_em": _agora_iso(),
                    })
                    self.log.warning("Falha na fonte %s: %s", nome, e)

        relatorio.sort(key=lambda r: r["nome"])
        return itens, relatorio

    # -- ciclo -------------------------------------------------------------
    def ciclo(self, dry_run: bool = False) -> dict:
        inicio = _agora()
        self.log.info("Ciclo iniciado%s", " (dry-run)" if dry_run else "")

        brutos, relatorio_fontes = self._coletar()
        cfg_p = self.cfg["pontuacao"]
        limite_idade = timedelta(days=self.cfg["coleta"].get("idade_maxima_dias", 14))
        novas: list[dict] = []
        ignoradas = 0

        vistos: set[str] = set()
        for bruto in brutos:
            if bruto["chave"] in vistos:
                continue
            vistos.add(bruto["chave"])

            publicado = bruto.get("publicado")
            if publicado and (inicio - publicado) > limite_idade:
                ignoradas += 1
                continue

            avaliacao = scoring.avaliar(bruto["titulo"], bruto["resumo"], bruto["fonte"])
            if not avaliacao or avaliacao["score"] < cfg_p["minimo_painel"]:
                ignoradas += 1
                continue

            item = dict(bruto)
            item.update(avaliacao)
            item_id, criado = self.store.inserir(item)
            item["id"] = item_id
            if criado:
                novas.append(item)

        # Na primeira execução o banco pode vir cheio de notícias antigas.
        primeiro_ciclo = self.store.meta_get("primeiro_ciclo") is None
        enviados = self._alertar(novas, primeiro_ciclo, dry_run)

        self.store.meta_set("primeiro_ciclo", "1")

        resultado = {
            "inicio": inicio,
            "duracao_s": round((_agora() - inicio).total_seconds(), 1),
            "coletados": len(brutos),
            "relevantes_novos": len(novas),
            "ignorados": ignoradas,
            "alertas": enviados,
            "dry_run": dry_run,
            "fontes": relatorio_fontes,
        }

        with self._lock:
            self.status["ultimo_ciclo"] = _agora_iso()
            self.status["ultimo_resultado"] = resultado
            self.status["fontes"] = relatorio_fontes
            self.status["erro"] = None
            self.status["proximo_ciclo"] = (
                _agora() + timedelta(seconds=self.cfg["coleta"]["intervalo_segundos"])
            ).isoformat()

        self.log.info(
            "Ciclo: %s coletadas, %s novas relevantes, %s alertas, %.1fs",
            len(brutos), len(novas), enviados, resultado["duracao_s"],
        )
        return resultado

    # -- alertas -----------------------------------------------------------
    def _alertar(self, novas: list[dict], primeiro_ciclo: bool, dry_run: bool) -> int:
        cfg_a = self.cfg["alertas"]
        cfg_p = self.cfg["pontuacao"]
        agora = _agora()

        candidatas = []
        for item in novas:
            if not item.get("priority"):
                continue
            if item["score"] < cfg_p["minimo_alerta"]:
                continue
            publicado = item.get("publicado")
            if publicado and (agora - publicado) > timedelta(hours=cfg_a["idade_maxima_horas"]):
                continue
            candidatas.append(item)

        candidatas.sort(
            key=lambda i: (i["score"], i.get("publicado") or agora), reverse=True
        )

        if primeiro_ciclo:
            return self._boas_vindas(candidatas, dry_run)

        # Suppressão de cluster: não repetir o mesmo fato por vários veículos.
        ja_alertados = [tokens(t) for t in self.store.titulos_alertados_recentes(
            cfg_a["janela_cluster_horas"]
        )]
        escolhidas: list[dict] = []
        for item in candidatas:
            toks = tokens(item["titulo"])
            if any(parecido(toks, antigo, cfg_a["similaridade_cluster"]) for antigo in ja_alertados):
                self.log.info("Suprimida (mesmo fato): %s", item["titulo"])
                continue
            escolhidas.append(item)
            ja_alertados.append(toks)
            if len(escolhidas) >= cfg_a["max_por_ciclo"]:
                break

        if not escolhidas:
            return 0

        if dry_run or not telegram_configurado(self.cfg):
            for item in escolhidas:
                self.log.info("[dry-run] alertaria: %s", item["titulo"])
            if not dry_run:
                self.log.warning("Telegram não configurado; alerta não enviado.")
            return 0

        tg = self.cfg["telegram"]
        enviados = 0
        enviados_itens: list[dict] = []
        for item in escolhidas:
            ok, resp = telegram.enviar(
                tg["bot_token"], tg["chat_id"], telegram.formatar(item)
            )
            if ok:
                enviados += 1
                enviados_itens.append(item)
            else:
                self.log.error("Falha ao enviar no Telegram: %s", resp.get("erro"))
                break
        self.store.marcar_alertado([i["id"] for i in enviados_itens if i.get("id")])
        return enviados

    def _boas_vindas(self, candidatas: list[dict], dry_run: bool) -> int:
        """Primeira execução: manda um resumo em vez de despejar o histórico."""
        # Marca todo mundo como já visto para não haver enxurrada depois.
        recentes = [
            i for i in self.store.recentes(100)
            if i["priority"] and i["score"] >= self.cfg["pontuacao"]["minimo_alerta"]
        ]
        ids = [i["id"] for i in recentes]
        self.store.marcar_alertado(ids)

        if not self.cfg["alertas"]["enviar_primeira_vez"]:
            return 0
        if dry_run or not telegram_configurado(self.cfg):
            self.log.info("[dry-run] enviaria mensagem de boas-vindas (%s itens)", len(recentes))
            return 0

        top = sorted(
            recentes, key=lambda i: (i["score"], i["publicado"] or ""), reverse=True
        )[:3]
        tg = self.cfg["telegram"]
        ok, resp = telegram.enviar(
            tg["bot_token"], tg["chat_id"],
            telegram.formatar_boas_vindas(
                top, len(recentes), self.cfg["coleta"]["intervalo_segundos"] // 60
            ),
        )
        if ok:
            return 1
        self.log.error("Falha ao enviar boas-vindas: %s", resp.get("erro"))
        return 0

    # -- loop --------------------------------------------------------------
    def iniciar_thread(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, name="monitor", daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        with self._lock:
            self.status["ativo"] = True
            self.status["iniciado_em"] = _agora_iso()
        while not self._parar.is_set():
            try:
                self.ciclo()
            except Exception as e:
                self.log.exception("Erro no ciclo: %s", e)
                with self._lock:
                    self.status["erro"] = f"{type(e).__name__}: {e}"
            self._parar.wait(self.cfg["coleta"]["intervalo_segundos"])
        with self._lock:
            self.status["ativo"] = False

    def parar(self) -> None:
        self._parar.set()


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _agora_iso() -> str:
    return _agora().replace(microsecond=0).isoformat()
