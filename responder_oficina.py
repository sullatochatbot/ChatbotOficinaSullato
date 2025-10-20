# responder_oficina.py — Sullato Oficina e Pós-Venda
# ================================================================
# Estrutura baseada no chatbot da Clínica Luma, adaptada para o setor automotivo.
# Termos: Paciente → Cliente | Consulta → Serviço | Exame → Peça
# ================================================================

import os, re, json, requests, time
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any, List

# ===== Variáveis de ambiente ====================================
WA_ACCESS_TOKEN    = os.getenv("WA_ACCESS_TOKEN", "").strip() or os.getenv("ACCESS_TOKEN", "").strip()
WA_PHONE_NUMBER_ID = os.getenv("WA_PHONE_NUMBER_ID", "").strip() or os.getenv("PHONE_NUMBER_ID", "").strip()

SHEETS_URL         = os.getenv("SHEETS_URL", "").strip()
SHEETS_SECRET      = os.getenv("SHEETS_SECRET", "").strip()

NOME_EMPRESA   = os.getenv("NOME_EMPRESA", "Sullato Oficina e Pós-Venda").strip()
LINK_SITE      = os.getenv("LINK_SITE", "https://www.sullato.com.br").strip()
LINK_INSTAGRAM = os.getenv("LINK_INSTAGRAM", "https://www.instagram.com/sullatomicrosevans").strip()

GRAPH_URL = f"https://graph.facebook.com/v20.0/{WA_PHONE_NUMBER_ID}/messages" if WA_PHONE_NUMBER_ID else ""
HEADERS   = {"Authorization": f"Bearer {WA_ACCESS_TOKEN}", "Content-Type": "application/json"}

# Evita duplicatas e repetições de salvamento
_ULTIMAS_CHAVES = set()
SESSION_TTL_MIN = 10  # minutos de inatividade para resetar sessão

# ===== Persistência via WebApp ==================================
def _post_webapp(payload: dict) -> dict:
    """
    Envia o registro ao WebApp Google Sheets (rota 'chatbot').
    """
    if not (SHEETS_URL and SHEETS_SECRET):
        print("[SHEETS] ⚠️ Configuração ausente (SHEETS_URL/SHEETS_SECRET).")
        return {"ok": False, "erro": "config ausente"}

    data = {"secret": SHEETS_SECRET, "rota": "chatbot"}
    data.update(payload or {})

    if not data.get("message_id"):
        data["message_id"] = f"auto-{int(datetime.now().timestamp()*1000)}"

    data["contato"] = data.get("contato") or data.get("fone") or data.get("telefone") or ""
    data["whatsapp_nome"] = (
        data.get("whatsapp_nome") or
        data.get("nome_whatsapp") or
        data.get("nome_cap") or
        data.get("nome") or ""
    )

    # Campos de origem P / Q / R
    data["origem_cliente"] = data.get("origem_cliente") or data.get("origem") or ""
    data["panfleto_codigo"] = data.get("panfleto_codigo") or data.get("panfleto_codigo_raw") or ""
    data["origem_outro_texto"] = data.get("origem_outro_texto") or data.get("origem_texto") or ""

    # Compatibilidade
    data["origem"] = data["origem_cliente"]
    data["origem_panfleto_codigo"] = data["panfleto_codigo"]
    data["origem_texto"] = data["origem_outro_texto"]

    dbg = {k: data.get(k) for k in [
        "message_id","contato","whatsapp_nome",
        "servico","peca","forma","tipo",
        "origem_cliente","panfleto_codigo","origem_outro_texto"
    ]}
    print("[SEND→Sheets] URL:", SHEETS_URL)
    print("[SEND→Sheets] Campos:", json.dumps(dbg, ensure_ascii=False))

    try:
        r = requests.post(SHEETS_URL, json=data, timeout=12)
        r.raise_for_status()
        j = r.json()
        print("[SHEETS] ✅ Resp:", j)
        return j
    except Exception as e:
        print("[SHEETS] ❌ Erro:", e)
        return {"ok": False, "erro": str(e)}

