from __future__ import annotations

from langchain_mistralai import MistralAIEmbeddings

from app.config import Settings


def build_embeddings(settings: Settings) -> MistralAIEmbeddings:
    return MistralAIEmbeddings(
        model="mistral-embed",
        api_key=settings.require_mistral_api_key(),
    )

