# -*- coding: utf-8 -*-
import os
import re
import time
import random
import threading
import unicodedata
import contextvars
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

# Multi-número Meta (mesma WABA) — TS Sullato Auto Service com dois números
# de entrada/saída. WA_PHONE_NUMBER_ID = número principal — usado como
# FALLBACK só em rotinas legadas que não se originam de uma mensagem
# recebida (disparo via Apps Script, chamadas antigas sem
# sender_phone_number_id). O número usado para RESPONDER uma conversa é
# sempre o mesmo que a recebeu (sender_phone_number_id, definido por
# webhook.py a partir de metadata.phone_number_id) — nunca escolhido às
# cegas.
WA_PHONE_NUMBER_ID = os.getenv("WA_PHONE_NUMBER_ID")
WA_PHONE_NUMBER_ID_2 = os.getenv("WA_PHONE_NUMBER_ID_2")
WHATSAPP_TOKEN = os.getenv("WA_ACCESS_TOKEN")
GOOGLE_SHEETS_URL = os.getenv("OFICINA_SHEET_WEBHOOK_URL")
SECRET_KEY = os.getenv("OFICINA_SHEETS_SECRET")

TIMEOUT_SESSAO = 3600
SESSOES = {}

# Guarda, durante o processamento da mensagem atual, qual phone_number_id a
# recebeu — usado só por _url_mensagens() para montar a URL de envio, sem
# alterar a assinatura nem os ~73 pontos onde enviar_texto/enviar_botoes/
# enviar_imagem já são chamadas hoje. contextvars (em vez de uma variável
# global comum) porque continua correto mesmo se o servidor rodar com mais
# de uma thread/worker no futuro.
_phone_number_id_atual = contextvars.ContextVar("_phone_number_id_atual", default=None)


def _url_mensagens() -> str:
    """
    Monta a URL da Graph API para enviar mensagens, usando o
    phone_number_id que recebeu a mensagem em processamento (gravado no
    início de responder_oficina()). Fora desse contexto — rotinas legadas
    que não se originam de uma mensagem recebida — cai no WA_PHONE_NUMBER_ID
    padrão. Nunca escolhe um número por conta própria.
    """
    phone_id = _phone_number_id_atual.get() or WA_PHONE_NUMBER_ID
    return f"https://graph.facebook.com/v20.0/{phone_id}/messages"


def _chave_sessao(numero, sender_phone_number_id=None):
    """
    Chave usada em SESSOES e no histórico da IA (_HIST_IA). Multi-número:
    compõe (sender_phone_number_id, numero) para que o mesmo cliente
    conversando simultaneamente com os dois números da TS Sullato tenha
    sessão/etapa/dados e histórico de IA totalmente independentes. Sem
    sender_phone_number_id (chamadas antigas/testes), mantém o
    comportamento anterior — chave é só o número do cliente.
    """
    if sender_phone_number_id:
        return f"{sender_phone_number_id}:{numero}"
    return numero


def _normalizar_texto(txt):
    """
    Normaliza texto (minúsculas, sem acento) para os detectores de
    intenção novos (Trabalhe Conosco / handoff comercial). Não altera a
    variável `texto` usada no resto do state machine (só minúscula, sem
    remoção de acento) — usada só por esses dois detectores, para não
    arriscar nenhuma comparação já existente no arquivo.
    """
    if not txt:
        return ""
    t = unicodedata.normalize("NFKD", txt.strip().lower())
    return "".join(c for c in t if not unicodedata.combining(c))


_HIST_IA: dict = {}
_HIST_TTL = 3600

def _get_hist_ia(numero, sender_phone_number_id=None):
    chave = _chave_sessao(numero, sender_phone_number_id)
    h = _HIST_IA.get(chave, {})
    if time.time() - h.get("ts", 0) > _HIST_TTL:
        return []
    return list(h.get("msgs", []))

def _add_hist_ia(numero, user_msg, assistant_msg, sender_phone_number_id=None):
    chave = _chave_sessao(numero, sender_phone_number_id)
    h = _HIST_IA.get(chave, {})
    msgs = list(h.get("msgs", []))
    msgs.append({"role": "user", "content": user_msg})
    msgs.append({"role": "assistant", "content": assistant_msg})
    _HIST_IA[chave] = {"msgs": msgs[-10:], "ts": time.time()}

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
        requests.post(_url_mensagens(), json=payload, headers=headers)
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

        requests.post(_url_mensagens(), json=payload, headers=headers)

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
            _url_mensagens(),
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

def reset_sessao(numero, sender_phone_number_id=None):
    chave = _chave_sessao(numero, sender_phone_number_id)
    if chave in SESSOES:
        del SESSOES[chave]

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

