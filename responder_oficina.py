# responder_oficina.py — Sullato Oficina e Pós-Venda
# ================================================================
# Estrutura baseada no chatbot da Clínica Luma, adaptada para o setor automotivo.
# ================================================================

import os, re, json, requests, time
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any, List

# ===== Variáveis de ambiente ====================================
WA_ACCESS_TOKEN    = os.getenv("WA_ACCESS_TOKEN", "").strip() or os.getenv("ACCESS_TOKEN", "").strip()
WA_PHONE_NUMBER_ID = os.getenv("WA_PHONE_NUMBER_ID", "").strip() or os.getenv("PHONE_NUMBER_ID", "").strip()

NOME_EMPRESA   = os.getenv("NOME_EMPRESA", "Sullato Oficina e Pós-Venda").strip()
LINK_SITE      = os.getenv("LINK_SITE", "https://www.sullato.com.br").strip()
LINK_INSTAGRAM = os.getenv("LINK_INSTAGRAM", "https://www.instagram.com/sullatomicrosevans").strip()

GRAPH_URL = f"https://graph.facebook.com/v20.0/{WA_PHONE_NUMBER_ID}/messages" if WA_PHONE_NUMBER_ID else ""
HEADERS   = {"Authorization": f"Bearer {WA_ACCESS_TOKEN}", "Content-Type": "application/json"}

# ===== Funções utilitárias ====================================================
def _hora_sp():
    return datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%Y-%m-%d %H:%M:%S")

def _send_text(to: str, text: str):
    """Envia mensagens de texto no WhatsApp."""
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": text[:4096]}
    }
    requests.post(GRAPH_URL, headers=HEADERS, json=payload, timeout=30)

def _send_buttons(to: str, body: str, buttons: List[Dict[str, str]]):
    """Envia botões interativos."""
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body[:1024]},
            "action": {"buttons": [{"type": "reply", "reply": b} for b in buttons[:3]]}
        }
    }
    requests.post(GRAPH_URL, headers=HEADERS, json=payload, timeout=30)

# ===== Boas-vindas ============================================================
def msg_boas_vindas(nome=None):
    nome_fmt = nome or ""
    saudacao = f"Olá {nome_fmt}," if nome_fmt else "Olá,"
    return (
        f"{saudacao} 👋\n"
        f"Bem-vindo(a) à *{NOME_EMPRESA}*! 🚗🔧\n\n"
        "Aqui você agenda serviços, solicita peças, fala com o pós-venda e muito mais.\n\n"
        "Escolha abaixo como deseja seguir:"
    )

# ===== Botões principais ======================================================
BTN_ROOT = [
    {"id": "op_servicos", "title": "Serviços"},
    {"id": "op_pecas", "title": "Peças"},
    {"id": "op_mais", "title": "Mais opções"},
]

BTN_MAIS = [
    {"id": "op_posvenda", "title": "Pós-venda"},
    {"id": "op_endereco", "title": "Endereço"},
    {"id": "op_voltar", "title": "Voltar ao início"},
]

BTN_ENDERECOS = [
    {"id": "end_loja", "title": "📍 Loja Principal"},
    {"id": "end_oficina", "title": "🔧 Oficina e Peças"},
    {"id": "op_voltar", "title": "Voltar"},
]

BTN_POSVENDA = [
    {"id": "pos_garantia", "title": "Garantia"},
    {"id": "pos_agendar", "title": "Agendar Serviço"},
    {"id": "op_voltar", "title": "Voltar"},
]

MSG_ENDERECOS = (
    "🏠 *Endereços Sullato*\n\n"
    "📍 *Loja Principal*\n"
    "Av. São Miguel, 4049/4084 – CEP 03871-000\n"
    "☎️ (11) 94054-5704\n\n"
    "📍 *Oficina e Peças*\n"
    "Av. São Miguel, 7900 – CEP 08070-001\n"
    "☎️ (11) 94054-5704\n\n"
    f"🌐 Site: {LINK_SITE}\n"
    f"📸 Instagram: {LINK_INSTAGRAM}"
)
# ===== Listas de serviços e peças ============================================
SERVICOS_DISPONIVEIS = [
    "Revisão completa",
    "Troca de óleo",
    "Freios e suspensão",
    "Correia dentada",
    "Motor e embreagem",
    "Elétrica e injeção",
    "Outros serviços"
]

PECAS_DISPONIVEIS = [
    "Filtros (óleo, ar, combustível)",
    "Pastilhas de freio",
    "Amortecedores",
    "Correia dentada",
    "Velas e cabos",
    "Bateria e elétrica",
    "Outras peças"
]

# ===== MENU: SERVIÇOS =========================================================
def _menu_servicos(contato: str):
    texto = (
        "🧰 *Serviços disponíveis:*\n\n"
        "Selecione o tipo de serviço que deseja realizar 👇"
    )
    botoes = [{"id": f"serv_{i}", "title": nome} for i, nome in enumerate(SERVICOS_DISPONIVEIS[:3])]
    botoes.append({"id": "serv_mais", "title": "Mais opções"})
    _send_buttons(contato, texto, botoes)

# ===== MENU: PEÇAS ============================================================
def _menu_pecas(contato: str):
    texto = (
        "🔩 *Peças disponíveis:*\n\n"
        "Selecione o tipo de peça que deseja 👇"
    )
    botoes = [{"id": f"peca_{i}", "title": nome} for i, nome in enumerate(PECAS_DISPONIVEIS[:3])]
    botoes.append({"id": "peca_mais", "title": "Mais opções"})
    _send_buttons(contato, texto, botoes)

