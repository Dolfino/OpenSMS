"""
spintax.py - Motor de Spintax e Interpolador de Variaveis de Leads.
Permite variacao dinamica de vocabulario para evitar deteccao por hash de conteudo identico.
"""

import re
import random
from typing import Dict, Any, List
from core.gsm import sanitize_for_gsm7, calculate_sms_segments


def parse_spintax(text: str) -> str:
    """
    Processa spintax suportando aninhamento.
    Exemplo: "{Ola|Oi|Bom dia} {nome}, {seu codigo|sua chave} e {codigo}."
    """
    pattern = re.compile(r"\{([^{}]+)\}")
    while True:
        match = pattern.search(text)
        if not match:
            break
        choices = match.group(1).split("|")
        text = text[:match.start()] + random.choice(choices) + text[match.end():]
    return text


def render_message(
    template: str,
    lead_data: Dict[str, Any],
    auto_sanitize_gsm7: bool = True,
    opt_out_suffix: str = " P/ sair responda SAIR"
) -> str:
    """
    Renderiza uma mensagem completa para um contato especifico:
    1. Resolve spintax aleatorio
    2. Substitui variaveis do lead (ex: {nome}, {codigo}, etc.)
    3. Anexa o sufixo de Opt-out se solicitado e ainda nao presente
    4. Aplica sanitizacao GSM-7
    """
    # 1. Spintax
    content = parse_spintax(template)

    # 2. Interpolação de variáveis
    for key, val in lead_data.items():
        placeholder = f"{{{key}}}"
        content = content.replace(placeholder, str(val))

    # Limpa placeholders que nao foram encontrados no lead
    content = re.sub(r"\{[a-zA-Z0-9_]+\}", "", content)

    # 3. Sufixo Opt-out (LGPD)
    if opt_out_suffix and opt_out_suffix.strip() not in content:
        content = f"{content.strip()}{opt_out_suffix}"

    # 4. Sanitização GSM-7
    if auto_sanitize_gsm7:
        content = sanitize_for_gsm7(content)

    return content


def analyze_template_variations(
    template: str,
    sample_lead: Dict[str, Any],
    max_samples: int = 100
) -> dict:
    """
    Analisa um template gerando amostras de variacao para determinar
    se alguma combinacao ultrapassa o limite critico de 160 caracteres.
    """
    lengths = []
    exceeds_count = 0
    sample_outputs = []

    for _ in range(max_samples):
        rendered = render_message(template, sample_lead)
        metrics = calculate_sms_segments(rendered)
        lengths.append(metrics["char_count"])
        if metrics["exceeds_160_chars"]:
            exceeds_count += 1
        if len(sample_outputs) < 3:
            sample_outputs.append({
                "text": rendered,
                "length": metrics["char_count"],
                "segments": metrics["segments"]
            })

    min_len = min(lengths) if lengths else 0
    max_len = max(lengths) if lengths else 0
    avg_len = sum(lengths) / len(lengths) if lengths else 0

    return {
        "min_length": min_len,
        "max_length": max_len,
        "avg_length": round(avg_len, 1),
        "safe_within_160": max_len <= 160,
        "samples_exceeding_160": exceeds_count,
        "sample_previews": sample_outputs
    }
