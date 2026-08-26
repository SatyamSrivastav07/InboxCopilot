from __future__ import annotations

from functools import lru_cache

from langchain_core.runnables import Runnable
from langchain_mistralai import ChatMistralAI

from app.config import get_settings
from app.genai.chains import build_analysis_chain
from app.schemas.email import EmailAnalysis, EmailInput


class EmailAnalyzer:
    def __init__(
        self, chain: Runnable[EmailInput, EmailAnalysis] | None = None
    ) -> None:
        self._chain = chain

    def analyze(self, email: EmailInput) -> EmailAnalysis:
        if self._chain is None:
            settings = get_settings()
            model = ChatMistralAI(
                api_key=settings.require_mistral_api_key(),
                model=settings.mistral_model,
                temperature=0,
                max_retries=2,
            )
            self._chain = build_analysis_chain(model)
        return self._chain.invoke(email)


@lru_cache
def get_email_analyzer() -> EmailAnalyzer:
    # Model construction is intentionally lazy so malformed requests can return
    # validation errors without requiring AI-provider configuration.
    return EmailAnalyzer()
