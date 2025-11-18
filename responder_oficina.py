# responder_oficina.py — Sullato Oficina e Pós-Venda
# ================================================================
# Estrutura baseada no chatbot da Clínica Luma, adaptada para o setor automotivo.
# ================================================================

import os, re, json, requests, time
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any, List

# ===== Estado de atendimento por contato =========================
ESTADOS_ATENDIMENTO: Dict[str, Dict[str, Any]] = {}

# ===== Variáveis de ambiente ====================================
WA_ACCESS_TOKEN    = os.getenv("WA_ACCESS_TOKEN", "").strip() or os.getenv("ACCESS_TOKEN", "").strip()
WA_PHONE_NUMBER_ID = os.getenv("WA_PHONE_NUMBER_ID", "").strip() or os.getenv("PHONE_NUMBER_ID", "").strip()

NOME_EMPRESA   = os.getenv("NOME_EMPRESA", "Sullato Oficina e Peças").strip()
LINK_SITE      = os.getenv("LINK_SITE", "https://www.sullato.br").strip()
LINK_INSTAGRAM_MICROS   = os.getenv("LINK_INSTAGRAM_MICROS", "https://www.instagram.com/sullatomicrosevans").strip()
LINK_INSTAGRAM_VEICULOS = os.getenv("LINK_INSTAGRAM_VEICULOS", "https://www.instagram.com/sullato.veiculos").strip()

GRAPH_URL = f"https://graph.facebook.com/v20.0/{WA_PHONE_NUMBER_ID}/messages" if WA_PHONE_NUMBER_ID else ""
HEADERS   = {"Authorization": f"Bearer {WA_ACCESS_TOKEN}", "Content-Type": "application/json"}

# ===== Funções utilitárias ====================================================
def _hora_sp():
    return datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%Y-%m-%d %H:%M:%S")

def _send_text(to: str, text: str):
    """Envia mensagens de texto no WhatsApp."""
    if not GRAPH_URL or not WA_ACCESS_TOKEN:
        print("[WARN] GRAPH_URL ou WA_ACCESS_TOKEN não configurados.")
        return
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": text[:4096]}
    }
    try:
        requests.post(GRAPH_URL, headers=HEADERS, json=payload, timeout=30)
    except Exception as e:
        print("[ERRO _send_text]", e)

def _send_buttons(to: str, body: str, buttons: List[Dict[str, str]]):
    """Envia botões interativos."""
    if not GRAPH_URL or not WA_ACCESS_TOKEN:
        print("[WARN] GRAPH_URL ou WA_ACCESS_TOKEN não configurados.")
        return
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
    try:
        requests.post(GRAPH_URL, headers=HEADERS, json=payload, timeout=30)
    except Exception as e:
        print("[ERRO _send_buttons]", e)

# ===== Boas-vindas ============================================================
def msg_boas_vindas(nome=None):
    nome_fmt = nome or ""
    saudacao = f"Olá {nome_fmt}," if nome_fmt else "Olá,"
    return (
        f"{saudacao} 👋\n"
        f"Bem-vindo(a) à *{NOME_EMPRESA}*! 🚗🔧\n\n"
        "Aqui você agenda serviços, adquire peças e acessórios, fala com o pós-venda e muito mais.\n\n"
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
    {"id": "end_loja", "title": "📍 Lojas"},
    {"id": "end_oficina", "title": "🔧 Oficina e Peças"},
    {"id": "op_voltar", "title": "Voltar"},
]

BTN_POSVENDA = [
    {"id": "pos_garantia", "title": "Garantia"},
    {"id": "pos_agendar", "title": "Agendar Serviço"},
    {"id": "op_voltar", "title": "Voltar"},
]

# Botões de tipo de veículo (única etapa com botões no fluxo de dados)
BTN_TIPO_VEICULO = [
    {"id": "tipo_passeio",    "title": "Passeio"},
    {"id": "tipo_utilitario", "title": "Utilitário"},
]

