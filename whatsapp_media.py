"""
Download de mídia (fotos) enviadas pelo WhatsApp.

Diferente de mensagens de texto, quando alguém manda uma FOTO, a Meta
não entrega o arquivo direto no webhook — ela manda só um "media id".
É preciso fazer duas chamadas:
  1. Consultar a URL temporária de download a partir do media id
  2. Baixar o conteúdo binário dessa URL (também exige o token, é uma
     URL protegida, não pública)
"""

import os
import requests

GRAPH_API_VERSION = "v21.0"


def baixar_midia(media_id: str) -> tuple[bytes, str]:
    """
    Baixa uma mídia do WhatsApp a partir do seu media id.
    Retorna (bytes_da_imagem, mime_type).
    """
    access_token = os.environ["META_ACCESS_TOKEN"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # 1. Descobre a URL de download temporária
    url_info = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{media_id}"
    resposta_info = requests.get(url_info, headers=headers, timeout=10)
    resposta_info.raise_for_status()
    info = resposta_info.json()

    url_download = info["url"]
    mime_type = info["mime_type"]

    # 2. Baixa o conteúdo binário (a URL também exige o token)
    resposta_arquivo = requests.get(url_download, headers=headers, timeout=20)
    resposta_arquivo.raise_for_status()

    return resposta_arquivo.content, mime_type