# ===== Conversão de dados para planilha =========================
def _map_to_captacao(d: dict) -> dict:
    """
    Converte dados do fluxo para o formato de gravação no Sheets.
    """
    out = dict(d)

    out["message_id"]    = d.get("message_id") or out.get("message_id")
    out["contato"]       = (d.get("contato") or "").strip()
    out["whatsapp_nome"] = (d.get("whatsapp_nome") or "").strip()

    # Tipo de atendimento
    out["forma"] = d.get("forma") or d.get("tipo") or ""
    if out["forma"].lower() in ["novo", "nova"]:
        out["forma"] = "Novo"
    elif out["forma"].lower() in ["pós", "pos", "pós-venda", "pos-venda"]:
        out["forma"] = "Pós-venda"

    # Identificação do cliente
    def only_digits(s): return "".join(ch for ch in (s or "") if ch.isdigit())

    out["cliente_nome"] = (d.get("nome") or "").strip()
    out["cliente_cpf"]  = only_digits(d.get("cpf") or "")
    out["placa"]        = (d.get("placa") or d.get("nasc") or "").strip()   # nasc → placa
    out["modelo_veiculo"] = (d.get("modelo_veiculo") or d.get("responsavel_nome") or "").strip()
    out["servico"]      = (d.get("servico") or d.get("especialidade") or "").strip()
    out["peca"]         = (d.get("peca") or d.get("exame") or "").strip()

    out["cep"]          = (d.get("cep") or "").strip()
    out["numero"]       = (d.get("numero") or "").strip()
    out["complemento"]  = (d.get("complemento") or "").strip()
    out["endereco"]     = (d.get("endereco") or "").strip()

    out["origem_cliente"]      = (d.get("origem_cliente") or d.get("origem") or "").strip()
    out["panfleto_codigo"]     = (d.get("panfleto_codigo") or d.get("panfleto_codigo_raw") or "").strip()
    out["origem_outro_texto"]  = (d.get("origem_outro_texto") or d.get("origem_texto") or "").strip()

    # Compatibilidade retro
    out["origem"] = out["origem_cliente"]
    out["origem_panfleto_codigo"] = out["panfleto_codigo"]
    out["origem_texto"] = out["origem_outro_texto"]

    out.pop("_origem_done", None)
    out.pop("_compl_decidido", None)
    return out

def _add_solicitacao(ss, d):
    chave = f"{(d.get('contato') or '').strip()}|" \
            f"{(d.get('servico') or d.get('peca') or '').strip()}|" \
            f"{(d.get('forma') or '').strip()}|" \
            f"{datetime.now().strftime('%Y-%m-%d %H:%M')}"
    if chave in _ULTIMAS_CHAVES:
        print("[SHEETS] 🔁 Ignorado duplicado:", chave)
        return
    _ULTIMAS_CHAVES.add(chave)

    payload = _map_to_captacao(d)
    base = (d.get("wa_id") or d.get("contato") or "").strip()
    tipo = (d.get("tipo") or ("peca" if d.get("peca") else "servico")).lower()
    payload["dedupe_key"] = f"{base}-{tipo}-{int(time.time())}"

    _post_webapp(payload)

# ===== Utilitários ============================================================
def _hora_sp(): return datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%Y-%m-%d %H:%M:%S")

def _send_text(to: str, text: str):
    """Envio de texto padrão via WhatsApp API"""
    if not (WA_ACCESS_TOKEN and WA_PHONE_NUMBER_ID):
        print("[MOCK→WA TEXT]", to, text)
        return
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": text[:4096]}
    }
    requests.post(GRAPH_URL, headers=HEADERS, json=payload, timeout=30)

def _send_buttons(to: str, body: str, buttons: List[Dict[str, str]]):
    btns = buttons[:3]
    if not (WA_ACCESS_TOKEN and WA_PHONE_NUMBER_ID):
        print("[MOCK→WA BTNS]", to, body, btns)
        return
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body[:1024]},
            "action": {"buttons": [{"type": "reply", "reply": b} for b in btns]}
        }
    }
    requests.post(GRAPH_URL, headers=HEADERS, json=payload, timeout=30)
# ================================================================
# PARTE 2 — Estrutura de menus e respostas do chatbot
# ================================================================

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

# ===== Mensagens fixas ========================================================
MSG_ENDERECOS = (
    "🏠 *Endereços Sullato*\n\n"
    "📍 *Loja Principal*\n"
    "Av. São Miguel, 4049/4084 – CEP 03871-000\n"
    "☎️ (11) 94054-5704\n\n"
    "📍 *Oficina e Peças*\n"
    "Av. São Miguel, 7900 – CEP 08070-001\n"
    "☎️ (11) 94054-5704\n\n"
    f"🌐 Site: {LINK_SITE}\n"
    f"📸 Instagram: {LINK_INSTAGRAM}\n\n"
    "_Em caso de dúvidas, fale com um dos nossos consultores._"
)

