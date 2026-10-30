"""Envio de mensagens pelo Telegram (Bot API)."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import timezone

API = "https://api.telegram.org/bot{token}/{metodo}"
LIMITE_TEXTO = 3900


def chamar(token: str, metodo: str, payload: dict | None = None, timeout: int = 20):
    """Devolve (ok, resposta). Nunca levanta exceção de rede."""
    url = API.format(token=token, metodo=metodo)
    dados = json.dumps(payload or {}).encode("utf-8")
    req = urllib.request.Request(
        url, data=dados, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            corpo = json.loads(e.read().decode("utf-8"))
        except Exception:
            corpo = {}
        return False, {
            "erro": corpo.get("description") or f"HTTP {e.code}",
            "codigo": e.code,
        }
    except Exception as e:  # timeout, DNS, TLS...
        return False, {"erro": f"{type(e).__name__}: {e}", "codigo": 0}


def enviar(token: str, chat_id: str, texto: str) -> tuple[bool, dict]:
    if len(texto) > LIMITE_TEXTO:
        texto = texto[: LIMITE_TEXTO - 20] + "\n\n<i>…</i>"
    return chamar(token, "sendMessage", {
        "chat_id": chat_id,
        "text": texto,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    })


def _quando(item: dict) -> str:
    dt = item.get("publicado")
    if not dt:
        return "agora"
    return dt.astimezone().strftime("%d/%m às %H:%M")


def formatar(item: dict) -> str:
    titulo = _esc(item.get("titulo", ""))
    tags = item.get("tags") or []
    if isinstance(tags, str):
        tags = [t for t in tags.split(",") if t]

    if "Santa Cruz" in tags:
        cabeca = "🚨 <b>Abastecimento · Santa Cruz</b>"
    elif "Zona Oeste" in tags:
        cabeca = "⚠️ <b>Abastecimento · Zona Oeste</b>"
    elif "Guandu" in tags:
        cabeca = "⚠️ <b>Sistema Guandu</b>"
    else:
        cabeca = "💧 <b>Abastecimento · Rio de Janeiro</b>"

    linhas = [cabeca, "", f"<b>{titulo}</b>", ""]
    linhas.append(f"📰 {_esc(item.get('fonte', ''))} · {_quando(item)}")
    if tags:
        linhas.append("🏷 " + " · ".join(_esc(t) for t in tags))

    resumo = (item.get("resumo") or "").strip()
    if resumo:
        if len(resumo) > 280:
            resumo = resumo[:277].rsplit(" ", 1)[0] + "…"
        linhas += ["", f"<i>{_esc(resumo)}</i>"]

    link = item.get("link", "")
    if link:
        linhas += ["", f'<a href="{_esc(link)}">Abrir notícia</a>']
    return "\n".join(linhas)


def formatar_boas_vindas(itens: list[dict], total_painel: int, intervalo_min: int) -> str:
    linhas = [
        "✅ <b>Monitor de abastecimento ativo</b>",
        "",
        f"Vigiando as fontes a cada {intervalo_min} min.",
        f"{total_painel} notícias relevantes no painel agora.",
    ]
    if itens:
        linhas += ["", "<b>Destaques do momento:</b>"]
        for it in itens[:3]:
            linhas.append(
                f"• <a href=\"{_esc(it.get('link',''))}\">{_esc(it.get('titulo',''))}</a>"
            )
    linhas += ["", "A partir de agora, aviso aqui assim que sair algo novo."]
    return "\n".join(linhas)


def _esc(texto: str) -> str:
    return (
        (texto or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
