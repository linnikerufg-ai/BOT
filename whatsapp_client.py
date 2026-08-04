"""
Envio de mensagens via Meta WhatsApp Cloud API.

Diferente do Twilio, a Meta não aceita resposta inline no webhook —
é preciso fazer uma chamada separada pra API do WhatsApp Business
pra mandar a mensagem de volta pro usuário.
"""

import os
import requests

GRAPH_API_VERSION = "v21.0"


def enviar_mensagem(destinatario: str, texto: str) -> None:
    """
    Envia uma mensagem de texto para o número informado via Meta Cloud API.

    destinatario: número no formato internacional sem símbolos, ex: '5511999999999'
    texto: conteúdo da mensagem a enviar
    """
    phone_number_id = os.environ["META_PHONE_NUMBER_ID"]
    access_token = os.environ["META_ACCESS_TOKEN"]

    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_number_id}/messages"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": destinatario,
        "type": "text",
        "text": {"body": texto},
    }

    resposta = requests.post(url, headers=headers, json=payload, timeout=10)

    if resposta.status_code >= 400:
        print(f"Erro ao enviar mensagem: {resposta.status_code} - {resposta.text}")
    resposta.raise_for_status()
