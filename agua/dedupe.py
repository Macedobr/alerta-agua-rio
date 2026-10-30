"""Agrupa notícias do mesmo fato publicadas por veículos diferentes."""
from __future__ import annotations

from .texto import parecido, tokens


def agrupar(itens: list[dict], limite: float = 0.7) -> list[dict]:
    grupos: list[dict] = []

    for item in itens:
        toks = tokens(item.get("titulo", ""))
        alvo = next((g for g in grupos if parecido(toks, g["tokens"], limite)), None)
        if alvo is None:
            grupos.append({
                "rep": item,
                "tokens": toks,
                "fontes": {item.get("fonte", "")},
                "n": 1,
            })
            continue

        alvo["n"] += 1
        alvo["fontes"].add(item.get("fonte", ""))
        if item.get("score", 0) > alvo["rep"].get("score", 0):
            alvo["rep"] = item
            alvo["tokens"] = toks

    saida: list[dict] = []
    for g in grupos:
        registro = dict(g["rep"])
        registro["fontes"] = sorted(f for f in g["fontes"] if f)
        registro["duplicados"] = g["n"] - 1
        saida.append(registro)

    saida.sort(key=lambda i: (i.get("publicado") or i.get("visto_em") or ""), reverse=True)
    return saida
