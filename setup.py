#!/usr/bin/env python3
"""Assistente de configuração do Telegram (roda uma vez só).

    python setup.py

Cria o config.json, valida o token do bot, descobre o seu chat_id e manda
uma mensagem de teste.
"""
from __future__ import annotations

import argparse
import sys
import time

for _fluxo in (sys.stdout, sys.stderr):
    if _fluxo and hasattr(_fluxo, "reconfigure"):
        try:
            _fluxo.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

from agua import config as cfgmod  # noqa: E402
from agua import telegram  # noqa: E402

LINHA = "─" * 62


def perguntar(texto: str) -> str:
    try:
        return input(texto).strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelado.")
        raise SystemExit(1)


def descobrir_chat_id(token: str, segundos: int = 90) -> str | None:
    print()
    print("Agora abra o Telegram, procure o seu bot e envie qualquer mensagem")
    print("(um simples \"oi\" já serve). Estou esperando…")
    limite = time.time() + segundos
    while time.time() < limite:
        ok, resp = telegram.chamar(token, "getUpdates", {"timeout": 5, "limit": 10}, timeout=15)
        if ok:
            for upd in resp.get("result", []):
                msg = upd.get("message") or upd.get("edited_message") or {}
                chat = msg.get("chat") or {}
                if chat.get("id"):
                    nome = chat.get("first_name") or chat.get("title") or "você"
                    print(f"  ✓ conversa encontrada: {nome} (id {chat['id']})")
                    return str(chat["id"])
        time.sleep(3)
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Configura o bot do Telegram")
    ap.add_argument("--token", help="token do bot (BotFather)")
    ap.add_argument("--chat-id", help="seu chat id (pula a descoberta automática)")
    ap.add_argument("--sem-teste", action="store_true", help="não envia mensagem de teste")
    args = ap.parse_args(argv)

    cfgmod.ensure_dirs()
    cfg = cfgmod.load_config()

    print(LINHA)
    print("  Alerta Água RJ — configuração do Telegram")
    print(LINHA)
    print()
    print("Se ainda não tem um bot:")
    print("  1. no Telegram, fale com @BotFather")
    print("  2. envie /newbot e escolha um nome")
    print("  3. copie o token que ele devolver (parece 123456:ABC-DEF…)")
    print()

    token = (args.token or (cfg["telegram"].get("bot_token") or "")).strip()
    if not token:
        token = perguntar("Cole o token do bot: ")
    if not token:
        print("Token vazio — nada a fazer.")
        return 1

    ok, resp = telegram.chamar(token, "getMe", timeout=15)
    if not ok:
        print(f"\n✗ Token inválido ou sem conexão: {resp.get('erro')}")
        return 1
    bot = resp.get("result", {})
    print(f"\n✓ Bot validado: @{bot.get('username')} ({bot.get('first_name')})")

    chat_id = (args.chat_id or (cfg["telegram"].get("chat_id") or "")).strip()
    if not chat_id:
        chat_id = descobrir_chat_id(token) or ""
    if not chat_id:
        print("\n✗ Não recebi nenhuma mensagem. Rode de novo e mande \"oi\" para o bot.")
        return 1

    cfg["telegram"]["bot_token"] = token
    cfg["telegram"]["chat_id"] = chat_id
    cfgmod.save_config(cfg)
    print(f"\n✓ Configuração salva em {cfgmod.CONFIG_PATH}")

    if not args.sem_teste:
        ok, resp = telegram.enviar(
            token, chat_id,
            "✅ <b>Alerta Água RJ configurado</b>\n"
            "A partir de agora você recebe aqui as notícias que afetam o abastecimento "
            "— com prioridade para Santa Cruz e Zona Oeste.",
        )
        if ok:
            print("✓ Mensagem de teste enviada. Confira o Telegram.")
        else:
            print(f"✗ Não consegui enviar a mensagem de teste: {resp.get('erro')}")
            return 1

    print()
    print("Próximo passo:  python app.py")
    print(f"Painel:         http://127.0.0.1:{cfg['web']['porta']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
