import os
import time
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# CONSULTA ENDEREÇO PELO CEP (ViaCEP)
# ============================================================

def consultar_endereco_por_cep(cep):
    try:
        cep_limpo = cep.replace("-", "").strip()
        url = f"https://viacep.com.br/ws/{cep_limpo}/json/"
        r = requests.get(url, timeout=5)
        if r.status_code != 200:
            return ""

        data = r.json()

        if "erro" in data:
            return ""

        # 🔥 TRECHO CORRIGIDO — agora com indentação perfeita
        logradouro = data.get("logradouro", "").strip() or "Não informado"
        bairro = data.get("bairro", "").strip() or "Não informado"
        cidade = data.get("localidade", "").strip() or "Não informado"
        estado = data.get("uf", "").strip() or "Não informado"

        endereco = f"{logradouro}, {bairro}, {cidade} - {estado}"
        return endereco

    except:
        return ""

# ============================================================
# VARIÁVEIS DE AMBIENTE
# ============================================================

WHATSAPP_API_URL = f"https://graph.facebook.com/v17.0/{os.getenv('WA_PHONE_NUMBER_ID')}"
WHATSAPP_TOKEN = os.getenv("WA_ACCESS_TOKEN")
GOOGLE_SHEETS_URL = os.getenv("OFICINA_SHEET_WEBHOOK_URL")
SECRET_KEY = os.getenv("OFICINA_SHEETS_SECRET")

TIMEOUT_SESSAO = 600
SESSOES = {}

# ============================================================
# ENVIAR TEXTO
# ============================================================

def enviar_texto(numero, texto):
    try:
        payload = {
            "messaging_product": "whatsapp",
            "to": numero,
            "text": {"body": texto},
        }
        headers = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json",
        }
        requests.post(f"{WHATSAPP_API_URL}/messages", json=payload, headers=headers)
    except Exception as e:
        print("Erro enviar texto:", e)

# ============================================================
# ENVIAR BOTÕES
# ============================================================

def enviar_botoes(numero, texto, botoes):
    try:
        botoes_formatados = [
            {"type": "reply", "reply": {"id": i["id"], "title": i["title"]}}
            for i in botoes
        ]

        payload = {
            "messaging_product": "whatsapp",
            "to": numero,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": texto},
                "action": {"buttons": botoes_formatados},
            },
        }

        headers = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json",
        }

        requests.post(f"{WHATSAPP_API_URL}/messages", json=payload, headers=headers)

    except Exception as e:
        print("Erro enviar botões:", e)

# ============================================================
# RESETAR SESSÃO
# ============================================================

def reset_sessao(numero):
    if numero in SESSOES:
        del SESSOES[numero]

# ============================================================
# INICIAR SESSÃO
# ============================================================

def iniciar_sessao(numero, nome_whatsapp):
    SESSOES[numero] = {
        "etapa": "menu_inicial",
        "inicio": time.time(),
        "dados": {
            "fone": numero,
            "nome_whatsapp": nome_whatsapp,
            "origem_cliente": "chatbot oficina",
        },
    }

    enviar_texto(
        numero,
        f"Olá {nome_whatsapp}! 👋\n\n"
        "Vamos iniciar seu atendimento.\n\n"
        "*Escolha uma opção:*\n"
        "1 – Serviços\n"
        "2 – Peças\n"
        "3 – Pós-venda / Garantia\n"
        "4 – Retorno Oficina\n"
        "5 – Endereço e Contatos",
    )

# ============================================================
# SALVAR VIA GOOGLE SHEETS
# ============================================================

def salvar_via_webapp(sessao):
    try:
        campos_validos = {}

        for campo, valor in sessao["dados"].items():
            # Ignorar valores que NÃO são aceitos pelo Google Sheets
            if isinstance(valor, (str, int, float)):
                campos_validos[campo] = valor

        payload = {
            "secret": SECRET_KEY,
            "route": "chatbot",
            "dados": campos_validos
        }

        headers = { "Content-Type": "application/json" }

        print("📤 Enviando para:", GOOGLE_SHEETS_URL)
        print("📦 Payload final:", payload)

        resp = requests.post(GOOGLE_SHEETS_URL, json=payload, headers=headers)
        print("📥 RESPOSTA:", resp.status_code, resp.text)

    except Exception as e:
        print("❌ Erro salvar webapp:", e)


# ============================================================
# RESUMO FINAL
# ============================================================

