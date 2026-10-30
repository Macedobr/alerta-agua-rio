"""Gera uma versão estática do painel, para publicar no GitHub Pages.

O HTML é o mesmo do painel local; a diferença é que os dados viajam embutidos
no arquivo (window.DADOS) em vez de virem de /api/itens.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

AQUI = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(AQUI, "dashboard.html")
MARCADOR = "<!-- DADOS -->"


def _enxugar(item: dict) -> dict:
    """Só o que a página usa — deixa o HTML bem menor."""
    return {
        "fonte": item.get("fonte", ""),
        "titulo": item.get("titulo", ""),
        "link": item.get("link", ""),
        "publicado": item.get("publicado") or item.get("visto_em"),
        "resumo": (item.get("resumo") or "")[:300],
        "score": item.get("score", 0),
        "tags": item.get("tags", ""),
        "alertado": item.get("alertado", 0),
        "duplicados": item.get("duplicados", 0),
        "fontes": item.get("fontes", []),
    }


def gerar(itens: list[dict], status: dict, destino: str) -> str:
    with open(TEMPLATE, "r", encoding="utf-8") as f:
        html = f.read()

    if MARCADOR not in html:
        raise RuntimeError(f"marcador {MARCADOR} não encontrado em {TEMPLATE}")

    dados = {
        "itens": [_enxugar(i) for i in itens],
        "status": status,
    }
    # "</" precisa ser escapado para não fechar o <script> antes da hora.
    payload = json.dumps(dados, ensure_ascii=False, default=str).replace("</", "<\\/")
    html = html.replace(MARCADOR, f"<script>window.DADOS = {payload};</script>\n{MARCADOR}")

    pasta = os.path.dirname(os.path.abspath(destino))
    os.makedirs(pasta, exist_ok=True)
    tmp = destino + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(html)
    os.replace(tmp, destino)
    return destino


def status_estatico(telegram_ativo: bool, totais: dict, gerado_em: str | None = None) -> dict:
    """`gerado_em` vem do banco (e não do relógio) para o HTML ser determinístico:
    sem notícia nova, o arquivo sai idêntico e o CI não cria commit."""
    return {
        "estatico": True,
        "gerado_em": gerado_em or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "telegram": telegram_ativo,
        "totais": totais,
        "fontes": [],
    }
