# -*- coding: utf-8 -*-
import os
import time
import requests
from datetime import datetime, timedelta
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

WHATSAPP_API_URL = f"https://graph.facebook.com/v20.0/{os.getenv('WA_PHONE_NUMBER_ID')}"
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
            "Accept": "application/json"
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
# ENVIAR IMAGEM (DUMMY — APENAS PARA COMPATIBILIDADE)
# ============================================================

def obter_imagem_oficina_mes():
    try:
        payload = {
            "secret": SECRET_KEY,
            "route": "get_imagem_mes"
        }

        r = requests.post(GOOGLE_SHEETS_URL, json=payload, timeout=10)
        data = r.json()

        url = data.get("url", "")
        if not url:
            print("⚠️ Planilha não retornou URL de imagem")
            return ""

        return normalizar_dropbox(url)

    except Exception as e:
        print("❌ Erro ao buscar imagem da planilha:", e)
        return ""


def normalizar_dropbox(url):
    if not url:
        return ""

    u = url.strip()
    u = u.replace("https://www.dropbox.com", "https://dl.dropboxusercontent.com")
    u = u.replace("?dl=0", "")
    return u


def enviar_imagem(numero, url):
    if not url:
        print("⚠️ URL de imagem vazia, envio ignorado")
        return

    try:
        payload = {
            "messaging_product": "whatsapp",
            "to": numero,
            "type": "image",
            "image": {
                "link": url
            }
        }

        headers = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json"
        }

        r = requests.post(
            f"{WHATSAPP_API_URL}/messages",
            json=payload,
            headers=headers,
            timeout=10
        )

        print("📤 ENVIO IMAGEM:", r.status_code, r.text)

    except Exception as e:
        print("❌ Erro ao enviar imagem:", e)

# ============================================================
# RESETAR SESSÃO
# ============================================================

def reset_sessao(numero):
    if numero in SESSOES:
        del SESSOES[numero]

# ============================================================
# HORÁRIO DE ATENDIMENTO — OFICINA
# ============================================================
from datetime import datetime, timedelta  # 👈 ajuste no import

def _em_horario_oficina():
    agora = datetime.utcnow() - timedelta(hours=3)  # 👈 força horário Brasil

    dia = agora.weekday()
    hora = agora.hour

    if 0 <= dia <= 4:
        return 9 <= hora < 18

    if dia == 5:
        return 9 <= hora < 13

    return False

# ============================================================
# INICIAR SESSÃO
# ============================================================

def iniciar_sessao(numero, nome_whatsapp):
    SESSOES[numero] = {
        "etapa": "menu_inicial",
        "inicio": time.time(),
        "acesso_registrado": False,   # 🔥 NOVO CONTROLE
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
        "5 – Endereço e Contato",
    )

# ============================================================
# SALVAR VIA GOOGLE SHEETS
# ============================================================

def salvar_via_webapp(sessao):
    try:
        campos_validos = {}

        for campo, valor in sessao["dados"].items():
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

    # return (
    #     "✅ *Resumo do seu atendimento:*\n\n"
    #     f"*Nome:* {d.get('nome','')}\n"
    #     f"*CPF:* {d.get('cpf','')}\n"
    #     f"*Nascimento:* {d.get('nascimento','')}\n"
    #     f"*Telefone:* {d.get('fone','')}\n\n"
    #     "🚗 *Veículo*\n"
    #     f"Tipo: {d.get('tipo_veiculo','')}\n"
    #     f"Marca/Modelo: {d.get('marca_modelo','')}\n"
    #     f"Ano Fab/Mod: {d.get('ano_modelo','')}\n"
    #     f"KM: {d.get('km','')}\n"
    #     f"Combustível: {d.get('combustivel','')}\n"
    #     f"Placa: {d.get('placa','')}\n\n"
    #     "📍 *Endereço*\n"
    #     f"CEP: {d.get('cep','')}\n"
    #     f"Número: {d.get('numero','')}\n"
    #     f"Complemento: {d.get('complemento','')}\n\n"
    #     "📝 *Atendimento*\n"
    #     f"Tipo: {d.get('tipo_registro','')}\n"
    #     f"Descrição: {d.get('descricao','')}\n"
    #     f"Origem: {d.get('origem','')}\n"
    #     f"Feedback: {d.get('feedback','')}\n"
    # )

    return (
        "✅ *Resumo do seu atendimento:*\n\n"
        f"*Nome:* {d.get('nome','')}\n"
        f"*Telefone:* {d.get('fone','')}\n"
        f"*Marca/Modelo:* {d.get('marca_modelo','')}\n\n"
        "📝 *Atendimento*\n"
        f"Tipo: {d.get('tipo_registro','')}\n"
        f"Descrição: {d.get('descricao','')}\n"
        f"Origem: {d.get('origem','')}\n"
        f"Feedback: {d.get('feedback','')}\n"
    )