def construir_resumo(d):
    return (
        "✅ *Resumo do seu atendimento:*\n\n"
        f"*Nome:* {d.get('nome','')}\n"
        f"*CPF:* {d.get('cpf','')}\n"
        f"*Nascimento:* {d.get('nascimento','')}\n"
        f"*Telefone:* {d.get('fone','')}\n\n"
        "🚗 *Veículo*\n"
        f"Tipo: {d.get('tipo_veiculo','')}\n"
        f"Marca/Modelo: {d.get('marca_modelo','')}\n"
        f"Ano Fab/Mod: {d.get('ano_modelo','')}\n"
        f"KM: {d.get('km','')}\n"
        f"Combustível: {d.get('combustivel','')}\n"
        f"Placa: {d.get('placa','')}\n\n"
        "📍 *Endereço*\n"
        f"CEP: {d.get('cep','')}\n"
        f"Número: {d.get('numero','')}\n"
        f"Complemento: {d.get('complemento','')}\n\n"
        "📝 *Atendimento*\n"
        f"Tipo: {d.get('tipo_registro','')}\n"
        f"Descrição: {d.get('descricao','')}\n"
        f"Origem: {d.get('origem','')}\n"
        f"Feedback: {d.get('feedback','')}\n"
    )

# ============================================================
# FLUXO PRINCIPAL
# ============================================================

