#!/usr/bin/env python3
"""Alerta Água RJ — avisa no Telegram quando sai notícia que afeta o
abastecimento no Rio de Janeiro, com prioridade para Santa Cruz e Zona Oeste.

Uso:
    python app.py                 # monitor + painel em http://127.0.0.1:8765
    python app.py --once          # roda um ciclo e mostra o relatório
    python app.py --once --dry-run  # igual, mas não envia nada no Telegram
    python app.py --testar-telegram # envia uma mensagem de teste
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

# Console do Windows costuma vir em cp1252; força UTF-8 para os acentos.
for _fluxo in (sys.stdout, sys.stderr):
    if _fluxo and hasattr(_fluxo, "reconfigure"):
        try:
            _fluxo.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

from agua import config as cfgmod  # noqa: E402
from agua import dedupe, exportar, telegram  # noqa: E402
from agua.monitor import Monitor  # noqa: E402
from agua.store import Store  # noqa: E402
from agua.web import ServidorWeb  # noqa: E402

LOG = logging.getLogger("alerta")


def configurar_log(verboso: bool = False) -> None:
    cfgmod.ensure_dirs()
    nivel = logging.DEBUG if verboso else logging.INFO
    LOG.setLevel(nivel)
    LOG.handlers.clear()

    arquivo = RotatingFileHandler(
        os.path.join(cfgmod.LOG_DIR, "alerta.log"),
        maxBytes=1_000_000, backupCount=3, encoding="utf-8",
    )
    arquivo.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s"))

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S"))

    LOG.addHandler(arquivo)
    LOG.addHandler(console)


def imprimir_relatorio(resultado: dict) -> None:
    print()
    print(f"Ciclo concluído em {resultado['duracao_s']}s"
          + ("  [dry-run: nada foi enviado]" if resultado["dry_run"] else ""))
    print(f"  coletadas: {resultado['coletados']:>3}   "
          f"novas relevantes: {resultado['relevantes_novos']:>3}   "
          f"alertas: {resultado['alertas']}")
    print("  fontes:")
    for f in resultado["fontes"]:
        marca = "OK  " if f["ok"] else "ERRO"
        detalhe = f"{f['itens']} itens" if f["ok"] else (f["erro"] or "")[:90]
        print(f"    [{marca}] {f['nome']} — {detalhe}")


def imprimir_itens(itens: list[dict]) -> None:
    if not itens:
        print("\n  (nenhuma notícia relevante nova neste ciclo)")
        return
    print("\n  novas notícias relevantes:")
    for it in itens:
        selo = "★" if it.get("priority") else " "
        tags = it.get("tags") or ""
        if isinstance(tags, str):
            tags = tags.split(",")
        tags = [t for t in tags if t]
        print(f"   {selo} [{it['score']:>3}] {it['titulo'][:100]}")
        if tags:
            print(f"          {it['fonte']} · {', '.join(tags)}")


def cmd_once(cfg: dict, store: Store, dry_run: bool) -> int:
    monitor = Monitor(cfg, store, LOG)
    resultado = monitor.ciclo(dry_run=dry_run)
    imprimir_relatorio(resultado)
    imprimir_itens(store.recentes(20, "todos"))
    return 0


def cmd_exportar(cfg: dict, store: Store, destino: str) -> int:
    """Gera o painel estático (o mesmo HTML, com os dados embutidos)."""
    itens = dedupe.agrupar(store.recentes(300, "todos"))
    status = exportar.status_estatico(
        cfgmod.telegram_configurado(cfg),
        store.estatisticas(),
        store.ultima_atualizacao(),
    )
    caminho = exportar.gerar(itens, status, destino)
    tamanho = os.path.getsize(caminho) // 1024
    print(f"Painel estático: {caminho} ({len(itens)} notícias, {tamanho} KB)")
    return 0


def cmd_servir(cfg: dict, store: Store) -> int:
    monitor = Monitor(cfg, store, LOG)

    try:
        servidor = ServidorWeb(monitor, cfg, LOG)
    except OSError as e:
        LOG.error("Não consegui abrir a porta %s: %s", cfg["web"]["porta"], e)
        LOG.error("Feche o outro programa ou mude 'web.porta' no config.json.")
        return 2

    servidor.iniciar()
    monitor.iniciar_thread()

    print()
    print("  ┌───────────────────────────────────────────────┐")
    print("  │  Alerta Água RJ está no ar                    │")
    print(f"  │  Painel: {servidor.url:<36}│")
    print("  │  Ctrl+C para parar                            │")
    print("  └───────────────────────────────────────────────┘")
    print()

    try:
        while True:
            monitor._parar.wait(1.0)  # mantém o processo vivo
    except KeyboardInterrupt:
        print("\nEncerrando…")
    finally:
        monitor.parar()
        servidor.parar()
    return 0


def cmd_testar_telegram(cfg: dict) -> int:
    tg = cfg.get("telegram") or {}
    token, chat_id = (tg.get("bot_token") or "").strip(), (tg.get("chat_id") or "").strip()
    if not token or not chat_id:
        print("Telegram ainda não configurado. Rode:  python setup.py")
        return 1
    ok, resp = telegram.enviar(
        token, chat_id,
        "✅ <b>Alerta Água RJ</b>\nTeste concluído. Você vai receber aqui os avisos de abastecimento.",
    )
    if ok:
        print("Mensagem de teste enviada. Confira o Telegram.")
        return 0
    print(f"Falhou: {resp.get('erro')}")
    return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Monitor de notícias de abastecimento do Rio de Janeiro")
    ap.add_argument("--once", action="store_true", help="executa um único ciclo e sai")
    ap.add_argument("--dry-run", action="store_true", help="não envia alertas no Telegram")
    ap.add_argument("--testar-telegram", action="store_true", help="envia mensagem de teste")
    ap.add_argument("--exportar-html", metavar="ARQUIVO",
                    help="gera o painel estático (ex.: docs/index.html)")
    ap.add_argument("--verboso", action="store_true", help="log detalhado")
    args = ap.parse_args(argv)

    configurar_log(args.verboso)
    cfg = cfgmod.load_config()
    cfgmod.ensure_dirs()

    if not cfgmod.telegram_configurado(cfg) and not args.testar_telegram:
        LOG.warning("Telegram não configurado — os alertas ficarão só no painel.")
        LOG.warning("Para configurar, rode:  python setup.py")

    store = Store(cfgmod.caminho_banco())
    try:
        if args.testar_telegram:
            return cmd_testar_telegram(cfg)

        codigo = 0
        if args.once:
            codigo = cmd_once(cfg, store, args.dry_run)
        if args.exportar_html:
            codigo = cmd_exportar(cfg, store, args.exportar_html) or codigo

        if not args.once and not args.exportar_html:
            return cmd_servir(cfg, store)
        return codigo
    finally:
        store.fechar()


if __name__ == "__main__":
    raise SystemExit(main())
