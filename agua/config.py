"""Configuração do Alerta Água RJ."""
from __future__ import annotations

import copy
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
DATA_DIR = os.path.join(BASE_DIR, "data")
LOG_DIR = os.path.join(BASE_DIR, "logs")
DB_PATH = os.path.join(DATA_DIR, "agua.db")

DEFAULTS = {
    "telegram": {
        "bot_token": "",
        "chat_id": "",
    },
    "pontuacao": {
        # Nota mínima para a notícia entrar no painel.
        "minimo_painel": 45,
        # Nota mínima para virar alerta no Telegram (quando é prioritária).
        "minimo_alerta": 60,
    },
    "alertas": {
        "max_por_ciclo": 4,
        "janela_cluster_horas": 12,
        "similaridade_cluster": 0.65,
        # Notícias mais antigas que isso não geram alerta (mas ficam no painel).
        "idade_maxima_horas": 72,
        "enviar_primeira_vez": True,
    },
    "coleta": {
        "intervalo_segundos": 120,
        "timeout_segundos": 25,
        # Janela do operador "when:" das buscas no Google News.
        "janela_queries": "7d",
        # Notícias mais velhas que isso nem entram no banco.
        "idade_maxima_dias": 14,
        "queries": [
            "abastecimento água Santa Cruz Rio de Janeiro",
            "falta de água Santa Cruz",
            "\"Águas do Rio\" Santa Cruz",
            "abastecimento Zona Oeste Rio de Janeiro",
            "Guandu abastecimento Rio de Janeiro",
            "Cedae manutenção abastecimento Rio",
            "racionamento água Rio de Janeiro",
        ],
    },
    "web": {
        "host": "127.0.0.1",
        "porta": 8765,
    },
}


def _merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
            cfg = _merge(DEFAULTS, json.load(f))
    else:
        cfg = copy.deepcopy(DEFAULTS)
    return _aplicar_env(cfg)


def _aplicar_env(cfg: dict) -> dict:
    """Permite rodar sem config.json (nuvem), lendo segredos do ambiente."""
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
    if token:
        cfg["telegram"]["bot_token"] = token
    if chat_id:
        cfg["telegram"]["chat_id"] = chat_id

    intervalo = (os.environ.get("AGUA_INTERVALO") or "").strip()
    if intervalo.isdigit() and int(intervalo) >= 60:
        cfg["coleta"]["intervalo_segundos"] = int(intervalo)

    porta = (os.environ.get("AGUA_PORTA") or "").strip()
    if porta.isdigit():
        cfg["web"]["porta"] = int(porta)

    return cfg


def caminho_banco() -> str:
    return (os.environ.get("AGUA_DB_PATH") or "").strip() or DB_PATH


def save_config(cfg: dict) -> None:
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG_PATH)


def ensure_dirs() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)


def telegram_configurado(cfg: dict) -> bool:
    tg = cfg.get("telegram") or {}
    return bool((tg.get("bot_token") or "").strip()) and bool((tg.get("chat_id") or "").strip())