def responder_oficina(numero, texto_digitado, nome_whatsapp):

    texto = texto_digitado.strip()
    agora = time.time()

    # Criar sessão
    if numero not in SESSOES:
        iniciar_sessao(numero, nome_whatsapp)
        return

    sessao = SESSOES[numero]

    # Timeout
    if agora - sessao.get("inicio", 0) > TIMEOUT_SESSAO:
        enviar_texto(numero, "Sessão expirada. Vamos recomeçar!")
        iniciar_sessao(numero, nome_whatsapp)
        return

    sessao["inicio"] = agora
    etapa = sessao["etapa"]
    d = sessao["dados"]

    # ============================================================
    # MENU INICIAL
    # ============================================================

    if etapa == "menu_inicial":

        if texto == "1":
            d["interesse_inicial"] = "servicos"
            sessao["etapa"] = "pergunta_nome"
            enviar_texto(numero, "Digite seu nome completo:")
            return

        if texto == "2":
            d["interesse_inicial"] = "pecas"
            sessao["etapa"] = "pergunta_nome"
            enviar_texto(numero, "Digite seu nome completo:")
            return

        if texto == "3":
            d["interesse_inicial"] = "pos_venda"
            sessao["etapa"] = "pergunta_nome"
            enviar_texto(numero, "Digite seu nome completo:")
            return

        if texto == "4":
            d["interesse_inicial"] = "retorno"
            sessao["etapa"] = "pergunta_nome"
            enviar_texto(numero, "Digite seu nome completo:")
            return

        if texto == "5":
            d["interesse_inicial"] = "endereco"
            d["tipo_registro"] = "Consulta Endereço"
            d["descricao"] = "Cliente acessou o menu de endereço"
            d["origem"] = "chatbot oficina"

            # ✔ SALVAR ANTES DE ENVIAR AS MENSAGENS
            salvar_via_webapp(sessao)

            enviar_texto(
                numero,
                "📍 *Endereços e contatos Sullato*\n\n"

                "🌐 Site: https://www.sullato.com.br\n\n"
                
                "📍 *Sullato Micros e Vans*\n"
                "Av. São Miguel, 7900 – CEP 08070-001\n"
                "☎️ (11) 2030-5081 / (11) 2031-5081\n"
                "👉 https://wa.me/5511940545704\n"
                "👉 https://wa.me/551120305081\n"
                "📸 Instagram: https://www.instagram.com/sullatomicrosevans\n\n"

                "📍 *Sullato Veículos*\n"
                "Av. São Miguel, 4049/4084 – CEP 03871-000\n"
                "☎️ (11) 2542-3332 / (11) 2542-3333\n"
                "👉 https://wa.me/5511940545704\n"
                "👉 https://wa.me/551125423332\n"
                "📸 Instagram: https://www.instagram.com/sullato.veiculos\n\n"

                "📍 *Sullato Oficina e Peças*\n"
                "Av. Amador Bueno da Veiga, 4222 – CEP 03652-000\n"
                "☎️ (11) 2542-3333\n"
                "👉 https://wa.me/551125423333\n\n",
                "🔧 *Érico*: https://wa.me/5511940497678\n"
                "🔧 *Leandro*: https://wa.me/5511940443566\n"
            )

            enviar_texto(numero, "Se precisar de ajuda, estou aqui! 😊")
            
            reset_sessao(numero)
            return

        enviar_texto(numero, "❗Digite uma opção válida entre 1 e 5.")
        return

    # ============================================================
    # PERGUNTAS BÁSICAS
    # ============================================================

    if etapa == "pergunta_nome":
        d["nome"] = texto
        sessao["etapa"] = "pergunta_cpf"
        enviar_texto(numero, "Digite *seu CPF*:")
        return

    if etapa == "pergunta_cpf":
        d["cpf"] = texto
        sessao["etapa"] = "pergunta_nascimento"
        enviar_texto(numero, "Digite sua *data de nascimento*:")
        return

    if etapa == "pergunta_nascimento":
        d["nascimento"] = texto
        sessao["etapa"] = "pergunta_tipo_veiculo"
        enviar_botoes(
            numero,
            "Qual o tipo de veículo?",
            [
                {"id": "tv_passeio", "title": "Passeio"},
                {"id": "tv_utilitario", "title": "Utilitário"},
            ],
        )
        return

    if etapa == "pergunta_tipo_veiculo":
        if texto in ["tv_passeio", "Passeio"]:
            d["tipo_veiculo"] = "Passeio"
        elif texto in ["tv_utilitario", "Utilitário"]:
            d["tipo_veiculo"] = "Utilitário"
        else:
            enviar_texto(numero, "Escolha uma opção válida.")
            return

        sessao["etapa"] = "pergunta_marca_modelo"
        enviar_texto(numero, "Digite *marca/modelo*:")
        return

    if etapa == "pergunta_marca_modelo":
        d["marca_modelo"] = texto
        sessao["etapa"] = "pergunta_ano_modelo"
        enviar_texto(numero, "Digite o *ano fab/mod*:")
        return

    if etapa == "pergunta_ano_modelo":
        d["ano_modelo"] = texto
        sessao["etapa"] = "pergunta_km"
        enviar_texto(numero, "Digite o KM atual:")
        return

    if etapa == "pergunta_km":
        d["km"] = texto
        sessao["etapa"] = "pergunta_combustivel"
        enviar_texto(numero, "Qual o combustível? (Gasolina, Etanol, Diesel, Flex ou GNV)")
        return

    if etapa == "pergunta_combustivel":

        combustivel = texto.lower()
        if combustivel not in ["gasolina", "etanol", "diesel", "flex", "gnv"]:
            enviar_texto(numero, "Informe um combustível válido.")
            return

        d["combustivel"] = combustivel.title()
        sessao["etapa"] = "pergunta_placa"
        enviar_texto(numero, "Digite a *placa*:")
        return

    if etapa == "pergunta_placa":
        d["placa"] = texto
        sessao["etapa"] = "pergunta_cep"
        enviar_texto(numero, "Digite o *CEP* (00000-000):")
        return

    if etapa == "pergunta_cep":
        d["cep"] = texto

        # 🔥 NOVO: consultar endereço pelo CEP
        endereco = consultar_endereco_por_cep(texto)
        d["endereco_completo"] = endereco

        sessao["etapa"] = "pergunta_numero_endereco"
        enviar_texto(numero, "Digite o *número*:")
        return

    if etapa == "pergunta_numero_endereco":
        d["numero"] = texto
        sessao["etapa"] = "pergunta_complemento"
        enviar_botoes(
            numero,
            "Deseja informar complemento?",
            [
                {"id": "comp_sim", "title": "Sim"},
                {"id": "comp_nao", "title": "Não"},
            ],
        )
        return

    if etapa == "pergunta_complemento":

        if texto.lower() in ["comp_sim", "sim"]:
            sessao["etapa"] = "complemento_digitacao"
            enviar_texto(numero, "Digite o complemento:")
            return

        if texto.lower() in ["comp_nao", "não", "nao"]:
            d["complemento"] = ""
            sessao["etapa"] = "descricao_especifica"
            # Avança automaticamente
            return responder_oficina(numero, "", nome_whatsapp)

        enviar_texto(numero, "Escolha Sim ou Não.")
        return

    if etapa == "complemento_digitacao":
        d["complemento"] = texto
        sessao["etapa"] = "descricao_especifica"
        # Avança automaticamente
        return responder_oficina(numero, "", nome_whatsapp)

    # ============================================================
    # DESCRIÇÃO ESPECÍFICA
    # ============================================================

    if etapa == "descricao_especifica":

        texto = texto.strip()   # ← LINHA NOVA (necessária)

        # Serviços
        if d.get("interesse_inicial") == "servicos":
            d["tipo_registro"] = "Serviço"
            sessao["etapa"] = "descricao_servico"
            enviar_texto(numero, "Descreva o serviço desejado:")
            return

        # Peças
        if d.get("interesse_inicial") == "pecas":
            d["tipo_registro"] = "Peça"
            sessao["etapa"] = "descricao_peca"
            enviar_texto(numero, "Descreva qual peça você procura:")
            return

        # Pós-venda
        if d.get("interesse_inicial") == "pos_venda":
            d["tipo_registro"] = "Pós-venda"
            sessao["etapa"] = "posvenda_data_compra"
            enviar_texto(numero, "Qual a data da compra / aquisição do veículo?")
            return

        # Retorno Oficina
        if d.get("interesse_inicial") == "retorno":
            d["tipo_registro"] = "Retorno Oficina"
            sessao["etapa"] = "retorno_data_servico"
            enviar_texto(numero, "Qual foi a data do serviço realizado?")
            return

    # ============================================================
    # SERVIÇOS
    # ============================================================

    if etapa == "descricao_servico":
        d["descricao"] = texto
        sessao["etapa"] = "servico_origem"
        enviar_texto(
        numero,
            "Como nos conheceu?\n"
            "1 – Instagram\n"
            "2 – Facebook\n"
            "3 – Google\n"
            "4 – Outros"
        )
        return

    if etapa == "servico_origem":
        mapa_origem = {
            "1": "Instagram",
            "2": "Facebook",
            "3": "Google",
            "4": "Outros"
        }

        d["origem"] = mapa_origem.get(texto, texto)
        sessao["etapa"] = "confirmacao"
        resumo = construir_resumo(d)
        enviar_botoes(
            numero,
            resumo + "\n\nConfirma?",
            [
                {"id": "confirmar", "title": "Confirmar"},
                {"id": "editar", "title": "Editar"},
            ],
        )
        return

    # ============================================================
    # PEÇAS
    # ============================================================

    if etapa == "descricao_peca":
        d["descricao"] = texto
        sessao["etapa"] = "peca_origem"
        enviar_texto(
        numero,
        "Como nos conheceu?\n"
            "1 – Instagram\n"
            "2 – Facebook\n"
            "3 – Google\n"
            "4 – Outros"
        )
        return

    if etapa == "peca_origem":
        mapa_origem = {
            "1": "Instagram",
            "2": "Facebook",
            "3": "Google",
            "4": "Outros"
        }

        d["origem"] = mapa_origem.get(texto, texto)
        sessao["etapa"] = "confirmacao"
        resumo = construir_resumo(d)
        enviar_botoes(
            numero,
            resumo + "\n\nConfirma a peça?",
            [
                {"id": "confirmar", "title": "Confirmar"},
                {"id": "editar", "title": "Editar"},
            ],
        )
        return

    # ============================================================
    # PÓS-VENDA
    # ============================================================

    if etapa == "posvenda_data_compra":
        d["data_compra_veiculo"] = texto
        sessao["etapa"] = "posvenda_descricao"
        enviar_texto(numero, "Descreva o problema ocorrido:")
        return

    if etapa == "posvenda_descricao":
        d["descricao"] = texto
        sessao["etapa"] = "posvenda_feedback"
        enviar_texto(numero, "Nos deixe uma sugestão:")
        return

    if etapa == "posvenda_feedback":
        d["feedback"] = texto
        sessao["etapa"] = "confirmacao"
        resumo = construir_resumo(d)
        enviar_botoes(
            numero,
            resumo + "\n\nConfirma?",
            [
                {"id": "confirmar", "title": "Confirmar"},
                {"id": "editar", "title": "Editar"},
            ],
        )
        return

    # ============================================================
    # RETORNO OFICINA
    # ============================================================

    if etapa == "retorno_data_servico":
        d["data_servico"] = texto
        sessao["etapa"] = "retorno_os"
        enviar_texto(numero, "Digite o número da OS:")
        return

    if etapa == "retorno_os":
        d["ordem_servico"] = texto
        sessao["etapa"] = "retorno_descricao"
        enviar_texto(numero, "Descreva o problema encontrado após o serviço:")
        return

    if etapa == "retorno_descricao":
        d["descricao"] = texto
        sessao["etapa"] = "retorno_feedback"
        enviar_texto(numero, "Nos deixe uma sugestão:")
        return

    if etapa == "retorno_feedback":
        d["feedback"] = texto
        sessao["etapa"] = "confirmacao"
        resumo = construir_resumo(d)
        enviar_botoes(
            numero,
            resumo + "\n\nConfirma?",
            [
                {"id": "confirmar", "title": "Confirmar"},
                {"id": "editar", "title": "Editar"},
            ],
        )
        return

        # ============================================================
    # CONFIRMAÇÃO FINAL
    # ============================================================

    if etapa == "confirmacao":

        texto_normalizado = texto.strip().lower()

        # Aceitar clique no botão OU digitação manual
        if texto_normalizado in ["confirmar", "confirm", "ok", "confirmar_button", "id_confirmar"]:
            salvar_via_webapp(sessao)
            reset_sessao(numero)
            enviar_texto(
                numero,
                "👍 *Perfeito!* Seus dados foram enviados.\n"
                "Um técnico da Sullato entrará em contato em breve!"
            )
            return

        if texto_normalizado in ["editar", "corrigir", "editar_button"]:
            sessao["etapa"] = "pergunta_nome"
            enviar_texto(numero, "Vamos corrigir. Digite seu nome completo:")
            return

        enviar_texto(numero, "Escolha uma opção válida.")
        return

    