# ============================================================
# MENSAGENS DE FECHAMENTO — OFICINA
# ============================================================

FECHAMENTO_DENTRO = (
    "✅ Obrigado! Seu atendimento foi registrado.\n\n"
    "Em breve, nossa equipe vai falar com você.\n\n"
    "📲 Contato:\n"
    "(11) 99408-1931\n\n"
    "⏰ Horário de atendimento:\n"
    "Segunda a sexta das 9h às 18h\n"
    "Sábado das 9h às 13h\n\n"
    "Se preferir, fale agora com nossa equipe:\n"
    "https://wa.me/5511994081931"
)

FECHAMENTO_FORA = (
    "✅ Obrigado! Seu atendimento foi registrado.\n\n"
    "📩 Sua solicitação foi recebida com sucesso.\n\n"
    "⏰ No momento estamos fora do horário de atendimento.\n"
    "Atendemos de segunda a sexta das 9h às 18h\n"
    "e aos sábados das 9h às 13h.\n\n"
    "Assim que retornarmos, nossa equipe entrará em contato.\n\n"
    "📲 Se desejar, você pode enviar mensagem:\n"
    "https://wa.me/5511994081931"
)

# ============================================================
def enviar_template_oficina_disparo(numero):
    url = f"https://graph.facebook.com/v17.0/{os.getenv('WA_PHONE_NUMBER_ID')}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": numero,
        "type": "template",
        "template": {
            "name": "oficina_disparo2",
            "language": {
                "code": "pt_BR"
            }
        }
    }

    headers = {
        "Authorization": f"Bearer {os.getenv('WA_ACCESS_TOKEN')}",
        "Content-Type": "application/json"
    }

    response = requests.post(url, headers=headers, json=payload)

    print("📤 TEMPLATE STATUS:", response.status_code)
    print("📤 TEMPLATE BODY:", response.text)

    return response.text

# ============================================================
# FLUXO PRINCIPAL
# ============================================================

