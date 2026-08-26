from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any, TypeVar

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import Runnable, RunnableLambda, RunnableParallel
from langchain_mistralai import ChatMistralAI
from pydantic import BaseModel

from app.genai.prompts import (
    CLASSIFICATION_INSTRUCTION,
    ENTITIES_INSTRUCTION,
    MEETING_INSTRUCTION,
    SUMMARY_INSTRUCTION,
    TASKS_INSTRUCTION,
    analysis_prompt,
)
from app.schemas.email import (
    ClassificationResult,
    EmailAnalysis,
    EmailInput,
    Entities,
    MeetingExtractionResult,
    SummaryResult,
    TaskExtractionResult,
)

SchemaT = TypeVar("SchemaT", bound=BaseModel)


def _structured_branch(
    model: ChatMistralAI,
    schema: type[SchemaT],
    instruction: str,
) -> Runnable[dict[str, Any], Any]:
    parser = PydanticOutputParser(pydantic_object=schema)
    prompt = analysis_prompt().partial(
        analysis_instruction=instruction,
        format_instructions=parser.get_format_instructions(),
    )
    # Explicit LCEL RunnableSequence: prompt | model | parser.
    return prompt | model | parser


def _prepare_email(email: EmailInput) -> dict[str, str]:
    return {
        "sender": email.sender,
        "subject": email.subject,
        "body": email.body,
        "current_date": date.today().isoformat(),
    }


def _assemble(email: EmailInput, result: Mapping[str, Any]) -> EmailAnalysis:
    classification = ClassificationResult.model_validate(result["classification"])
    summary = SummaryResult.model_validate(result["summary"])
    tasks = TaskExtractionResult.model_validate(result["tasks"])
    meeting = MeetingExtractionResult.model_validate(result["meeting"])
    entities = Entities.model_validate(result["entities"])

    return EmailAnalysis(
        sender=email.sender,
        subject=email.subject,
        summary=summary.summary,
        classification={
            "category": classification.category,
            "priority": classification.priority,
            "reason": classification.reason,
        },
        tasks=tasks.tasks,
        meeting=meeting.meeting,
        entities=entities,
        reply_required=classification.reply_required,
    )


def build_analysis_chain(model: ChatMistralAI) -> Runnable[EmailInput, EmailAnalysis]:
    parallel = RunnableParallel(
        classification=_structured_branch(
            model, ClassificationResult, CLASSIFICATION_INSTRUCTION
        ),
        summary=_structured_branch(model, SummaryResult, SUMMARY_INSTRUCTION),
        tasks=_structured_branch(model, TaskExtractionResult, TASKS_INSTRUCTION),
        meeting=_structured_branch(model, MeetingExtractionResult, MEETING_INSTRUCTION),
        entities=_structured_branch(model, Entities, ENTITIES_INSTRUCTION),
    )

    def analyze(email: EmailInput) -> EmailAnalysis:
        result = parallel.invoke(_prepare_email(email))
        return _assemble(email, result)

    return RunnableLambda(analyze)
