import os
import requests
from flask import Flask, request
from dotenv import load_dotenv
from responder_oficina import responder_oficina

load_dotenv()

app = Flask(__name__)

# 🔒 CONTROLE DE DUPLICIDADE (MEMÓRIA TEMPORÁRIA)
MENSAGENS_PROCESSADAS = set()

# ============================================================
# VARIÁVEIS DE AMBIENTE
# ============================================================
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WA_PHONE_NUMBER_ID = os.getenv("WA_PHONE_NUMBER_ID")
WA_ACCESS_TOKEN = os.getenv("WA_ACCESS_TOKEN")

# ============================================================
# HOME
# ============================================================
@app.route("/", methods=["GET"])
def home():
    return "OK", 200

# ============================================================
# POLÍTICA DE PRIVACIDADE (META REQUIREMENT)
# ============================================================
@app.route("/politica-de-privacidade", methods=["GET"])
def politica_privacidade():
    return """
    <h1>Política de Privacidade – Sullato Oficina</h1>
    <p>A Sullato Oficina utiliza dados fornecidos exclusivamente para atendimento,
    suporte e comunicação referente aos serviços solicitados.</p>
    <p>Não compartilhamos informações com terceiros.</p>
    <p>Contato: anderson@sullato.com.br</p>
    """, 200

# ============================================================
# VERIFICAÇÃO META
# ============================================================
@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge"), 200
    return "Erro", 403

# ============================================================
# NORMALIZA DROPBOX
# ============================================================
def normalizar_dropbox(url):
    if not url:
        return ""
    u = url.strip()
    u = u.replace("https://www.dropbox.com", "https://dl.dropboxusercontent.com")
    u = u.replace("?dl=0", "")
    return u

# ============================================================
# ENVIO TEMPLATE
# ============================================================
def enviar_template_oficina(numero, imagem_url):
    url = f"https://graph.facebook.com/v20.0/{WA_PHONE_NUMBER_ID}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "template",
        "template": {
            "name": "oficina_promocao",
            "language": {"code": "pt_BR"},
            "components": [
                {
                    "type": "header",
                    "parameters": [
                        {
                            "type": "image",
                            "image": {"link": imagem_url}
                        }
                    ]
                }
            ]
        }
    }

    headers = {
        "Authorization": f"Bearer {WA_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    r = requests.post(url, json=payload, headers=headers, timeout=30)
    print("📤 TEMPLATE:", r.status_code, r.text)

# ============================================================
# WEBHOOK POST
# ============================================================
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}

    print("📩 PAYLOAD RECEBIDO:")
    print(data)

    # ===== DISPARO APPS SCRIPT =====
    if data.get("origem") == "apps_script_disparo":
        imagem = normalizar_dropbox(data.get("imagem_url"))
        enviar_template_oficina(
            numero=data.get("numero"),
            imagem_url=imagem
        )
        return "OK", 200

    # ===== EVENTOS META =====
    if "entry" not in data:
        return "OK", 200

    for entry in data["entry"]:
        for change in entry.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages")
            contacts = value.get("contacts")

            if not messages or not contacts:
                continue

            msg = messages[0]

            # 🔒 IGNORA eventos que não são mensagens do usuário
            if "from" not in msg:
                continue

            message_id = msg.get("id")

            # 🔒 BLOQUEIO DE DUPLICIDADE PELO MESSAGE ID
            message_id = msg.get("id")

            # 🔒 BLOQUEIO DE DUPLICIDADE
            if message_id in MENSAGENS_PROCESSADAS:
                print("⚠️ Mensagem duplicada ignorada:", message_id)
                continue

            MENSAGENS_PROCESSADAS.add(message_id)

            numero = contacts[0].get("wa_id")

            # 🔒 IGNORA se não for realmente o número do usuário
            if msg.get("from") != numero:
                continue

            nome = contacts[0].get("profile", {}).get("name", "Cliente")

            texto = ""

            # ===== TEXTO DIGITADO =====
            if msg.get("type") == "text":
                texto = msg.get("text", {}).get("body", "").strip()

            # ===== INTERACTIVE (BOTÕES / LISTA) =====
            elif msg.get("type") == "interactive":
                interactive = msg.get("interactive", {})
                tipo = interactive.get("type")

                if tipo == "button_reply":
                    texto = interactive["button_reply"].get("id") \
                            or interactive["button_reply"].get("title")

                elif tipo == "list_reply":
                    texto = interactive["list_reply"].get("id") \
                            or interactive["list_reply"].get("title")

            # ===== BOTÃO TEMPLATE MARKETING =====
            elif msg.get("type") == "button":
                texto = msg.get("button", {}).get("text")

                # 🔥 BOTÃO DO TEMPLATE → REINICIA SESSÃO
                if texto.lower() in ["olá", "ola"]:
                    from responder_oficina import reset_sessao
                    reset_sessao(numero)

            if texto and len(texto.strip()) > 0:
                print(f"👉 RECEBIDO: {texto}")
                print("📞 ENVIANDO PARA RESPONDER:", numero)

                responder_oficina(
                    numero=numero,
                    texto_digitado=texto,
                    nome_whatsapp=nome
                )

    return "OK", 200

# ============================================================
# RUN
# ============================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
