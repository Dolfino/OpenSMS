"""
gsm.py - Sanitizador e Calculador de Segmentos GSM-7 para SMS.
Garante que o texto respeite os limites estritos das operadoras (160 caracteres).
"""

import unicodedata
import re

# Caracteres padrao do conjunto basico GSM 03.38 (7-bit)
GSM_BASIC = set(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ\x1bÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)

# Caracteres de extensao GSM (contam como 2 caracteres cada)
GSM_EXTENDED = set("|^€{}[]~\\")

# Mapeamento para substituicoes comuns em portugues
REPLACEMENTS = {
    'ã': 'a', 'Ã': 'A',
    'õ': 'o', 'Õ': 'O',
    'ç': 'c', 'Ç': 'C',
    'á': 'a', 'Á': 'A',
    'é': 'e', 'É': 'E',
    'í': 'i', 'Í': 'I',
    'ó': 'o', 'Ó': 'O',
    'ú': 'u', 'Ú': 'U',
    'â': 'a', 'Â': 'A',
    'ê': 'e', 'Ê': 'E',
    'ô': 'o', 'Ô': 'O',
    '–': '-', '—': '-',
    '“': '"', '”': '"',
    '‘': "'", '’': "'",
    '«': '"', '»': '"',
}


def sanitize_for_gsm7(text: str, remove_emojis: bool = True) -> str:
    """
    Normaliza o texto para garantir compatibilidade com GSM-7:
    - Converte acentos complexos para equivalentes simples
    - Remove emojis (que forçariam codificação UCS-2 de 70 caracteres)
    - Substitui aspas e travessoes tipograficos
    """
    if not text:
        return ""

    for k, v in REPLACEMENTS.items():
        text = text.replace(k, v)

    if remove_emojis:
        emoji_pattern = re.compile(
            r"[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\ud83c-\ud83e][\ud000-\udfff]",
            flags=re.UNICODE,
        )
        text = emoji_pattern.sub("", text)

    normalized = unicodedata.normalize("NFKD", text)
    cleaned = "".join([c for c in normalized if not unicodedata.combining(c)])

    result = []
    for char in cleaned:
        if char in GSM_BASIC or char in GSM_EXTENDED or ord(char) < 128:
            result.append(char)
        else:
            result.append(" ")

    return "".join(result).strip()


def calculate_sms_segments(text: str) -> dict:
    """
    Calcula o tamanho real do SMS e o numero de partes (segmentos):
    - Se codificacao for GSM-7:
        1 segmento: ate 160 caracteres
        Multiplos segmentos: 153 caracteres por parte
    - Se contiver caracteres UCS-2 (nao GSM):
        1 segmento: ate 70 caracteres
        Multiplos segmentos: 67 caracteres por parte
    """
    is_gsm7 = True
    char_count = 0

    for char in text:
        if char in GSM_EXTENDED:
            char_count += 2
        elif char in GSM_BASIC or ord(char) < 128:
            char_count += 1
        else:
            is_gsm7 = False
            char_count += 1

    if is_gsm7:
        encoding = "GSM-7"
        if char_count <= 160:
            segments = 1
            remaining_in_segment = 160 - char_count
        else:
            segments = (char_count + 152) // 153
            remaining_in_segment = 153 - (char_count % 153)
            if remaining_in_segment == 153:
                remaining_in_segment = 0
    else:
        encoding = "UCS-2 (UTF-16)"
        if char_count <= 70:
            segments = 1
            remaining_in_segment = 70 - char_count
        else:
            segments = (char_count + 66) // 67
            remaining_in_segment = 67 - (char_count % 67)
            if remaining_in_segment == 67:
                remaining_in_segment = 0

    return {
        "char_count": char_count,
        "segments": segments,
        "encoding": encoding,
        "is_single_segment": segments == 1,
        "remaining_in_current_segment": remaining_in_segment,
        "exceeds_160_chars": char_count > 160,
    }