def responder_oficina(numero, texto_digitado, nome_whatsapp):

    texto = (texto_digitado or "").strip().lower()

    agora = time.time()

    # ============================================================
    # PRIMEIRO CONTATO OU NOVA SESSÃO
    # ============================================================

    if numero not in SESSOES:

        iniciar_sessao(numero, nome_whatsapp)

        # 🔥 REGISTRA ACESSO INICIAL
        try:
            payload = {
                "secret": SECRET_KEY,
                "route": "chatbot",
                "dados": {
                    "fone": numero,
                    "nome_whatsapp": nome_whatsapp,
                    "interesse_inicial": "acesso_inicial",
                    "tipo_registro": "Acesso",
                    "origem": "whatsapp"
                }
            }

            requests.post(GOOGLE_SHEETS_URL, json=payload)

        except Exception as e:
            print("Erro registrar acesso:", e)

        return

    sessao = SESSOES[numero]

    # ============================================================
    # TIMEOUT DE SESSÃO
    # ============================================================

    if agora - sessao.get("inicio", 0) > TIMEOUT_SESSAO:

        enviar_texto(numero, "Sessão expirada. Vamos recomeçar! 👋")

        # Encerra sessão anterior
        reset_sessao(numero)

        # Inicia nova sessão
        iniciar_sessao(numero, nome_whatsapp)

        # 🔥 REGISTRA NOVO ACESSO POR TIMEOUT
        try:
            payload = {
                "secret": SECRET_KEY,
                "route": "chatbot",
                "dados": {
                    "fone": numero,
                    "nome_whatsapp": nome_whatsapp,
                    "interesse_inicial": "acesso_inicial",
                    "tipo_registro": "Acesso",
                    "origem": "whatsapp"
                }
            }

            requests.post(GOOGLE_SHEETS_URL, json=payload, timeout=10)

        except Exception as e:
            print("Erro registrar acesso (timeout):", e)

        return

    # ============================================================
    # SESSÃO ATIVA
    # ============================================================

    # Atualiza tempo da sessão ativa
    sessao["inicio"] = agora

    etapa = sessao.get("etapa")
    d = sessao.get("dados")

    # ============================================================
    # MENU INICIAL
    # ============================================================

    if etapa == "menu_inicial":

        if texto in ["1", "btn_servicos"]:
            d["interesse_inicial"] = "servicos"

            # sessao["etapa"] = "ja_cadastrado"
            # enviar_botoes(
            #     numero,
            #     "Você já fez atendimento conosco antes?",
            #     [
            #         {"id": "cad_sim", "title": "Sim"},
            #         {"id": "cad_nao", "title": "Não"}
            #     ]
            # )


            sessao["etapa"] = "pergunta_nome"
            enviar_texto(numero, "Digite seu nome completo:")
            return

        if texto in ["2", "btn_pecas"]:
            d["interesse_inicial"] = "pecas"

            # sessao["etapa"] = "ja_cadastrado"
            # enviar_botoes(
            #     numero,
            #     "Você já fez atendimento conosco antes?",
            #     [
            #         {"id": "cad_sim", "title": "Sim"},
            #         {"id": "cad_nao", "title": "Não"}
            #     ]
            # )

            sessao["etapa"] = "pergunta_nome"
            enviar_texto(numero, "Digite seu nome completo:")
            return

        if texto in ["3", "btn_pos_venda"]:
            d["interesse_inicial"] = "pos_venda"

            # sessao["etapa"] = "ja_cadastrado"
            # enviar_botoes(
            #     numero,
            #     "Você já fez atendimento conosco antes?",
            #     [
            #         {"id": "cad_sim", "title": "Sim"},
            #         {"id": "cad_nao", "title": "Não"}
            #     ]
            # )

            sessao["etapa"] = "pergunta_nome"
            enviar_texto(numero, "Digite seu nome completo:")
            return

        if texto in ["4", "btn_retorno"]:
            d["interesse_inicial"] = "retorno_oficina"

            # sessao["etapa"] = "ja_cadastrado"
            # enviar_botoes(
            #     numero,
            #     "Você já fez atendimento conosco antes?",
            #     [
            #         {"id": "cad_sim", "title": "Sim"},
            #         {"id": "cad_nao", "title": "Não"}
            #     ]
            # )

            sessao["etapa"] = "pergunta_nome"
            enviar_texto(numero, "Digite seu nome completo:")
            return
        
        if texto in ["5", "btn_endereco"]:
            d["interesse_inicial"] = "endereco"

            salvar_via_webapp(sessao)

            enviar_texto(
                numero,
                "📍 *Endereços e Contatos Sullato*\n\n"
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
                "👉 https://wa.me/551125423330\n"
                "📸 Instagram: https://www.instagram.com/sullato.veiculos\n\n"

                "📍 *Sullato Oficina e Peças*\n"
                "Av. Amador Bueno da Veiga, 4222 – CEP 03652-000\n"
                "☎️ (11) 20922304\n"
                "👉 https://wa.me/5511994081931\n\n"
                "🔧 *Érico*: https://wa.me/5511940497678\n"
            )

            enviar_texto(numero, "Se precisar de ajuda, estou aqui! 😊")
            reset_sessao(numero)
            return

    # ============================================================
    # ETAPA: JA_CADASTRADO
    # ============================================================

    # if etapa == "ja_cadastrado":
    #
    #     if texto in ["cad_sim", "btn_cad_sim", "sim"]:
    #         sessao["veio_de"] = "cliente_antigo"
    #         sessao["etapa"] = "pergunta_cpf"
    #         enviar_texto(numero, "Digite seu *CPF* (ex: 123.456.789-00):")
    #         return
    #
    #     if texto in ["cad_nao", "btn_cad_nao", "não", "nao"]:
    #         sessao["etapa"] = "pergunta_nome"
    #         enviar_texto(numero, "Digite seu nome completo:")
    #         return
    #
    #     enviar_texto(numero, "Escolha uma opção válida.")
    #     return

    # ============================================================
    # PERGUNTA NOME
    # ============================================================

    if etapa == "pergunta_nome":
        d["nome"] = texto

        # sessao["etapa"] = "pergunta_cpf"
        # enviar_texto(numero, "Digite *seu CPF* (ex: 123.456.789-00):")

        sessao["etapa"] = "pergunta_marca_modelo"
        enviar_texto(numero, "Digite a *marca/modelo* do veículo:")
        return

    # ============================================================
    # PERGUNTA CPF
    # ============================================================

    if etapa == "pergunta_cpf":

        cpf_limpo = (
            texto.replace(".", "").replace("-", "").replace(" ", "").strip()
        )

        if len(cpf_limpo) == 11 and cpf_limpo.isdigit():
            texto_fmt = f"{cpf_limpo[0:3]}.{cpf_limpo[3:6]}.{cpf_limpo[6:9]}-{cpf_limpo[9:11]}"
            d["cpf"] = texto_fmt
        else:
            enviar_texto(numero, "CPF inválido. Digite no formato 123.456.789-00")
            return

        if sessao.get("veio_de") == "cliente_antigo":

            if d.get("interesse_inicial") == "servicos":
                d["tipo_registro"] = "Serviço"
                sessao["etapa"] = "descricao_servico"
                enviar_texto(numero, "Descreva o serviço desejado:")
                return

            if d.get("interesse_inicial") == "pecas":
                d["tipo_registro"] = "Peça"
                sessao["etapa"] = "descricao_peca"
                enviar_texto(numero, "Descreva qual peça você procura:")
                return

            if d.get("interesse_inicial") == "pos_venda":
                d["tipo_registro"] = "Pós-venda"
                sessao["etapa"] = "posvenda_data_compra"
                enviar_texto(numero, "Qual a data da compra / aquisição do veículo?")
                return

            if d.get("interesse_inicial") == "retorno_oficina":
                d["tipo_registro"] = "Retorno Oficina"
                sessao["etapa"] = "retorno_data_servico"
                enviar_texto(numero, "Qual foi a data do serviço realizado?")
                return

        sessao["etapa"] = "pergunta_nascimento"
        enviar_texto(numero, "Digite sua *data de nascimento*:")
        return

    # ============================================================
    # NASCIMENTO → VEÍCULO
    # ============================================================

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
        if texto == "tv_passeio":
            d["tipo_veiculo"] = "Passeio"
        elif texto == "tv_utilitario":
            d["tipo_veiculo"] = "Utilitário"
        else:
            enviar_texto(numero, "Escolha uma opção válida.")
            return

        sessao["etapa"] = "pergunta_marca_modelo"
        enviar_texto(numero, "Digite *marca/modelo*:")
        return

    if etapa == "pergunta_marca_modelo":
        d["marca_modelo"] = texto

        # sessao["etapa"] = "pergunta_ano_modelo"
        # enviar_texto(numero, "Digite o *ano fab/mod*:")

        sessao["etapa"] = "descricao_especifica"
        # Força execução imediata da próxima etapa
        return responder_oficina(numero, "", nome_whatsapp)

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

    # ============================================================
    # CEP + ENDEREÇO
    # ============================================================

    if etapa == "pergunta_cep":
        d["cep"] = texto

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

        if texto.lower() in ["comp_sim", "btn_comp_sim", "sim"]:
            sessao["etapa"] = "complemento_digitacao"
            enviar_texto(numero, "Digite o complemento:")
            return

        if texto.lower() in ["comp_nao", "btn_comp_nao", "não", "nao"]:
            d["complemento"] = ""

            # DISPARO DIRETO DA PRÓXIMA ETAPA
            if d.get("interesse_inicial") == "servicos":
                d["tipo_registro"] = "Serviço"
                sessao["etapa"] = "descricao_servico"
                enviar_texto(numero, "Descreva o serviço desejado:")
                return

            if d.get("interesse_inicial") == "pecas":
                d["tipo_registro"] = "Peça"
                sessao["etapa"] = "descricao_peca"
                enviar_texto(numero, "Descreva qual peça você procura:")
                return

            if d.get("interesse_inicial") == "pos_venda":
                d["tipo_registro"] = "Pós-venda"
                sessao["etapa"] = "posvenda_data_compra"
                enviar_texto(numero, "Qual a data da compra / aquisição do veículo?")
                return

            if d.get("interesse_inicial") == "retorno_oficina":
                d["tipo_registro"] = "Retorno Oficina"
                sessao["etapa"] = "retorno_data_servico"
                enviar_texto(numero, "Qual foi a data do serviço realizado?")
                return

        enviar_texto(numero, "Escolha Sim ou Não.")
        return

    if etapa == "complemento_digitacao":
        d["complemento"] = texto

        if d.get("interesse_inicial") == "servicos":
            d["tipo_registro"] = "Serviço"
            sessao["etapa"] = "descricao_servico"
            enviar_texto(numero, "Descreva o serviço desejado:")
            return

        if d.get("interesse_inicial") == "pecas":
            d["tipo_registro"] = "Peça"
            sessao["etapa"] = "descricao_peca"
            enviar_texto(numero, "Descreva qual peça você procura:")
            return

        if d.get("interesse_inicial") == "pos_venda":
            d["tipo_registro"] = "Pós-venda"
            sessao["etapa"] = "posvenda_data_compra"
            enviar_texto(numero, "Qual a data da compra / aquisição do veículo?")
            return

        if d.get("interesse_inicial") == "retorno_oficina":
            d["tipo_registro"] = "Retorno Oficina"
            sessao["etapa"] = "retorno_data_servico"
            enviar_texto(numero, "Qual foi a data do serviço realizado?")
            return

    # ============================================================
    # DESCRIÇÃO ESPECÍFICA
    # ============================================================

    if etapa == "descricao_especifica":

        if d.get("interesse_inicial") == "servicos":
            d["tipo_registro"] = "Serviço"
            sessao["etapa"] = "descricao_servico"
            enviar_texto(numero, "Descreva o serviço desejado:")
            return

        if d.get("interesse_inicial") == "pecas":
            d["tipo_registro"] = "Peça"
            sessao["etapa"] = "descricao_peca"
            enviar_texto(numero, "Descreva qual peça você procura:")
            return

        if d.get("interesse_inicial") == "pos_venda":
            d["tipo_registro"] = "Pós-venda"
            sessao["etapa"] = "posvenda_data_compra"
            enviar_texto(numero, "Qual a data da compra / aquisição do veículo?")
            return

        if d.get("interesse_inicial") == "retorno_oficina":
            d["tipo_registro"] = "Retorno Oficina"
            sessao["etapa"] = "retorno_data_servico"
            enviar_texto(numero, "Qual foi a data do serviço realizado?")
            return

    # ============================================================
    # SERVIÇOS
    # ============================================================

    if etapa == "descricao_servico":
        d["descricao"] = texto

        if sessao.get("veio_de") == "cliente_antigo":
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

        if sessao.get("veio_de") == "cliente_antigo":
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

        if texto_normalizado in ["confirmar"]:
            salvar_via_webapp(sessao)

            if _em_horario_oficina():
                mensagem_final = FECHAMENTO_DENTRO
            else:
                mensagem_final = FECHAMENTO_FORA

            enviar_texto(numero, mensagem_final)

            reset_sessao(numero)  # 👈 depois do envio

            return

        if texto_normalizado in ["editar"]:
            sessao["etapa"] = "pergunta_nome"
            enviar_texto(numero, "Vamos corrigir. Digite seu nome completo:")
            return

        enviar_texto(numero, "Escolha uma opção válida.")
        return