def iniciar_sessao(numero, nome_whatsapp, enviar_menu=True, sender_phone_number_id=None):
    SESSOES[_chave_sessao(numero, sender_phone_number_id)] = {
        "etapa": "menu_inicial",
        "inicio": time.time(),
        "acesso_registrado": False,   # 🔥 NOVO CONTROLE
        "dados": {
            "fone": numero,
            "nome_whatsapp": nome_whatsapp,
            "origem_cliente": "chatbot oficina",
        },
        # Reservados para evolução futura — não usados por nenhuma lógica
        # nesta rodada além do que está descrito nos próprios comentários:
        "responsavel_handoff": None,   # {"nome","telefone","link"} quando o handoff comercial (Juliano/Priscila) for acionado nesta sessão
        "trabalhe_conosco": None,      # {"ativo": True, "origem": "whatsapp"} quando a intenção for reconhecida; futuramente pode evoluir para area_interesse/vaga_id/experiencia/curriculo/etapa/dados_candidato sem reconstruir a sessão
        "produto_contexto": None,      # reservado para a futura integração com o catálogo/site (sku, nome, fabricante, aplicacao, especificacoes, compatibilidade, preco, estoque, garantia, url)
    }

    if enviar_menu:
        enviar_texto(
            numero,
            f"Olá {nome_whatsapp}! 👋\n\n"
            "Seja bem-vindo à *TS Sullato Auto Service*.\n\n"
            "💬 Você também pode escrever sua dúvida ou enviar um áudio explicando o que precisa.\n\n"
            "Se preferir, utilize uma das opções abaixo:\n\n"
            "1 – Serviços\n"
            "2 – Peças\n"
            "3 – Pós-venda / Garantia\n"
            "4 – Retorno Oficina\n"
            "5 – Endereço e Contato\n"
            "6 – Mais opções"
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

def obter_responsavel_atendimento():

    responsaveis = [
        {
            "nome": "Juliano",
            "telefone": "(11) 99373-8592",
            "link": "https://wa.me/5511993738592"
        },
        {
            "nome": "Priscila",
            "telefone": "(11) 99408-1931",
            "link": "https://wa.me/5511994081931"
        }
    ]

    random.shuffle(responsaveis)

    return responsaveis

# ============================================================
# MENSAGENS DE FECHAMENTO — OFICINA
# ============================================================

def construir_fechamento(dentro_horario=True):

    responsaveis = obter_responsavel_atendimento()

    contatos = "\n\n".join(
        [
            f"👤 *{r['nome']}*\n"
            f"📲 {r['telefone']}\n"
            f"👉 {r['link']}"
            for r in responsaveis
        ]
    )

    if dentro_horario:

        return (
            "✅ *Atendimento registrado com sucesso!*\n\n"
            "Obrigado por entrar em contato com a "
            "*TS Sullato Auto Service*.\n\n"
            "Nossa equipe recebeu sua solicitação e dará "
            "continuidade ao seu atendimento.\n\n"

            "👥 *Responsáveis pelo atendimento:*\n\n"
            f"{contatos}\n\n"

            "Nossa equipe entrará em contato com você. "
            "Se preferir, você também pode falar diretamente "
            "com um de nossos responsáveis pelos links acima.\n\n"

            "⏰ *Horário de atendimento*\n"
            "Segunda a sexta, das 9h às 18h\n"
            "Sábado, das 9h às 13h\n\n"

            "🔧 *TS Sullato Auto Service*\n"
            "Oficina • Peças • Pós-venda"
        )

    return (
        "✅ *Atendimento registrado com sucesso!*\n\n"
        "Obrigado por entrar em contato com a "
        "*TS Sullato Auto Service*.\n\n"
        "No momento estamos fora do nosso horário de atendimento, "
        "mas sua solicitação já foi recebida.\n\n"
        "Assim que retornarmos, nossa equipe dará continuidade "
        "ao seu atendimento.\n\n"

        "👥 *Responsáveis pelo atendimento:*\n\n"
        f"{contatos}\n\n"

        "Se preferir, você já pode deixar uma mensagem "
        "diretamente para um de nossos responsáveis pelos links acima.\n\n"

        "⏰ *Horário de atendimento*\n"
        "Segunda a sexta, das 9h às 18h\n"
        "Sábado, das 9h às 13h\n\n"

        "🔧 *TS Sullato Auto Service*\n"
        "Oficina • Peças • Pós-venda"
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
# HANDOFF PARA HUMANO
# ============================================================

_HANDOFF_NUMERO = "5511940497678"
_GATILHOS_HANDOFF = ["atendente", "falar com humano", "falar com pessoa", "quero falar com alguem", "quero falar com alguém"]

def _enviar_alerta_handoff(numero_cliente, nome_cliente):
    try:
        msg = (
            f"🔔 *Solicitação de Atendimento Humano*\n\n"
            f"Cliente: {nome_cliente}\n"
            f"WhatsApp: +{numero_cliente}\n"
            f"Via: ChatBot Oficina Sullato\n\n"
            "Por favor, entre em contato!"
        )
        payload = {
            "messaging_product": "whatsapp",
            "to": _HANDOFF_NUMERO,
            "text": {"body": msg}
        }
        headers = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json"
        }
        requests.post(_url_mensagens(), json=payload, headers=headers, timeout=10)
        print("🔔 Alerta handoff Oficina enviado")
    except Exception as e:
        print("❌ Erro alerta handoff:", e)

# ============================================================
# INSTITUCIONAL — "Quem criou este chatbot/sistema?" — intenção própria,
# independente de Serviços/Peças/Comercial/Trabalhe Conosco. Detector
# DETERMINÍSTICO (não depende da IA/Claude estar configurado ou responder
# no formato certo). Nunca aciona Juliano/Priscila nem Trabalhe Conosco.
# Não reinicia nem encerra a sessão — a conversa segue normalmente depois.
# Checada com PRIORIDADE MÁXIMA em texto livre (antes de tudo o mais).
# ============================================================

_GATILHOS_INSTITUCIONAL_CRIADOR = (
    "quem criou", "quem fez esse chatbot", "quem fez este chatbot",
    "quem fez esse bot", "quem fez este bot", "quem fez essa ia",
    "quem fez este sistema", "quem fez esse sistema",
    "quem desenvolveu", "quem e o desenvolvedor", "quem e a desenvolvedora",
    "desenvolvido por quem", "foi feito por quem", "feito por quem",
    "voces que fizeram esse chatbot", "voces que fizeram este chatbot",
    "voces que fizeram esse sistema", "voces que fizeram essa ia",
    "como faco para ter um igual", "como ter um sistema igual",
    "como ter um chatbot igual", "quero um chatbot desse",
    "quero um sistema igual", "quero um chatbot igual", "quero uma ia dessa",
    "voces fazem chatbot", "voces desenvolvem chatbot", "voces desenvolvem sistema",
    "voces desenvolvem esse sistema", "voces desenvolvem esse tipo de sistema",
    "quanto custa um sistema desse", "quanto custa um chatbot desse",
    "quanto custa essa ia", "quanto custa esse sistema", "quanto custa esse chatbot",
)


def _eh_pergunta_institucional_criador(texto_norm: str) -> bool:
    return any(g in texto_norm for g in _GATILHOS_INSTITUCIONAL_CRIADOR)


def _texto_institucional_criador() -> str:
    """Texto fixo aprovado — determinístico, nunca gerado pela IA."""
    return (
        "Ótima pergunta! 🙌\n\n"
        "Este assistente virtual foi desenvolvido por *Anderson R. Sullato*.\n\n"
        "Se você tiver interesse em um sistema similar ou quiser conversar sobre isso, "
        "pode entrar em contato direto com ele:\n\n"
        "📱 *WhatsApp*: (11) 98878-0161 | https://wa.me/5511988780161\n"
        "📧 *Email*: anderson@sullato.com.br | andersonsullato@gmail.com\n\n"
        "Qualquer outra dúvida sobre a Sullato, fico à disposição! 😊"
    )


def _acionar_institucional_criador(numero: str) -> None:
    """Só envia a resposta fixa — não toca em sessao/etapa, nunca reinicia
    nem encerra a sessão. A conversa segue normalmente na próxima mensagem."""
    enviar_texto(numero, _texto_institucional_criador())


# ============================================================
# TRABALHE CONOSCO — intenção própria, independente de Serviços/Peças/
# Comercial. Nunca aciona o handoff Juliano/Priscila. Checada com
# PRIORIDADE MÁXIMA em texto livre (antes do handoff comercial e da IA).
# ============================================================

# Frases (não palavras isoladas) — evita falso positivo de "vaga"/"emprego"/
# "currículo"/"rh" soltos em outro contexto, conforme decisão explícita.
_GATILHOS_TRABALHE_CONOSCO = (
    "trabalhar com voces", "trabalhar na ts", "trabalhar na sullato",
    "trabalhar na oficina", "trabalhar ai", "trabalhar aqui",
    "quero trabalhar", "gostaria de trabalhar",
    "tem vaga", "tem vagas", "abriu vaga", "abriram vaga", "vaga para mecanico",
    "vagas disponiveis", "processo seletivo", "estao contratando",
    "vcs contratam", "voces contratam",
    "oportunidade de emprego", "oportunidade de trabalho", "procurando emprego",
    "tem emprego", "tem alguma vaga",
    "mandar curriculo", "enviar curriculo", "mandar meu curriculo",
    "enviar meu curriculo", "onde envio meu curriculo", "deixar meu curriculo",
    "deixar curriculo", "trabalhe conosco", "trabalhem conosco",
    "falar com o rh", "falar com rh", "contato do rh", "setor de rh",
)


def _eh_intencao_trabalhe_conosco(texto_norm: str) -> bool:
    return any(g in texto_norm for g in _GATILHOS_TRABALHE_CONOSCO)


def _texto_trabalhe_conosco() -> str:
    """Mensagem própria da TS Sullato Auto Service — autoral, não copiada
    do texto de Trabalhe Conosco do chatbot Sullato (referência só de
    arquitetura/comportamento, não de conteúdo). Simplificada: entrega
    contato direto do responsável (Érico) e e-mail de currículos, sem
    coletar nome/área (não havia processamento algum dessa coleta) e sem
    afirmar vaga aberta nem prometer entrevista/retorno."""
    return (
        "Que legal seu interesse em fazer parte da equipe da "
        "*TS Sullato Auto Service*! 🔧\n\n"
        "Você pode enviar seu currículo ou falar diretamente com o responsável:\n\n"
        "👤 *Érico*\n"
        "📱 WhatsApp: https://wa.me/5511940497678\n\n"
        "📧 *Currículos:*\n"
        "tssullatoautoservice@gmail.com\n\n"
        "Se preferir, envie seu currículo por e-mail com a área de interesse. Boa sorte! 😊"
    )


def _acionar_trabalhe_conosco(numero: str, sessao: dict) -> None:
    """
    Registra a intenção na sessão (preparação para evolução futura — SEM
    criar state machine de candidato, SEM formulário, SEM Sheets, SEM
    encaminhamento nesta rodada) e envia a mensagem ao candidato. Não
    bloqueia nem "prende" as mensagens seguintes — a próxima mensagem do
    cliente volta a ser reavaliada normalmente do zero.
    """
    sessao["trabalhe_conosco"] = {"ativo": True, "origem": "whatsapp"}
    enviar_texto(numero, _texto_trabalhe_conosco())


# ============================================================
# HANDOFF COMERCIAL — PEÇAS/SERVIÇOS (Juliano/Priscila)
# ============================================================
# Sinais FORTES o bastante para justificar intervenção humana — mencionar
# uma peça/serviço, por si só, NÃO aciona isso (a IA pode conversar
# livremente sobre o assunto antes). Reflete o item 5 revisado: intenção
# concreta de compra, orçamento/cotação, confirmação de disponibilidade/
# preço quando depende de humano, confirmação técnica de aplicação/
# compatibilidade, instalação, agendamento, ou pedido explícito de falar
# com vendedor/consultor comercial (nunca "atendente" sozinho — isso já é
# coberto pelo handoff genérico ao Érico, _GATILHOS_HANDOFF, mecanismo
# separado e intocado).
_GATILHOS_HANDOFF_COMERCIAL = (
    # procura ativa de peça/serviço específico (bucket B — diagnóstico real:
    # "estou procurando pastilhas de freio para uma Master 2022. Vocês
    # trabalham com essa peça?" não batia em nenhum grupo abaixo; esta é a
    # forma mais comum de um cliente real abrir a conversa pedindo algo)
    "estou procurando", "procurando por", "procuro", "estou atras de",
    "preciso de", "precisando de", "estou precisando de",
    "voces trabalham com", "vcs trabalham com", "trabalham com",
    "voces tem", "vcs tem", "voces vendem", "vcs vendem", "vendem",
    "voces possuem", "vcs possuem",
    # intenção concreta de compra
    "quero comprar", "quero fechar", "vou levar", "quero levar",
    "fechar negocio", "fechar pedido",
    # orçamento/cotação
    "orcamento", "cotacao", "quanto custa", "qual o valor", "qual o preco",
    "quanto fica", "quanto sai", "me passa o preco", "me passa o valor",
    # confirmação de disponibilidade/preço/aplicação quando depende de humano
    "tem em estoque", "tem disponivel", "confirmar disponibilidade",
    "confirmar estoque", "serve no meu carro", "e compativel",
    "confirma se serve", "confirmar aplicacao",
    # instalação
    "voces instalam", "fazem a instalacao", "quero instalar",
    # agendamento
    "quero agendar", "posso agendar", "marcar um horario", "marcar horario",
    # solicitação explícita de vendedor/consultor comercial
    "falar com um vendedor", "falar com o vendedor", "falar com consultor",
    "falar com o comercial", "falar com a equipe comercial",
)

# Perguntas puramente conceituais/informativas (bucket A) — checadas ANTES
# do handoff comercial. Mesmo que a mensagem contenha uma palavra de
# "procura" por perto (ex.: "procurando saber para que serve a pastilha"),
# uma pergunta claramente conceitual vence e a IA responde normalmente,
# sem handoff prematuro. Frases, não palavras soltas.
_GATILHOS_PERGUNTA_INFORMATIVA = (
    "para que serve", "para que servem", "o que e", "o que sao", "o que faz",
    "qual a funcao", "qual e a funcao", "quais os sintomas",
    "quais sao os sintomas", "qual a diferenca entre", "qual a diferenca",
    "como funciona", "quando trocar", "de quanto em quanto tempo",
)


def _eh_pergunta_informativa(texto_norm: str) -> bool:
    return any(g in texto_norm for g in _GATILHOS_PERGUNTA_INFORMATIVA)


# Perguntas institucionais que legitimamente usam "tem" (horário, endereço,
# estacionamento, etc.) — excluídas ANTES de considerar o "tem" solto
# (bare) como sinal comercial. Também protege frases já existentes como
# "vocês tem" contra esse mesmo tipo de falso positivo (ex.: "vocês tem
# horário aos sábados?" não deve virar handoff).
_GATILHOS_PERGUNTA_INSTITUCIONAL = (
    "tem horario", "tem atendimento", "tem expediente",
    "tem estacionamento", "tem wifi", "tem wi-fi", "tem banheiro",
    "tem cafe", "tem cafezinho", "tem espera", "tem fila",
    "tem outra loja", "tem outra unidade", "tem filial",
    "tem endereco", "tem contato", "tem telefone", "tem whatsapp",
    "tem instagram", "tem facebook", "tem site", "tem garantia",
    "tem alguem atendendo", "tem alguem ai", "tem alguem disponivel",
    # Mesmos tópicos institucionais acima, mas com "possuem" em vez de
    # "tem" — sem prefixo "voces/vcs" de propósito: "possuem X" já cobre
    # "voces possuem X" e "vcs possuem X" pela mesma substring (achado ao
    # investigar "vcs possuem estacionamento?", que já falhava mesmo antes
    # desta correção com "voces possuem estacionamento?").
    "possuem horario", "possuem atendimento", "possuem expediente",
    "possuem estacionamento", "possuem wifi", "possuem wi-fi", "possuem banheiro",
    "possuem cafe", "possuem cafezinho", "possuem espera", "possuem fila",
    "possuem outra loja", "possuem outra unidade", "possuem filial",
    "possuem endereco", "possuem contato", "possuem telefone", "possuem whatsapp",
    "possuem instagram", "possuem facebook", "possuem site", "possuem garantia",
    "possuem alguem atendendo", "possuem alguem ai", "possuem alguem disponivel",
    # "vendem" não faz sentido genérico para tópicos institucionais (não
    # se "vende" horário/estacionamento/wifi), mas a frase de teste
    # específica precisa ficar protegida contra o gatilho comercial
    # "voces vendem"/"vcs vendem".
    "vendem algum servico de estacionamento",
)

# "tem" como palavra isolada (bare) — ex.: "Tem pastilha para Master?", sem
# o pronome "vocês/vcs" antes. Usa \b (limite de palavra) de propósito: um
# "in" simples bateria em qualquer palavra que contenha as letras "tem"
# (também, tempo, contém, mantém, tentar...), o que geraria falso positivo
# em quase qualquer frase. Só considerado quando NÃO for pergunta
# institucional nem informativa (checadas antes).
_BARE_TEM_RE = re.compile(r"\btem\b")


def _eh_pergunta_institucional(texto_norm: str) -> bool:
    return any(g in texto_norm for g in _GATILHOS_PERGUNTA_INSTITUCIONAL)


def _eh_sinal_handoff_comercial(texto_norm: str) -> bool:
    if _eh_pergunta_informativa(texto_norm) or _eh_pergunta_institucional(texto_norm):
        return False
    if any(g in texto_norm for g in _GATILHOS_HANDOFF_COMERCIAL):
        return True
    return bool(_BARE_TEM_RE.search(texto_norm))


_RESPONSAVEIS_HANDOFF = [
    {"nome": "Juliano",  "telefone": "(11) 99373-8592", "link": "https://wa.me/5511993738592"},
    {"nome": "Priscila", "telefone": "(11) 99408-1931", "link": "https://wa.me/5511994081931"},
]
_RODIZIO_INDICE_HANDOFF = 0
_LOCK_RODIZIO_HANDOFF = threading.Lock()


def _responsavel_da_vez() -> dict:
    """Responsável que receberia o próximo lead, sem avançar o índice."""
    with _LOCK_RODIZIO_HANDOFF:
        return _RESPONSAVEIS_HANDOFF[_RODIZIO_INDICE_HANDOFF % len(_RESPONSAVEIS_HANDOFF)]


def _avancar_rodizio_handoff() -> None:
    """Avança o índice do rodízio — chamar só após envio confirmado ao
    responsável. threading.Lock() protege contra concorrência de threads
    dentro do mesmo processo (não cobre múltiplos workers/processos —
    aceito conforme definido: 1 worker no Render, sem persistência
    externa; após restart o índice volta a 0 e o próximo lead vai para
    Juliano)."""
    global _RODIZIO_INDICE_HANDOFF
    with _LOCK_RODIZIO_HANDOFF:
        _RODIZIO_INDICE_HANDOFF = (_RODIZIO_INDICE_HANDOFF + 1) % len(_RESPONSAVEIS_HANDOFF)


# Nome do template aprovado pela Meta para avisar Juliano/Priscila
# automaticamente. Template já criado, AINDA EM ANÁLISE — NÃO adivinhar
# nem inventar o nome. Configure via variável de ambiente assim que a Meta
# aprovar; nenhum código precisa mudar depois disso, só a variável.
TEMPLATE_NOVO_ATENDIMENTO_RESPONSAVEL = os.getenv("TEMPLATE_NOVO_ATENDIMENTO_RESPONSAVEL")


def _enviar_template_novo_atendimento_responsavel(numero_responsavel, nome_cliente, interesse, veiculo, link_cliente) -> bool:
    """
    Envia o template aprovado (Estrutura combinada: 4 variáveis — nome,
    interesse, veículo, link do cliente) para abrir/reabrir a janela de
    conversa com o responsável. Só dispara quando
    TEMPLATE_NOVO_ATENDIMENTO_RESPONSAVEL já estiver configurado — antes
    disso, não faz nada (retorna False) e quem chama segue com o texto
    livre. Usa _url_mensagens() — respeita o número que recebeu a
    conversa, igual a todo o resto do multi-número.
    """
    if not TEMPLATE_NOVO_ATENDIMENTO_RESPONSAVEL:
        return False
    try:
        payload = {
            "messaging_product": "whatsapp",
            "to": numero_responsavel,
            "type": "template",
            "template": {
                "name": TEMPLATE_NOVO_ATENDIMENTO_RESPONSAVEL,
                "language": {"code": "pt_BR"},
                "components": [
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": nome_cliente or "Cliente"},
                            {"type": "text", "text": interesse},
                            {"type": "text", "text": veiculo},
                            {"type": "text", "text": link_cliente},
                        ],
                    }
                ],
            },
        }
        headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
        r = requests.post(_url_mensagens(), json=payload, headers=headers, timeout=30)
        print("📤 Template novo atendimento (responsável):", r.status_code, r.text)
        return 200 <= r.status_code < 300
    except Exception as e:
        print("❌ Erro ao enviar template novo atendimento (responsável):", e)
        return False


