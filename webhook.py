# ============================================================
# webhook.py — Webhook Oficial Chatbot Oficina Sullato
# Compatível com responder_oficina.py (nova estrutura)
# ============================================================

from flask import Flask, request, jsonify
import requests
import os
from datetime import datetime
import responder_oficina as responder

app = Flask(__name__)

# ==========================
# VARIÁVEIS DE AMBIENTE
# ==========================

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "sullato_token_verificacao")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
WA_PHONE_NUMBER_ID = os.getenv("WA_PHONE_NUMBER_ID")

# ==========================
# LOG
# ==========================

def hora_sp():
    return datetime.utcnow().strftime("%d/%m/%Y %H:%M:%S")

# ==========================
# ROTA GET (VERIFICAÇÃO META)
# ==========================

@app.route("/webhook", methods=["GET"])
def verificar_meta():
    try:
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            print(f"[{hora_sp()}] ✔ WEBHOOK VERIFICADO COM SUCESSO!")
            return challenge, 200
        else:
            print(f"[{hora_sp()}] ❌ Token inválido na verificação GET")
            return "Token inválido", 403

    except Exception as e:
        print(f"[{hora_sp()}] ❌ Erro na verificação GET:", e)
        return "erro", 500

# ==========================
# ROTA POST (RECEBIMENTO DE EVENTOS)
# ==========================

@app.route("/webhook", methods=["POST"])
def receber_evento():
    try:
        dados = request.get_json()

        if not dados:
            return "no data", 200

        # Structure: entry > changes > value > messages
        entry = dados.get("entry", [])
        if not entry:
            return "ok", 200

        changes = entry[0].get("changes", [])
        if not changes:
            return "ok", 200

        value = changes[0].get("value", {})
        mensagens = value.get("messages", [])

        if not mensagens:
            return "ok", 200

        msg = mensagens[0]

        fone = msg.get("from")
        tipo = msg.get("type")

        # ==========================
        # TEXTO — MENSAGEM DIGITADA
        # ==========================
        if tipo == "text":
            texto = msg["text"]["body"]
            try:
                responder.responder_oficina(fone, texto)
            except Exception as e:
                print(f"[{hora_sp()}] ⚠ Erro ao processar TEXTO:", e)

        # ==========================
        # BOTÃO — interactive.button_reply
        # ==========================
        elif tipo == "interactive":
            try:
                botao = msg["interactive"]["button_reply"]["id"]
                responder.responder_oficina(fone, "", tipo_botao=botao)
            except Exception as e:
                print(f"[{hora_sp()}] ⚠ Erro ao processar BOTÃO:", e)

        return "ok", 200

    except Exception as e:
        print(f"[{hora_sp()}] ❌ ERRO GERAL NO POST:", e)
        return "erro", 500

# ==========================
# EXECUTAR LOCAL
# ==========================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
