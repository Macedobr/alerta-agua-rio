"""Persistência em SQLite: histórico, deduplicação e fila de alertas."""
from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chave       TEXT UNIQUE NOT NULL,
    fonte       TEXT NOT NULL,
    tipo        TEXT,
    titulo      TEXT NOT NULL,
    link        TEXT NOT NULL,
    publicado   TEXT,
    resumo      TEXT,
    score       INTEGER DEFAULT 0,
    priority    INTEGER DEFAULT 0,
    tags        TEXT DEFAULT '',
    motivos     TEXT DEFAULT '',
    visto_em    TEXT NOT NULL,
    alertado    INTEGER DEFAULT 0,
    alertado_em TEXT
);
CREATE INDEX IF NOT EXISTS idx_items_pub ON items(publicado DESC);
CREATE INDEX IF NOT EXISTS idx_items_alertado ON items(alertado, publicado DESC);

CREATE TABLE IF NOT EXISTS meta (
    chave TEXT PRIMARY KEY,
    valor TEXT
);
"""


def _iso(dt: datetime | None) -> str | None:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat() if dt else None


class Store:
    def __init__(self, caminho: str):
        pasta = os.path.dirname(os.path.abspath(caminho))
        os.makedirs(pasta, exist_ok=True)
        self._lock = threading.RLock()
        self._sujo = False
        self._db = sqlite3.connect(caminho, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            self._db.executescript(SCHEMA)
            modo = self._db.execute("PRAGMA journal_mode").fetchone()[0]
            if str(modo).lower() != "wal":
                self._db.execute("PRAGMA journal_mode=WAL")
            self._db.commit()

    # -- itens -------------------------------------------------------------
    def inserir(self, item: dict) -> tuple[int | None, bool]:
        """Insere se for novo. Devolve (id, criado_agora)."""
        agora = _iso(datetime.now(timezone.utc))
        with self._lock:
            cur = self._db.execute(
                """
                INSERT INTO items (chave, fonte, tipo, titulo, link, publicado,
                                   resumo, score, priority, tags, motivos, visto_em)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(chave) DO NOTHING
                """,
                (
                    item["chave"], item["fonte"], item.get("tipo", ""),
                    item["titulo"], item["link"], _iso(item.get("publicado")),
                    item.get("resumo", ""), item.get("score", 0),
                    1 if item.get("priority") else 0,
                    ",".join(item.get("tags", [])),
                    ",".join(item.get("motivos", [])),
                    agora,
                ),
            )
            self._db.commit()
            if cur.rowcount:
                self._sujo = True
                return cur.lastrowid, True
            self._db.rollback()  # nada inserido: não deixa transação aberta
            row = self._db.execute("SELECT id FROM items WHERE chave=?", (item["chave"],)).fetchone()
            return (row["id"] if row else None), False

    def marcar_alertado(self, ids: list[int]) -> None:
        if not ids:
            return
        with self._lock:
            self._db.executemany(
                "UPDATE items SET alertado=1, alertado_em=? WHERE id=?",
                [(_iso(datetime.now(timezone.utc)), i) for i in ids],
            )
            self._db.commit()
            self._sujo = True

    def recentes(self, limite: int = 200, filtro: str = "todos") -> list[dict]:
        where = ""
        if filtro == "santa":
            where = "AND tags LIKE '%Santa Cruz%'"
        elif filtro == "oeste":
            where = "AND tags LIKE '%Zona Oeste%'"
        elif filtro == "guandu":
            where = "AND tags LIKE '%Guandu%'"
        elif filtro == "alertados":
            where = "AND alertado=1"
        with self._lock:
            rows = self._db.execute(
                f"SELECT * FROM items WHERE 1=1 {where} "
                "ORDER BY COALESCE(publicado, visto_em) DESC LIMIT ?",
                (limite,),
            ).fetchall()
        return [dict(r) for r in rows]

    def titulos_alertados_recentes(self, horas: int) -> list[str]:
        corte = _iso(datetime.now(timezone.utc) - timedelta(hours=horas))
        with self._lock:
            rows = self._db.execute(
                "SELECT titulo FROM items WHERE alertado=1 AND alertado_em >= ? "
                "AND priority=1",
                (corte,),
            ).fetchall()
        return [r["titulo"] for r in rows]

    def estatisticas(self) -> dict:
        with self._lock:
            total = self._db.execute("SELECT COUNT(*) c FROM items").fetchone()["c"]
            alertados = self._db.execute(
                "SELECT COUNT(*) c FROM items WHERE alertado=1"
            ).fetchone()["c"]
            hoje = _iso(datetime.now(timezone.utc) - timedelta(hours=24))
            recentes = self._db.execute(
                "SELECT COUNT(*) c FROM items WHERE COALESCE(publicado, visto_em) >= ?",
                (hoje,),
            ).fetchone()["c"]
        return {"total": total, "alertados": alertados, "ultimas_24h": recentes}

    def existe_item(self, chave_item: str) -> bool:
        with self._lock:
            return self._db.execute(
                "SELECT 1 FROM items WHERE chave=?", (chave_item,)
            ).fetchone() is not None

    # -- meta --------------------------------------------------------------
    def meta_get(self, chave: str, padrao: str | None = None) -> str | None:
        with self._lock:
            row = self._db.execute("SELECT valor FROM meta WHERE chave=?", (chave,)).fetchone()
        return row["valor"] if row else padrao

    def meta_set(self, chave: str, valor: str) -> None:
        valor = str(valor)
        with self._lock:
            row = self._db.execute("SELECT valor FROM meta WHERE chave=?", (chave,)).fetchone()
            if row and row["valor"] == valor:
                return  # nada mudou: não suja o arquivo (importante no CI)
            self._db.execute(
                "INSERT INTO meta (chave, valor) VALUES (?,?) "
                "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
                (chave, valor),
            )
            self._db.commit()
            self._sujo = True

    def ultima_atualizacao(self) -> str | None:
        """Horário da última mudança de conteúdo (para o painel estático)."""
        with self._lock:
            row = self._db.execute(
                "SELECT MAX(COALESCE(alertado_em, visto_em)) AS t FROM items"
            ).fetchone()
        return row["t"] if row else None

    def fechar(self) -> None:
        with self._lock:
            if self._sujo:
                try:
                    self._db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    self._db.commit()
                except sqlite3.Error:
                    pass
            self._db.close()
