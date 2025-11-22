import os
import json
from flask import Flask, request
from responder_oficina import responder_oficina  # garantir import correto

app = Flask(__name__)

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")


# ============================================================
# 🔹 WEBHOOK GET — VERIFICAÇÃO COM META
# ============================================================
@app.get("/webhook")
def verificar_webhook():
    try:
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            return challenge, 200
        else:
            return "Token inválido", 403

    except Exception as e:
        print("ERRO WEBHOOK GET:", e)
        return "Erro interno", 500


# ============================================================
# 🔹 WEBHOOK POST — RECEBE MENSAGENS DO WHATSAPP
# ============================================================
@app.post("/webhook")
def receber_mensagem():
    try:
        data = request.get_json()

        if not data:
            return "NO JSON", 200

        entry = data.get("entry", [])
        if not entry:
            return "NO ENTRY", 200

        changes = entry[0].get("changes", [])
        if not changes:
            return "NO CHANGES", 200

        value = changes[0].get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return "NO MSG", 200

        msg = messages[0]

        # ID do telefone do cliente
        fone = msg.get("from")
        if not fone:
            return "NO FROM", 200

        # nome do WhatsApp
        nome_whatsapp = ""
        profile = msg.get("profile")
        if profile and profile.get("name"):
            nome_whatsapp = profile.get("name")
        else:
            nome_whatsapp = "Cliente"

        # Tipo da mensagem
        msg_type = msg.get("type")

        # ============================
        # BOTÃO
        # ============================
        if msg_type == "interactive":
            inter = msg.get("interactive", {})
            botao = inter.get("button_reply") or inter.get("list_reply")
            if botao:
                payload = botao.get("id")
                responder_oficina(fone, nome_whatsapp, "", "botao", payload)
                return "OK", 200

        # ============================
        # TEXTO
        # ============================
        if msg_type == "text":
            texto = msg["text"]["body"]
            responder_oficina(fone, nome_whatsapp, texto, "texto", None)
            return "OK", 200

        return "IGNORED", 200

    except Exception as e:
        print("ERRO WEBHOOK POST:", e)
        return "Erro interno", 500


# ============================================================
# 🔹 ROTA TESTE
# ============================================================
@app.get("/")
def home():
    return "Sullato Oficina — Webhook ativo!", 200


# ============================================================
# 🔹 EXEC LOCAL
# ============================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