def _enviar_texto_com_status(numero, texto) -> bool:
    """
    Variante de enviar_texto() que informa se o envio teve sucesso — usada
    só na notificação de handoff ao responsável, para decidir se o
    rodízio pode avançar. enviar_texto() não é alterada (mesmo padrão já
    usado no chatbot Sullato: _enviar_mensagem_com_status).
    """
    try:
        payload = {"messaging_product": "whatsapp", "to": numero, "text": {"body": texto}}
        headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
        r = requests.post(_url_mensagens(), json=payload, headers=headers, timeout=30)
        print("📤 Aviso ao responsável (texto livre):", r.status_code, r.text)
        return 200 <= r.status_code < 300
    except Exception as e:
        print("❌ Erro ao enviar aviso ao responsável:", e)
        return False


def _notificar_responsavel_handoff(responsavel, nome_cliente, interesse, veiculo, link_cliente) -> bool:
    """
    Avisa o responsável sobre o novo lead comercial. Tenta o template
    aprovado primeiro (só dispara de fato quando configurado); em
    qualquer caso, também garante o aviso em texto livre com o resumo e o
    link clicável do cliente (sujeito à janela de 24h da Meta enquanto o
    template não está pronto). True se pelo menos um dos dois canais foi
    confirmado.
    """
    numero_responsavel = responsavel["link"].replace("https://wa.me/", "").strip()

    template_ok = _enviar_template_novo_atendimento_responsavel(
        numero_responsavel, nome_cliente, interesse, veiculo, link_cliente
    )
    if TEMPLATE_NOVO_ATENDIMENTO_RESPONSAVEL and not template_ok:
        print(f"⚠️ Falha ao enviar template ao responsável {responsavel['nome']} — seguindo com texto livre.")

    texto_lead = (
        "🔔 Novo atendimento – TS Sullato Auto Service\n\n"
        f"Cliente: {nome_cliente or 'não informado'}\n"
        f"Interesse: {interesse}\n"
        f"Veículo: {veiculo}\n\n"
        f"📲 Falar com o cliente:\n{link_cliente}\n\n"
        "Solicitação recebida pelo atendimento automático da TS Sullato Auto Service."
    )
    texto_ok = _enviar_texto_com_status(numero_responsavel, texto_lead)

    return template_ok or texto_ok