MSG_ENDERECOS = (
    "🏠 *Endereços Sullato*\n\n"

    "📍 *Sullato Micros e Vans*\n"
    "Av. São Miguel, 7900 – CEP 08070-001\n"
    "☎️ (11) 2030-5081 / (11) 94054-5704\n"
    "👉 https://wa.me/551120305081\n"
    "👉 https://wa.me/5511940545704\n\n"

    "📍 *Sullato Veículos*\n"
    "Av. São Miguel, 4049/4084 – CEP 03871-000\n"
    "☎️ (11) 2542-3332 / (11) 94054-5704\n"
    "👉 https://wa.me/551125423332\n"
    "👉 https://wa.me/5511940545704\n\n"

    "📍 *Sullato Oficina e Peças*\n"
    "Av. Amador Bueno da Veiga, 4222 – CEP 03652-000\n"
    "☎️ (11) 2542-3333\n"
    "👉 https://wa.me/551125423333\n\n"

    f"🌐 *Site:* {LINK_SITE}\n\n"

    f"📸 *Instagram Micros e Vans:* {LINK_INSTAGRAM_MICROS}\n"
    f"📸 *Instagram Veículos:* {LINK_INSTAGRAM_VEICULOS}\n"
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
        _iniciar_fluxo_dados(contato, "servico", nome_cliente, descricao)
        return

    if resposta_id.startswith("peca_"):
        indice = int(resposta_id.split("_")[1])
        descricao = PECAS_DISPONIVEIS[indice]
        _iniciar_fluxo_dados(contato, "peca", nome_cliente, descricao)
        return

# ===== INICIA O FLUXO DE PERGUNTAS ===========================================
def _iniciar_fluxo_dados(contato: str, tipo: str, nome_cliente: str, descricao: str):
    """
    Começa o fluxo pergunta-a-pergunta.
    Apenas o tipo de veículo será em botão (Passeio / Utilitário).
    """
    cabecalho = (
        f"✅ *Serviço selecionado:* {descricao}"
        if tipo == "servico"
        else f"✅ *Peça selecionada:* {descricao}"
    )

    ESTADOS_ATENDIMENTO[contato] = {
        "etapa": "tipo_veiculo",
        "tipo": tipo,
        "descricao": descricao,
        "nome": nome_cliente or "",
        "dados": {}
    }

    texto = (
        f"{cabecalho}\n\n"
        "Para começar, escolha o *tipo de veículo* 👇"
    )
    _send_buttons(contato, texto, BTN_TIPO_VEICULO)

# ===== CONTINUA O FLUXO DE PERGUNTAS =========================================
def _continuar_fluxo_dados(contato: str, texto: str):
    estado = ESTADOS_ATENDIMENTO.get(contato)
    if not estado:
        return _send_text(contato, "Não reconheci. Envie *oi* para começar.")

    dados = estado.setdefault("dados", {})
    etapa = estado.get("etapa")

    # 1) Placa
    if etapa == "placa":
        dados["placa"] = texto.strip()
        estado["etapa"] = "ano_modelo"
        return _send_text(contato, "Agora informe o *ano/modelo* do veículo (ex.: 2018/2019):")

    # 2) Ano/Modelo
    if etapa == "ano_modelo":
        dados["ano_modelo"] = texto.strip()
        estado["etapa"] = "km"
        return _send_text(contato, "Informe a *quilometragem aproximada* (ex.: 85.000 km):")

    # 3) Quilometragem
    if etapa == "km":
        dados["km"] = texto.strip()
        estado["etapa"] = "data"
        return _send_text(
            contato,
            "Qual a *data desejada* para levar o veículo?\n"
            "(Ex.: 25/11 ou 'próxima terça de manhã')"
        )

    # 4) Data desejada
    if etapa == "data":
        dados["data_desejada"] = texto.strip()
        estado["etapa"] = "nome_responsavel"
        return _send_text(contato, "Informe o *nome completo do responsável* pelo veículo:")

    # 5) Nome responsável
    if etapa == "nome_responsavel":
        dados["nome_responsavel"] = texto.strip()
        estado["etapa"] = "cpf"
        return _send_text(contato, "Agora informe o *CPF* do responsável:")

    # 6) CPF
    if etapa == "cpf":
        dados["cpf"] = texto.strip()
        estado["etapa"] = "nascimento"
        return _send_text(contato, "Informe a *data de nascimento* do responsável (ex.: 10/03/1985):")

    # 7) Data de nascimento
    if etapa == "nascimento":
        dados["nascimento"] = texto.strip()
        estado["etapa"] = "cep"
        return _send_text(contato, "Informe o *CEP*:")

    # 8) CEP
    if etapa == "cep":
        dados["cep"] = texto.strip()
        estado["etapa"] = "endereco"
        return _send_text(contato, "Informe o *endereço* (rua/avenida):")

    # 9) Endereço
    if etapa == "endereco":
        dados["endereco"] = texto.strip()
        estado["etapa"] = "numero"
        return _send_text(contato, "Informe o *número*:")

    # 10) Número
    if etapa == "numero":
        dados["numero"] = texto.strip()
        estado["etapa"] = "complemento"
        return _send_text(contato, "Complemento (se não tiver, responda 'nenhum'):")

    # 11) Complemento
    if etapa == "complemento":
        dados["complemento"] = texto.strip()
        estado["etapa"] = "origem"
        return _send_text(
            contato,
            "De onde nos conheceu?\n"
            "Ex.: Instagram, Google, Indicação, Panfleto, Outro..."
        )

    # 12) Origem
    if etapa == "origem":
        dados["origem_cliente"] = texto.strip()
        estado["etapa"] = "panfleto"
        return _send_text(
            contato,
            "Se veio por *panfleto*, informe o código (ex.: P-1234).\n"
            "Se não for o caso, responda 'não'."
        )

    # 13) Código do panfleto
    if etapa == "panfleto":
        dados["panfleto_codigo"] = texto.strip()
        estado["etapa"] = "sugestao"
        return _send_text(
            contato,
            "Por fim, deixe alguma *sugestão ou observação* sobre o serviço "
            "(se não tiver, pode responder 'nenhuma')."
        )

    # 14) Sugestão / observação
    if etapa == "sugestao":
        dados["sugestao_servico"] = texto.strip()

        # Aqui depois podemos plugar a gravação na planilha do Google Sheets
        # Exemplo:
        # salvar_dados_oficina(contato, estado)

        ESTADOS_ATENDIMENTO.pop(contato, None)
        return _send_text(
            contato,
            "Perfeito, obrigado! 🙏\n\n"
            "Recebemos todas as informações. Nossa equipe da *Sullato Oficina e Pós-Venda* "
            "vai dar sequência no mesmo número deste WhatsApp."
        )

    # Se chegar aqui, algo saiu do fluxo esperado
    ESTADOS_ATENDIMENTO.pop(contato, None)
    return _send_text(contato, "Não entendi muito bem. Envie *oi* para recomeçar, por favor.")
# ===== ROTEADOR GERAL =========================================================
def _rotear_escolha(contato: str, resposta_id: str, nome_cliente: str = ""):

    # BOTÕES PRINCIPAIS
    if resposta_id == "op_servicos":
        return _menu_servicos(contato)

    if resposta_id == "op_pecas":
        return _menu_pecas(contato)

    if resposta_id == "op_mais":
        return _send_buttons(contato, "Escolha uma opção 👇", BTN_MAIS)

    # TIPO DE VEÍCULO (Passeio / Utilitário)
    if resposta_id in ("tipo_passeio", "tipo_utilitario"):
        estado = ESTADOS_ATENDIMENTO.get(contato)
        if not estado:
            return _send_text(contato, "Vamos começar de novo. Envie *oi* para iniciar, por favor.")

        tipo_label = "Passeio" if resposta_id == "tipo_passeio" else "Utilitário"
        dados = estado.setdefault("dados", {})
        dados["tipo_veiculo"] = tipo_label

        estado["etapa"] = "placa"
        return _send_text(contato, "Perfeito! Agora informe a *placa* do veículo:")

    # EXPANSÃO LISTAS
    if resposta_id == "serv_mais":
        return _menu_servicos_mais(contato)

    if resposta_id == "peca_mais":
        return _menu_pecas_mais(contato)

    # ESCOLHA DE SERVIÇO / PEÇA
    if resposta_id.startswith("serv_") or resposta_id.startswith("peca_"):
        return _processar_escolha(contato, resposta_id, nome_cliente)

    # PÓS-VENDA
    if resposta_id == "pos_garantia":
        return _send_text(contato, "🛠️ Para garantia, envie: Placa, modelo e problema apresentado.")

    if resposta_id == "pos_agendar":
        return _send_text(
            contato,
            "📅 Para agendar um serviço no pós-venda, envie:\n"
            "• Placa\n• Modelo\n• Serviço desejado\n• Data e período preferidos"
        )

    # ENDEREÇOS
    if resposta_id == "op_endereco":
        return _send_buttons(contato, MSG_ENDERECOS, BTN_ENDERECOS)

    if resposta_id in ["end_loja", "end_oficina"]:
        return _send_text(contato, MSG_ENDERECOS)

    # VOLTAR
    if resposta_id == "op_voltar":
        ESTADOS_ATENDIMENTO.pop(contato, None)
        return _send_buttons(contato, msg_boas_vindas(nome_cliente), BTN_ROOT)

    # NÃO RECONHECIDO
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
        texto, texto_lower, resposta_id = "", "", None

        if tipo == "text":
            texto = msg["text"]["body"]
            texto_lower = texto.lower().strip()

        elif tipo == "interactive":
            inter = msg["interactive"]
            if inter["type"] == "button_reply":
                resposta_id = inter["button_reply"]["id"]
                texto = inter["button_reply"]["title"]
                texto_lower = texto.lower().strip()

        print(f"[WA] Msg de {contato}: {texto} ({resposta_id})")

        # Saudações: sempre reiniciam o fluxo
        if texto_lower and any(p in texto_lower for p in ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite"]):
            ESTADOS_ATENDIMENTO.pop(contato, None)
            return _send_buttons(contato, msg_boas_vindas(nome_wa), BTN_ROOT)

        # Se veio de botão, roteia pelos botões
        if resposta_id:
            return _rotear_escolha(contato, resposta_id, nome_wa)

        # Se não é botão mas há fluxo em andamento, continua o fluxo de perguntas
        if ESTADOS_ATENDIMENTO.get(contato):
            return _continuar_fluxo_dados(contato, texto)

        # Fallback
        return _send_text(contato, "Envie *oi* para iniciar.")
    except Exception as e:
        print("[ERRO responder_evento_mensagem]", e)
        try:
            _send_text(contato, "⚠️ Erro temporário. Tente novamente.")
        except Exception:
            print("[ERRO responder_evento_mensagem] Falha ao enviar mensagem de erro ao cliente.")

print("✅ responder_oficina.py carregado com sucesso — Sullato Oficina")