MSG_GARANTIA = (
    "🛠️ *Pós-venda — Garantia*\n\n"
    "Para abrir um chamado de garantia, por favor informe:\n"
    "• Placa do veículo\n"
    "• Modelo\n"
    "• Descrição do problema\n\n"
    "Nosso time retornará para acompanhar o processo."
)

MSG_AGENDAR = (
    "📅 *Agendamento de Serviço*\n\n"
    "Por favor, informe:\n"
    "• Placa do veículo\n"
    "• Modelo\n"
    "• Tipo de serviço desejado (ex: revisão, troca de óleo, etc)\n\n"
    "Assim que recebermos, entraremos em contato para confirmar o horário."
)

# ===== Funções principais de fluxo ===========================================
def responder_evento_mensagem(entry: Dict[str, Any]):
    """
    Ponto central que recebe eventos do webhook e decide a resposta.
    """
    try:
        value = entry["changes"][0]["value"]
        messages = value.get("messages", [])
        contacts = value.get("contacts", [])
        if not messages:
            return

        msg = messages[0]
        contato = contacts[0].get("wa_id") if contacts else None
        nome_wa = contacts[0].get("profile", {}).get("name") if contacts else None
        tipo = msg.get("type")
        texto = ""
        resposta_id = None

        if tipo == "text":
            texto = msg.get("text", {}).get("body", "").strip().lower()
        elif tipo == "interactive":
            inter = msg.get("interactive", {})
            if inter.get("type") == "button_reply":
                resposta_id = inter["button_reply"]["id"]
                texto = inter["button_reply"]["title"].strip().lower()
            elif inter.get("type") == "list_reply":
                resposta_id = inter["list_reply"]["id"]
                texto = inter["list_reply"]["title"].strip().lower()

        print(f"[WA] 📩 Mensagem recebida de {contato}: {texto}")

        if not texto:
            return

        # ===== SAUDAÇÕES INICIAIS ===========================================
        if any(p in texto for p in ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite"]):
            _send_buttons(contato, msg_boas_vindas(nome_wa), BTN_ROOT)
            return

        # ===== MENU PRINCIPAL ==============================================
        if resposta_id in ["op_servicos"]:
            _menu_servicos(contato)
            return

        if resposta_id in ["op_pecas"]:
            _menu_pecas(contato)
            return

        if resposta_id in ["op_mais"]:
            _send_buttons(contato, "Selecione uma das opções abaixo 👇", BTN_MAIS)
            return

        # ===== MENU MAIS OPÇÕES ============================================
        if resposta_id in ["op_posvenda"]:
            _send_buttons(contato, "O que deseja acessar no Pós-venda?", BTN_POSVENDA)
            return

        if resposta_id in ["op_endereco"]:
            _send_buttons(contato, MSG_ENDERECOS, BTN_ENDERECOS)
            return

        # ===== ENDEREÇOS ===================================================
        if resposta_id in ["end_loja", "end_oficina"]:
            _send_text(contato, MSG_ENDERECOS)
            return

        # ===== PÓS-VENDA ===================================================
        if resposta_id in ["pos_garantia"]:
            _send_text(contato, MSG_GARANTIA)
            return

        if resposta_id in ["pos_agendar"]:
            _send_text(contato, MSG_AGENDAR)
            return

        # ===== VOLTAR ======================================================
        if resposta_id in ["op_voltar"]:
            _send_buttons(contato, msg_boas_vindas(nome_wa), BTN_ROOT)
            return

        # ===== NÃO RECONHECIDO ============================================
        _send_text(
            contato,
            "Não entendi bem 🤔\nPor favor, escolha uma das opções do menu ou envie 'oi' para começar novamente."
        )

    except Exception as e:
        print("[ERRO responder_evento_mensagem]", e)
# ================================================================
# PARTE 3 — Fluxos de atendimento (Serviços e Peças)
# ================================================================

# ===== Serviços disponíveis =====================================
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

# ===== MENU: SERVIÇOS ==========================================
def _menu_servicos(contato: str):
    texto = (
        "🧰 *Serviços disponíveis:*\n\n"
        "Selecione o tipo de serviço que deseja realizar 👇"
    )
    botoes = [{"id": f"serv_{i}", "title": nome} for i, nome in enumerate(SERVICOS_DISPONIVEIS[:3])]
    botoes.append({"id": "serv_mais", "title": "Mais opções"})
    _send_buttons(contato, texto, botoes)

# ===== MENU: PEÇAS =============================================
def _menu_pecas(contato: str):
    texto = (
        "🔩 *Peças disponíveis:*\n\n"
        "Selecione o tipo de peça que deseja 👇"
    )
    botoes = [{"id": f"peca_{i}", "title": nome} for i, nome in enumerate(PECAS_DISPONIVEIS[:3])]
    botoes.append({"id": "peca_mais", "title": "Mais opções"})
    _send_buttons(contato, texto, botoes)

# ===== EXPANDE “MAIS OPÇÕES” ===================================
def _menu_servicos_mais(contato: str):
    botoes = [{"id": f"serv_{i}", "title": nome} for i, nome in enumerate(SERVICOS_DISPONIVEIS[3:6])]
    botoes.append({"id": "op_voltar", "title": "Voltar"})
    _send_buttons(contato, "Outros serviços disponíveis 👇", botoes)

def _menu_pecas_mais(contato: str):
    botoes = [{"id": f"peca_{i}", "title": nome} for i, nome in enumerate(PECAS_DISPONIVEIS[3:6])]
    botoes.append({"id": "op_voltar", "title": "Voltar"})
    _send_buttons(contato, "Outras peças disponíveis 👇", botoes)

# ===== Capta informações de serviço / peça ======================
def _processar_escolha(contato: str, resposta_id: str, nome_cliente: str = ""):
    """
    Interpreta a escolha feita e pede dados complementares.
    """
    if resposta_id.startswith("serv_"):
        indice = int(resposta_id.split("_")[1])
        servico = SERVICOS_DISPONIVEIS[indice] if indice < len(SERVICOS_DISPONIVEIS) else "Outro serviço"
        _solicitar_dados(contato, tipo="servico", nome_cliente=nome_cliente, descricao=servico)
        return

    if resposta_id.startswith("peca_"):
        indice = int(resposta_id.split("_")[1])
        peca = PECAS_DISPONIVEIS[indice] if indice < len(PECAS_DISPONIVEIS) else "Outra peça"
        _solicitar_dados(contato, tipo="peca", nome_cliente=nome_cliente, descricao=peca)
        return

# ===== Pergunta dados complementares =============================
def _solicitar_dados(contato: str, tipo: str, nome_cliente: str, descricao: str):
    """
    Pede ao cliente os dados necessários para agendamento ou orçamento.
    """
    if tipo == "servico":
        msg = (
            f"✅ *Serviço selecionado:* {descricao}\n\n"
            "Por favor, informe:\n"
            "• Placa do veículo\n"
            "• Modelo do veículo\n"
            "• Deseja realizar o serviço como *Novo* ou *Pós-venda*?"
        )
    else:
        msg = (
            f"✅ *Peça selecionada:* {descricao}\n\n"
            "Por favor, informe:\n"
            "• Placa do veículo\n"
            "• Modelo do veículo\n"
            "• Deseja solicitar como *Novo* ou *Pós-venda*?"
        )
    _send_text(contato, msg)

    # Salva tentativa no log (parcial)
    dados = {
        "contato": contato,
        "whatsapp_nome": nome_cliente,
        "tipo": tipo,
        "servico" if tipo == "servico" else "peca": descricao,
        "forma": "",
    }
    _add_solicitacao("Parcial", dados)

# ===== Conclusão do atendimento =================================
def _finaliza_solicitacao(contato: str, tipo: str, descricao: str):
    """
    Finaliza o fluxo e envia confirmação ao cliente.
    """
    if tipo == "servico":
        msg = (
            f"✅ Solicitação registrada!\n\n"
            f"Serviço: *{descricao}*\n"
            "Nosso time entrará em contato para confirmar agendamento e valores.\n\n"
            "Agradecemos a preferência pela Sullato Oficina e Pós-venda! 🚗🔧"
        )
    else:
        msg = (
            f"✅ Solicitação registrada!\n\n"
            f"Peça: *{descricao}*\n"
            "Em breve entraremos em contato com disponibilidade e valores.\n\n"
            "Agradecemos pela confiança na Sullato Oficina e Pós-venda! 🧰"
        )
    _send_text(contato, msg)
# ================================================================
# PARTE 4 — Roteamento de escolhas e fallback
# ================================================================

def _rotear_escolha(contato: str, resposta_id: str, nome_cliente: str = ""):
    """
    Direciona o fluxo conforme o ID da resposta (serviço, peça, mais opções etc.)
    """
    try:
        # Expande menus “mais opções”
        if resposta_id == "serv_mais":
            _menu_servicos_mais(contato)
            return
        if resposta_id == "peca_mais":
            _menu_pecas_mais(contato)
            return

        # Identifica escolha direta de serviço ou peça
        if resposta_id.startswith("serv_") or resposta_id.startswith("peca_"):
            _processar_escolha(contato, resposta_id, nome_cliente)
            return

        # Pós-venda
        if resposta_id in ["pos_garantia", "pos_agendar"]:
            _send_text(contato, "✅ Entendido! Nosso time do pós-venda entrará em contato em instantes.")
            return

        # Endereço / voltar
        if resposta_id in ["end_loja", "end_oficina"]:
            _send_text(contato, MSG_ENDERECOS)
            return

        if resposta_id == "op_voltar":
            _send_buttons(contato, msg_boas_vindas(nome_cliente), BTN_ROOT)
            return

        # Caso não reconhecido
        _send_text(contato, "Desculpe, não consegui entender. Digite 'oi' para recomeçar o atendimento.")
    except Exception as e:
        print("[ERRO _rotear_escolha]", e)
        _send_text(contato, "⚠️ Ocorreu um erro momentâneo. Tente novamente em instantes.")

# ================================================================
# Função principal — entrada de mensagens
# ================================================================
def responder_evento_mensagem(entry: Dict[str, Any]):
    """
    Ponto central chamado pelo webhook.py
    """
    try:
        value = entry["changes"][0]["value"]
        messages = value.get("messages", [])
        contacts = value.get("contacts", [])
        if not messages:
            return

        msg = messages[0]
        contato = contacts[0].get("wa_id") if contacts else None
        nome_wa = contacts[0].get("profile", {}).get("name") if contacts else None
        tipo = msg.get("type")
        texto = ""
        resposta_id = None

        if tipo == "text":
            texto = msg.get("text", {}).get("body", "").strip().lower()
        elif tipo == "interactive":
            inter = msg.get("interactive", {})
            if inter.get("type") == "button_reply":
                resposta_id = inter["button_reply"]["id"]
                texto = inter["button_reply"]["title"].strip().lower()
            elif inter.get("type") == "list_reply":
                resposta_id = inter["list_reply"]["id"]
                texto = inter["list_reply"]["title"].strip().lower()

        print(f"[WA] 📩 Mensagem recebida de {contato}: {texto} ({resposta_id})")

        # Saudações básicas
        if any(p in texto for p in ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite"]):
            _send_buttons(contato, msg_boas_vindas(nome_wa), BTN_ROOT)
            return

        # Direciona interações por ID
        if resposta_id:
            _rotear_escolha(contato, resposta_id, nome_wa)
            return

        # Detecta palavras-chave fora do menu
        if any(p in texto for p in ["serviço", "revisão", "óleo", "freio", "suspensão"]):
            _menu_servicos(contato)
            return
        if any(p in texto for p in ["peça", "peças", "filtro", "pastilha", "amortecedor"]):
            _menu_pecas(contato)
            return
        if any(p in texto for p in ["endereço", "local", "oficina", "loja"]):
            _send_text(contato, MSG_ENDERECOS)
            return
        if any(p in texto for p in ["garantia", "pós", "pos", "agendar", "agendamento"]):
            _send_text(contato, MSG_AGENDAR)
            return

        # Fallback geral (mensagem fora de contexto)
        _send_text(
            contato,
            "Não entendi bem 🤔\nEnvie *oi* para começar, ou selecione uma opção do menu."
        )
    except Exception as e:
        print("[ERRO responder_evento_mensagem - final]", e)
        _send_text(
            contato,
            "⚠️ Ocorreu um erro interno. Tente novamente em alguns segundos."
        )

# ================================================================
# Fim do arquivo
# ================================================================
print("✅ responder_oficina.py carregado com sucesso — Sullato Oficina e Pós-Venda")
