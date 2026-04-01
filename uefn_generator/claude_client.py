import os
import anthropic
from system_prompt import SYSTEM_PROMPT


def get_api_key() -> str:
    """Obtém a API key do ambiente ou do Streamlit secrets."""
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        try:
            import streamlit as st
            key = st.secrets.get("ANTHROPIC_API_KEY")
        except Exception:
            pass
    return key


def stream_response(messages: list[dict]):
    """
    Faz streaming da resposta do Claude Opus 4.6.
    Usa adaptive thinking para geração de código complexo.
    Yield de chunks de texto à medida que chegam.
    """
    api_key = get_api_key()
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY não encontrada. "
            "Define a variável de ambiente ou cria um ficheiro .env"
        )

    client = anthropic.Anthropic(api_key=api_key)

    with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=8000,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=messages,
    ) as stream:
        for event in stream:
            # Só fazemos yield de texto (ignoramos thinking blocks no stream)
            if (
                event.type == "content_block_delta"
                and hasattr(event.delta, "type")
                and event.delta.type == "text_delta"
            ):
                yield event.delta.text