# ===== EXPANSÃO “MAIS OPÇÕES” =================================================
def _menu_servicos_mais(contato: str):
    botoes = [{"id": f"serv_{i+3}", "title": n} for i, n in enumerate(SERVICOS_DISPONIVEIS[3:6])]
    botoes.append({"id": "op_voltar", "title": "Voltar"})
    _send_buttons(contato, "Outros serviços 👇", botoes)

def _menu_pecas_mais(contato: str):
    botoes = [{"id": f"peca_{i+3}", "title": n} for i, n in enumerate(PECAS_DISPONIVEIS[3:6])]
    botoes.append({"id": "op_voltar", "title": "Voltar"})
    _send_buttons(contato, "Outras peças 👇", botoes)

# ===== PROCESSA ESCOLHA DE SERVIÇO / PEÇA ====================================
def _processar_escolha(contato: str, resposta_id: str, nome_cliente: str = ""):
    if resposta_id.startswith("serv_"):
        indice = int(resposta_id.split("_")[1])
        descricao = SERVICOS_DISPONIVEIS[indice]
        _solicitar_dados(contato, "servico", nome_cliente, descricao)
        return

    if resposta_id.startswith("peca_"):
        indice = int(resposta_id.split("_")[1])
        descricao = PECAS_DISPONIVEIS[indice]
        _solicitar_dados(contato, "peca", nome_cliente, descricao)
        return

# ===== PEDE DADOS DO CLIENTE ==================================================
def _solicitar_dados(contato: str, tipo: str, nome_cliente: str, descricao: str):
    if tipo == "servico":
        msg = (
            f"✅ *Serviço selecionado:* {descricao}\n\n"
            "Informe:\n• Placa\n• Modelo\n• Novo ou Pós-venda?"
        )
    else:
        msg = (
            f"✅ *Peça selecionada:* {descricao}\n\n"
            "Informe:\n• Placa\n• Modelo\n• Novo ou Pós-venda?"
        )
    _send_text(contato, msg)
# ===== ROTEADOR GERAL =========================================================
def _rotear_escolha(contato: str, resposta_id: str, nome_cliente: str = ""):

    # ======================
    # BOTÕES PRINCIPAIS
    # ======================
    if resposta_id == "op_servicos":
        return _menu_servicos(contato)

    if resposta_id == "op_pecas":
        return _menu_pecas(contato)

    if resposta_id == "op_mais":
        return _send_buttons(contato, "Escolha uma opção 👇", BTN_MAIS)

    # ======================
    # EXPANSÃO
    # ======================
    if resposta_id == "serv_mais":
        return _menu_servicos_mais(contato)

    if resposta_id == "peca_mais":
        return _menu_pecas_mais(contato)

    # ======================
    # ESCOLHA DIRETA
    # ======================
    if resposta_id.startswith("serv_") or resposta_id.startswith("peca_"):
        return _processar_escolha(contato, resposta_id, nome_cliente)

    # ======================
    # PÓS-VENDA
    # ======================
    if resposta_id == "pos_garantia":
        return _send_text(contato, "🛠️ Para garantia envie: Placa, modelo e problema.")

    if resposta_id == "pos_agendar":
        return _send_text(contato, "📅 Para agendar envie: Placa, modelo e tipo de serviço.")

    # ======================
    # ENDEREÇOS
    # ======================
    if resposta_id == "op_endereco":
        return _send_buttons(contato, MSG_ENDERECOS, BTN_ENDERECOS)

    if resposta_id in ["end_loja", "end_oficina"]:
        return _send_text(contato, MSG_ENDERECOS)

    # ======================
    # VOLTAR
    # ======================
    if resposta_id == "op_voltar":
        return _send_buttons(contato, msg_boas_vindas(nome_cliente), BTN_ROOT)

    # ======================
    # NÃO RECONHECIDO
    # ======================
    return _send_text(contato, "Não reconheci. Envie *oi* para começar.")

# ===== FUNÇÃO PRINCIPAL DO CHATBOT ===========================================
def responder_evento_mensagem(entry: Dict[str, Any]):
    try:
        value = entry["changes"][0]["value"]
        messages = value.get("messages", [])
        contacts = value.get("contacts", [])

        if not messages:
            return

        msg = messages[0]
        contato = contacts[0].get("wa_id")
        nome_wa = contacts[0].get("profile", {}).get("name")

        tipo = msg.get("type")
        texto, resposta_id = "", None

        if tipo == "text":
            texto = msg["text"]["body"].lower().strip()

        elif tipo == "interactive":
            inter = msg["interactive"]
            if inter["type"] == "button_reply":
                resposta_id = inter["button_reply"]["id"]
                texto = inter["button_reply"]["title"].lower().strip()

        print(f"[WA] Msg de {contato}: {texto} ({resposta_id})")

        # Saudações
        if any(p in texto for p in ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite"]):
            return _send_buttons(contato, msg_boas_vindas(nome_wa), BTN_ROOT)

        # Roteamento por botão
        if resposta_id:
            return _rotear_escolha(contato, resposta_id, nome_wa)

        # Fallback
        return _send_text(contato, "Envie *oi* para iniciar.")
    except Exception as e:
        print("[ERRO responder_evento_mensagem]", e)
        _send_text(contato, "⚠️ Erro temporário. Tente novamente.")


print("✅ responder_oficina.py carregado com sucesso — Sullato Oficina")
