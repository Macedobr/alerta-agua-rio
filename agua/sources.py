"""Coleta de notícias em fontes públicas (RSS e HTML).

Fontes:
  * Google News RSS  - agrega veículos (G1, O Globo, Extra, Diário do Rio...)
  * Águas do Rio     - feed RSS nativo do site oficial
  * CEDAE            - lista de notícias no site oficial (sem RSS, scraping)
"""
from __future__ import annotations

import hashlib
import html as htmllib
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

GOOGLE_NEWS = "https://news.google.com/rss/search?{qs}"
AGUAS_FEED = "https://www.aguasdorio.com.br/feed/"
CEDAE_LISTA = "https://www.cedae.com.br/Noticias"

_MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "março": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
    "outubro": 10, "novembro": 11, "dezembro": 12,
}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def http_get(url: str, timeout: int = 25) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/xml, text/html;q=0.9, */*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.5",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def strip_tags(valor: str) -> str:
    if not valor:
        return ""
    texto = re.sub(r"<[^>]+>", " ", valor)
    texto = htmllib.unescape(texto)
    return re.sub(r"\s+", " ", texto).strip()


def chave(link: str) -> str:
    return hashlib.sha1(link.strip().encode("utf-8")).hexdigest()


def parse_data(valor: str) -> datetime | None:
    if not valor:
        return None
    valor = valor.strip()
    try:
        dt = parsedate_to_datetime(valor)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        pass
    try:
        dt = datetime.fromisoformat(valor.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _item(fonte, titulo, link, publicado, resumo="", tipo="noticia") -> dict:
    return {
        "fonte": fonte,
        "titulo": strip_tags(titulo),
        "link": (link or "").strip(),
        "publicado": publicado,
        "resumo": strip_tags(resumo)[:600],
        "tipo": tipo,
        "chave": chave(link),
    }


# ---------------------------------------------------------------------------
# RSS (Google News e Águas do Rio)
# ---------------------------------------------------------------------------

def parse_rss(dados: bytes, fonte_padrao: str, tipo: str = "noticia") -> list[dict]:
    raiz = ET.fromstring(dados)
    itens: list[dict] = []

    for node in raiz.iter("item"):
        titulo = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        if not titulo or not link:
            continue

        source_el = node.find("source")
        fonte = (source_el.text or "").strip() if source_el is not None else ""
        fonte = fonte or fonte_padrao

        # Google News anexa " - Veículo" ao título.
        sufixo = f" - {fonte}"
        if titulo.endswith(sufixo):
            titulo = titulo[: -len(sufixo)].strip()

        itens.append(_item(
            fonte=fonte,
            titulo=titulo,
            link=link,
            publicado=parse_data(node.findtext("pubDate") or ""),
            resumo=node.findtext("description") or "",
            tipo=tipo,
        ))
    return itens


def fetch_google_news(consulta: str, janela: str = "7d", timeout: int = 25) -> list[dict]:
    if "when:" not in consulta:
        consulta = f"{consulta} when:{janela}"
    qs = urllib.parse.urlencode({
        "q": consulta,
        "hl": "pt-BR",
        "gl": "BR",
        "ceid": "BR:pt-419",
    })
    dados = http_get(GOOGLE_NEWS.format(qs=qs), timeout=timeout)
    return parse_rss(dados, fonte_padrao="Google News", tipo="imprensa")


def fetch_aguas_do_rio(timeout: int = 25) -> list[dict]:
    dados = http_get(AGUAS_FEED, timeout=timeout)
    return parse_rss(dados, fonte_padrao="Águas do Rio", tipo="oficial")


# ---------------------------------------------------------------------------
# CEDAE (HTML)
# ---------------------------------------------------------------------------

def _inferir_data(dia: int, mes_nome: str) -> datetime | None:
    mes = _MESES.get(mes_nome.lower().strip())
    if not mes:
        return None
    agora = datetime.now(timezone.utc)
    for ano in (agora.year, agora.year - 1):
        try:
            return datetime(ano, mes, dia, 12, 0, tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def fetch_cedae(timeout: int = 25) -> list[dict]:
    html = http_get(CEDAE_LISTA, timeout=timeout).decode("utf-8", "ignore")
    itens: list[dict] = []

    for bloco in re.findall(r'<div class="item">(.*?)</div>', html, re.S):
        link_m = re.search(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', bloco, re.S)
        if not link_m:
            continue
        link = link_m.group(1).strip()
        titulo = strip_tags(link_m.group(2))
        if not titulo:
            continue
        if link.startswith("/"):
            link = "https://www.cedae.com.br" + link

        dia_m = re.search(r'class="dia">(?:<span[^>]*>)?(\d{1,2})', bloco)
        mes_m = re.search(r'class="mes">(?:<span[^>]*>)?([A-Za-zÀ-ÿ]+)', bloco)
        publicado = None
        if dia_m and mes_m:
            publicado = _inferir_data(int(dia_m.group(1)), mes_m.group(1))

        resumo_m = re.search(r"<p>(.*?)</p>", bloco, re.S)
        itens.append(_item(
            fonte="CEDAE",
            titulo=titulo,
            link=link,
            publicado=publicado,
            resumo=resumo_m.group(1) if resumo_m else "",
            tipo="oficial",
        ))
    return itens


# ---------------------------------------------------------------------------
# Orquestração
# ---------------------------------------------------------------------------

def todas_as_fontes(config: dict, timeout: int = 25) -> list[tuple[str, callable]]:
    """Lista (nome, função) que devolve itens. Cada função pode levantar erro."""
    janela = config["coleta"].get("janela_queries", "7d")
    fontes: list[tuple[str, callable]] = [
        ("Águas do Rio (oficial)", lambda: fetch_aguas_do_rio(timeout)),
        ("CEDAE (oficial)", lambda: fetch_cedae(timeout)),
    ]
    for consulta in config["coleta"]["queries"]:
        fontes.append((
            f"Google News · {consulta}",
            lambda c=consulta: fetch_google_news(c, janela, timeout),
        ))
    return fontes


def descrever(item: dict) -> str:
    when = item["publicado"].astimezone().strftime("%d/%m %H:%M") if item["publicado"] else "sem data"
    return f"[{item['fonte']}] {when} · {item['titulo']}"