def _acionar_handoff_comercial(numero: str, nome_whatsapp: str, sessao: dict, texto_gatilho: str) -> None:
    """
    Encaminha o cliente para Juliano ou Priscila (rodízio) quando um sinal
    comercial forte é identificado em texto livre. Idempotente por sessão
    (sessao["responsavel_handoff"]): se já houver responsável atribuído
    nesta conversa, reaproveita sem sortear nem notificar de novo — evita
    lead duplicado. Nunca inventa preço/estoque/prazo/diagnóstico: só
    reaproveita dados que já existem na sessão (marca_modelo do formulário
    longo, se já preenchido; produto_contexto, quando existir no futuro).
    """
    ja_atribuido = bool(sessao.get("responsavel_handoff"))
    responsavel = sessao["responsavel_handoff"] if ja_atribuido else _responsavel_da_vez()

    dados = sessao.get("dados") or {}
    produto_contexto = sessao.get("produto_contexto") or {}
    veiculo = produto_contexto.get("nome") or dados.get("marca_modelo") or "não especificado"
    interesse = (texto_gatilho or "").strip()[:200] or "não especificado"
    numero_normalizado = "".join(ch for ch in (numero or "") if ch.isdigit())
    link_cliente = f"https://wa.me/{numero_normalizado}"

    if not ja_atribuido:
        enviado = _notificar_responsavel_handoff(responsavel, nome_whatsapp, interesse, veiculo, link_cliente)
        if not enviado:
            print(f"⚠️ Falha ao notificar {responsavel['nome']} — handoff NÃO concluído, tentará de novo na próxima mensagem.")
            return
        sessao["responsavel_handoff"] = responsavel
        _avancar_rodizio_handoff()

    enviar_texto(
        numero,
        f"Perfeito, {nome_whatsapp}! 👍\n\n"
        f"Vou encaminhar sua solicitação para o(a) {responsavel['nome']}, da nossa equipe.\n"
        "Ele(a) vai dar continuidade ao seu atendimento.\n\n"
        f"📱 {responsavel['nome']}: {responsavel['link']}"
    )


