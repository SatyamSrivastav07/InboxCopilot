from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import ConfigurationError
from app.core.metrics import log_timing
from app.genai.analyzer import EmailAnalyzer, get_email_analyzer
from app.schemas.email import EmailAnalysis, EmailInput

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["email-analysis"])


@router.post("/analyze-email", response_model=EmailAnalysis)
def analyze_email(
    email: EmailInput,
    analyzer: Annotated[EmailAnalyzer, Depends(get_email_analyzer)],
) -> EmailAnalysis:
    try:
        with log_timing(logger, "llm_manual_analysis"):
            return analyzer.analyze(email)
    except ConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except Exception as exc:
        logger.exception("Email analysis failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI provider could not analyze the email. Please try again.",
        ) from exc
