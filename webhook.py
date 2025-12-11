import os
import json
import time
from flask import Flask, request
from responder_oficina import responder_oficina, enviar_imagem, enviar_texto

app = Flask(__name__)

VERIFY_TOKEN = os.getenv("WA_VERIFY_TOKEN")


@app.route("/", methods=["GET"])
def home():
    return "ONLINE", 200


# ============================================================
# VERIFICAÇÃO DO WEBHOOK (META → FLASK)
# ============================================================

@app.route("/webhook", methods=["GET"])
def verificar_token():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200

    return "Token inválido", 403


# ============================================================
# RECEBIMENTO DE MENSAGENS (WHATSAPP → FLASK)
# ============================================================

@app.route("/webhook", methods=["POST"])
def receber_mensagem():
    data = request.get_json()

    try:
        print("📥 RECEBIDO:", json.dumps(data, indent=2, ensure_ascii=False))

        if "entry" in data:
            for entry in data["entry"]:
                if "changes" not in entry:
                    continue

                for change in entry["changes"]:
                    value = change.get("value", {})

                    messages = value.get("messages")
                    contacts = value.get("contacts")

                    if not messages or not contacts:
                        continue

                    mensagem = messages[0]
                    contato = contacts[0]

                    numero = contato.get("wa_id")
                    nome_whatsapp = contato.get("profile", {}).get("name", "Cliente")

                    texto = ""

                    # Texto normal
                    if mensagem.get("type") == "text":
                        texto = mensagem["text"]["body"]

                    # Botões / lista
                    elif mensagem.get("type") == "interactive":
                        inter = mensagem.get("interactive", {})
                        if inter.get("type") == "button_reply":
                            texto = inter["button_reply"]["id"]
                        elif inter.get("type") == "list_reply":
                            texto = inter["list_reply"]["id"]

                    # Quando vem campo "button"
                    if "button" in mensagem:
                        texto = mensagem["button"].get("payload") or mensagem["button"].get("text", "")

                    if texto == "":
                        texto = "undefined"

                    print(f"➡️ Texto interpretado: {texto}")

                    responder_oficina(numero, texto, nome_whatsapp)

        return "EVENT_RECEIVED", 200

    except Exception as e:
        print("❌ ERRO NO WEBHOOK:", str(e))
        return "ERRO", 200


# ============================================================
# ⚡ DISPARO DE MÍDIA — TEXTO + IMAGEM
# ============================================================

@app.route("/disparo_midia", methods=["POST"])
def disparo_midia():
    try:
        data = request.get_json()

        print("📥 DISPARO MIDIA RECEBIDO:", json.dumps(data, indent=2, ensure_ascii=False))

        numero = data.get("numero")
        imagem_url = data.get("imagem_url")

        if not numero or not imagem_url:
            return {"erro": "Payload inválido"}, 400

        # Texto igual ao template aprovado
        texto_template = (
            "Olá! 👋\n"
            "Confira a *Oferta Especial do Mês da Oficina Sullato!* 🔧🚗\n\n"
            "Clique na imagem abaixo e veja como aproveitar esta condição exclusiva!"
        )

        texto_final = texto_template.rstrip()

        # 1) Envia texto
        enviar_texto(numero, texto_final)

        # Dar tempo da API processar
        time.sleep(0.4)

        # 2) Envia a imagem
        enviar_imagem(numero, imagem_url)

        return {"status": "OK", "mensagem": "Texto e imagem enviados"}, 200

    except Exception as e:
        print("❌ ERRO DISPARO MIDIA:", str(e))
        return {"erro": str(e)}, 500


# ============================================================
# EXECUÇÃO DO FLASK
# ============================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