# ============================================================
# FLUXO PRINCIPAL
# ============================================================

def responder_oficina(numero, texto_digitado, nome_whatsapp, sender_phone_number_id=None):

    # Multi-número Meta: grava o phone_number_id que recebeu esta mensagem
    # para toda a duração do processamento — é ele que enviar_texto()/
    # enviar_botoes()/enviar_imagem()/_enviar_alerta_handoff() vão usar via
    # _url_mensagens(), sem precisar de nenhum parâmetro extra nelas.
    _phone_number_id_atual.set(sender_phone_number_id)
    print(
        f"📞 Respondendo cliente {numero} pelo phone_number_id="
        f"{sender_phone_number_id or WA_PHONE_NUMBER_ID} "
        f"({'recebido' if sender_phone_number_id else 'fallback padrão'})"
    )

    texto = (texto_digitado or "").strip().lower()

    # ============================================================
    # PRIMEIRO ACESSO / SAUDAÇÃO
    # ============================================================

    if texto in ["oi", "ola", "olá", "menu", "inicio", "início"]:

        reset_sessao(numero, sender_phone_number_id)
        iniciar_sessao(numero, nome_whatsapp, enviar_menu=True, sender_phone_number_id=sender_phone_number_id)

        sessao = SESSOES[_chave_sessao(numero, sender_phone_number_id)]

        # REGISTRA IMEDIATAMENTE O ACESSO NA PLANILHA
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

            requests.post(
                GOOGLE_SHEETS_URL,
                json=payload,
                timeout=10
            )

            sessao["acesso_registrado"] = True

            print(
                f"✅ ACESSO INICIAL REGISTRADO: "
                f"{numero} - {nome_whatsapp}"
            )

        except Exception as e:
            print("❌ Erro registrar acesso inicial:", e)

        return
    
    # HANDOFF — detectar antes de qualquer outra lógica
    
    if any(g in texto for g in _GATILHOS_HANDOFF):
        _enviar_alerta_handoff(numero, nome_whatsapp)
        enviar_texto(
            numero,
            "Entendido! 👍 Já avisamos nossa equipe.\n\n"
            "Em breve um atendente vai entrar em contato com você.\n\n"
            "Se preferir, fale diretamente com o Érico:\n"
            "👉 https://wa.me/5511940497678"
        )
        reset_sessao(numero, sender_phone_number_id)
        return

    # ============================================================
    # IMAGEM — resposta específica
    # ============================================================

    if texto == "__imagem__":
        enviar_texto(
            numero,
            "Recebemos sua imagem! 📸\n\n"
            "Infelizmente não consigo visualizar fotos por aqui.\n\n"
            "Pode descrever em texto o serviço ou problema que precisa? Será um prazer ajudar! 😊"
        )
        return

    # ============================================================
    # MÍDIAS / ENTRADAS SEM TEXTO
    # ============================================================

    if texto in ["__video__", "__documento__", "__mensagem__"]:

        if _chave_sessao(numero, sender_phone_number_id) not in SESSOES:

            iniciar_sessao(numero, nome_whatsapp, sender_phone_number_id=sender_phone_number_id)

            try:
                payload = {
                    "secret": SECRET_KEY,
                    "route": "chatbot",
                    "dados": {
                        "fone": numero,
                        "nome_whatsapp": nome_whatsapp,
                        "interesse_inicial": texto,
                        "tipo_registro": "Acesso Midia",
                        "origem": "whatsapp"
                    }
                }

                requests.post(
                    GOOGLE_SHEETS_URL,
                    json=payload,
                    timeout=10
                )

            except Exception as e:
                print("Erro registrar acesso mídia:", e)

        enviar_texto(
            numero,
            "Recebemos sua mensagem 👍\n\n"
            "Você também pode enviar um áudio ou descrever sua necessidade em texto.\n\n"
            "Escolha uma opção:\n"
            "1 – Serviços\n"
            "2 – Peças\n"
            "3 – Pós-venda / Garantia\n"
            "4 – Retorno Oficina\n"
            "5 – Endereço e Contato\n"
            "6 – Mais opções"
        )

        return

    agora = time.time()
    # ============================================================
    # PRIMEIRO CONTATO OU NOVA SESSÃO
    # ============================================================

    if _chave_sessao(numero, sender_phone_number_id) not in SESSOES:

        tem_conteudo = bool(texto)

        # Exibe menu só quando não há conteúdo; áudio/texto livre já traz intenção
        iniciar_sessao(numero, nome_whatsapp, enviar_menu=not tem_conteudo, sender_phone_number_id=sender_phone_number_id)

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

        if not tem_conteudo:
            return

    sessao = SESSOES[_chave_sessao(numero, sender_phone_number_id)]

    # ============================================================
    # TIMEOUT DE SESSÃO
    # ============================================================

    if agora - sessao.get("inicio", 0) > TIMEOUT_SESSAO:

        enviar_texto(numero, "Sessão expirada. Vamos recomeçar! 👋")

        # Encerra sessão anterior
        reset_sessao(numero, sender_phone_number_id)

        # Inicia nova sessão
        iniciar_sessao(numero, nome_whatsapp, sender_phone_number_id=sender_phone_number_id)

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

        if texto not in [
            "1", "btn_servicos", "2", "btn_pecas", "3", "btn_pos_venda", "4", "btn_retorno",
            "5", "btn_endereco", "6", "btn_mais_opcoes", "6.1", "btn_trabalhe_conosco",
        ]:
            # Prioridade (definida e aprovada):
            # 1) INSTITUCIONAL "quem criou" — nunca aciona handoff nem
            #    Trabalhe Conosco; não reinicia/encerra a sessão.
            # 2) TRABALHE_CONOSCO — nunca aciona o handoff comercial.
            # 3) comandos/fluxos estruturados — já tratados acima (fora deste
            #    bloco de texto livre), nada a fazer aqui.
            # 4) sinal comercial forte (peças/serviços) — Juliano/Priscila.
            # 5) IA / conversa livre normal.
            texto_norm = _normalizar_texto(texto_digitado)

            if _eh_pergunta_institucional_criador(texto_norm):
                _acionar_institucional_criador(numero)
                return

            if _eh_intencao_trabalhe_conosco(texto_norm):
                _acionar_trabalhe_conosco(numero, sessao)
                return

            if _eh_sinal_handoff_comercial(texto_norm):
                _acionar_handoff_comercial(numero, nome_whatsapp, sessao, texto_digitado)
                return

            resposta_ia = None
            try:
                from responder_ia import responder_com_ia
                hist = _get_hist_ia(numero, sender_phone_number_id)
                resposta_ia = responder_com_ia(texto_digitado, nome_whatsapp, historico=hist)
            except Exception:
                pass
            if resposta_ia:
                _add_hist_ia(numero, texto_digitado, resposta_ia, sender_phone_number_id)
                enviar_texto(numero, resposta_ia)
                enviar_texto(
                    numero,
                    "Para continuar, escolha uma opção:\n"
                    "1 – Serviços\n2 – Peças\n3 – Pós-venda / Garantia\n4 – Retorno Oficina\n5 – Endereço e Contato\n6 – Mais opções"
                )
                return
            else:
                enviar_texto(
                    numero,
                    "Olá! Para te atender melhor, escolha uma opção:\n"
                    "1 – Serviços\n2 – Peças\n3 – Pós-venda / Garantia\n4 – Retorno Oficina\n5 – Endereço e Contato\n6 – Mais opções"
                )
                return

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
                "👉 https://wa.me/5511994081931\n"
                "📸 Instagram: https://www.instagram.com/tssullatoautoservice/\n\n"
                "🔧 *Érico*: https://wa.me/5511940497678\n"
            )

            enviar_texto(numero, "Se precisar de ajuda, estou aqui! 😊")
            reset_sessao(numero, sender_phone_number_id)
            return

        if texto in ["6", "btn_mais_opcoes"]:
            enviar_texto(
                numero,
                "Mais opções:\n\n"
                "6.1 – Trabalhe Conosco"
            )
            return

        if texto in ["6.1", "btn_trabalhe_conosco"]:
            _acionar_trabalhe_conosco(numero, sessao)
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
        enviar_texto(
            numero,
            "Digite a *marca/modelo, ano fab/mod e placa* do veículo.\n\n"
            "Exemplo:\n"
            "Fiat Strada 2023/2024 - ABC1D23"
        )
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

            mensagem_final = construir_fechamento(
                dentro_horario=_em_horario_oficina()
            )

            enviar_texto(numero, mensagem_final)

            reset_sessao(numero, sender_phone_number_id)  # 👈 depois do envio

            return

        if texto_normalizado in ["editar"]:
            sessao["etapa"] = "pergunta_nome"
            enviar_texto(numero, "Vamos corrigir. Digite seu nome completo:")
            return

        enviar_texto(numero, "Escolha uma opção válida.")
        return
