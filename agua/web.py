"""Painel web local (somente leitura) servido com a biblioteca padrão."""
from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import dedupe

AQUI = os.path.dirname(os.path.abspath(__file__))
DASHBOARD = os.path.join(AQUI, "dashboard.html")


def _handler(monitor, cfg, log):
    class Handler(BaseHTTPRequestHandler):
        server_version = "AlertaAguaRJ/1.0"

        def do_GET(self):  # noqa: N802
            rota = urlparse(self.path)
            try:
                if rota.path in ("/", "/index.html"):
                    self._html()
                elif rota.path == "/api/status":
                    self._json(monitor.snapshot())
                elif rota.path == "/api/itens":
                    qs = parse_qs(rota.query)
                    filtro = (qs.get("filtro") or ["todos"])[0]
                    limite = min(int((qs.get("limite") or ["200"])[0]), 1000)
                    self._json({
                        "itens": dedupe.agrupar(monitor.store.recentes(limite, filtro)),
                        "status": monitor.snapshot(),
                    })
                elif rota.path == "/saude":
                    self._json({"ok": True})
                else:
                    self.send_error(404, "Rota não encontrada")
            except Exception as e:  # nunca derrubar o servidor
                log.exception("Erro no painel: %s", e)
                try:
                    self.send_error(500, str(e))
                except Exception:
                    pass

        # -- respostas -----------------------------------------------------
        def _html(self):
            with open(DASHBOARD, "rb") as f:
                corpo = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def _json(self, dados):
            corpo = json.dumps(dados, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def log_message(self, formato, *args):
            return  # silencioso

    return Handler


class ServidorWeb:
    def __init__(self, monitor, cfg, log):
        self.cfg = cfg
        self.log = log
        host = cfg["web"]["host"]
        porta = cfg["web"]["porta"]
        self.httpd = ThreadingHTTPServer((host, porta), _handler(monitor, cfg, log))
        self.httpd.daemon_threads = True
        self._thread: threading.Thread | None = None
        self.url = f"http://{host}:{porta}"

    def iniciar(self) -> None:
        self._thread = threading.Thread(target=self.httpd.serve_forever, name="web", daemon=True)
        self._thread.start()
        self.log.info("Painel disponível em %s", self.url)

    def parar(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
