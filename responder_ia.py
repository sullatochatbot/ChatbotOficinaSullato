import os
from typing import Optional

def responder_com_ia(mensagem: str, nome: Optional[str] = None) -> Optional[str]:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return None

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        sistema = (
            "Você é o assistente virtual da Sullato Oficina e Peças, em São Paulo. "
            "Localizada na Av. Amador Bueno da Veiga, 4222 – CEP 03652-000. "
            "Serviços: revisão, manutenção preventiva e corretiva, peças originais e pós-venda de veículos de passeio e utilitários. "
            "Contato da oficina: (11) 20922304 | WhatsApp: https://wa.me/5511994081931 | Érico: https://wa.me/5511940497678. "
            "Horário: segunda a sexta das 9h às 18h, sábado das 9h às 13h. "
            "Responda sempre em português brasileiro, com tom simpático e direto, em 1 a 3 frases. "
            "Nunca invente preços ou prazos específicos — oriente o cliente a entrar em contato ou use o menu. "
            "Quando fizer sentido, peça que o cliente escolha uma opção no menu."
        )

        usuario = mensagem if not nome else f"[Cliente: {nome}]\n{mensagem}"

        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            system=sistema,
            messages=[{"role": "user", "content": usuario}],
        )
        texto = (resp.content[0].text or "").strip()
        return texto if texto else None

    except Exception as e:
        print("⚠️ Claude indisponível:", e)
        return None
