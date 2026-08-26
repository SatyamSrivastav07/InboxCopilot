from __future__ import annotations

import re
from dataclasses import dataclass

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_mistralai import ChatMistralAI

from app.config import Settings
from app.schemas.draft import DraftValidation, ReplyDraftContent, ReplyTone


class ReplyGenerationError(RuntimeError):
    """Raised when Mistral cannot create a safe reply draft."""


REPLY_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Draft one email reply using only the supplied Gmail thread and persisted analysis.
Reply to the latest relevant message while respecting chronological context.
Tone: {tone}. Be concise, natural, and factual.
Follow the optional user instruction exactly when present.
Never invent dates, attachments, completed actions, availability, acceptance, or commitments.
Without explicit user intent, use neutral language and note any decision the user must make.
Do not claim an attachment is included; attachments are not supported.
Return only the requested structured output.
{format_instructions}""",
        ),
        (
            "human",
            """Thread context:
{thread_context}

Persisted AI analysis:
{email_analysis}

User instruction:
{instruction}""",
        ),
    ]
)

CORRECTION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Correct the email draft exactly once. Remove every unsupported claim listed below.
Do not add new facts or commitments. Do not claim attachments are included.
Keep the requested tone and user instruction. Return structured output only.
{format_instructions}""",
        ),
        (
            "human",
            """Issues:
{issues}

Original draft:
{draft}

Thread context:
{thread_context}

User instruction:
{instruction}

Tone: {tone}""",
        ),
    ]
)


def normalize_reply_subject(subject: str) -> str:
    cleaned = re.sub(r"^(?:\s*re\s*:\s*)+", "", subject, flags=re.IGNORECASE).strip()
    return f"Re: {cleaned or '(No subject)'}"


def validate_reply_body(body: str, instruction: str | None = None) -> DraftValidation:
    text = body.strip()
    instruction_text = (instruction or "").lower()
    issues: list[str] = []

    if re.search(r"\b(attached|attachment is included|find attached|i(?:'ve| have) attached)\b", text, re.IGNORECASE):
        issues.append("The draft claims an attachment is included, but attachments are unsupported.")

    completion_claim = re.search(
        r"\b(i(?:'ve| have)?\s+(?:completed|finished|submitted|sent)|the (?:task|work|assessment) is complete)\b",
        text,
        re.IGNORECASE,
    )
    completion_supported = re.search(
        r"\b(completed|finished|submitted|already sent|tell them .*sent)\b",
        instruction_text,
    )
    if completion_claim and not completion_supported:
        issues.append("The draft claims an action is complete without explicit user instruction.")

    commitment_claim = re.search(
        r"\b(i (?:can|will) attend|works for me|i accept|i confirm(?: that)?|count me in)\b",
        text,
        re.IGNORECASE,
    )
    commitment_supported = re.search(
        r"\b(accept|confirm|attend|works for me|say yes|agree)\b",
        instruction_text,
    )
    if commitment_claim and not commitment_supported:
        issues.append("The draft makes an attendance or acceptance commitment without instruction.")

    return DraftValidation(safe=not issues, issues=issues)


@dataclass(frozen=True)
class GeneratedReply:
    content: ReplyDraftContent
    validation: DraftValidation


class ReplyDraftGenerator:
    def __init__(
        self,
        settings: Settings,
        *,
        model: ChatMistralAI | None = None,
        draft_chain: Runnable | None = None,
        correction_chain: Runnable | None = None,
    ) -> None:
        self.settings = settings
        self.model = model
        self._draft_chain = draft_chain
        self._correction_chain = correction_chain
        self.validation_chain = RunnableLambda(
            lambda payload: validate_reply_body(
                payload["body"], payload.get("instruction")
            )
        )

    def _get_model(self) -> ChatMistralAI:
        if self.model is None:
            self.model = ChatMistralAI(
                api_key=self.settings.require_mistral_api_key(),
                model=self.settings.mistral_model,
                temperature=0,
                max_retries=2,
            )
        return self.model

    def _get_draft_chain(self) -> Runnable:
        if self._draft_chain is None:
            parser = PydanticOutputParser(pydantic_object=ReplyDraftContent)
            prompt = REPLY_PROMPT.partial(
                format_instructions=parser.get_format_instructions()
            )
            # Explicit LCEL reply chain: mapped evidence -> prompt -> model -> parser.
            mapped = {
                "thread_context": RunnableLambda(lambda data: data["thread_context"]),
                "email_analysis": RunnableLambda(lambda data: data["email_analysis"]),
                "instruction": RunnableLambda(lambda data: data["instruction"]),
                "tone": RunnableLambda(lambda data: data["tone"]),
            }
            self._draft_chain = mapped | prompt | self._get_model() | parser
        return self._draft_chain

    def _get_correction_chain(self) -> Runnable:
        if self._correction_chain is None:
            parser = PydanticOutputParser(pydantic_object=ReplyDraftContent)
            prompt = CORRECTION_PROMPT.partial(
                format_instructions=parser.get_format_instructions()
            )
            self._correction_chain = prompt | self._get_model() | parser
        return self._correction_chain

    def generate(
        self,
        *,
        thread_context: str,
        email_analysis: str,
        instruction: str | None,
        tone: ReplyTone,
    ) -> GeneratedReply:
        payload = {
            "thread_context": thread_context,
            "email_analysis": email_analysis,
            "instruction": instruction or "No additional instruction provided.",
            "tone": tone.value,
        }
        try:
            content = ReplyDraftContent.model_validate(
                self._get_draft_chain().invoke(payload)
            )
            validation = self.validation_chain.invoke(
                {"body": content.body, "instruction": instruction}
            )
            if not validation.safe:
                content = ReplyDraftContent.model_validate(
                    self._get_correction_chain().invoke(
                        {
                            **payload,
                            "draft": content.body,
                            "issues": "\n".join(f"- {item}" for item in validation.issues),
                        }
                    )
                )
                validation = self.validation_chain.invoke(
                    {"body": content.body, "instruction": instruction}
                )
            return GeneratedReply(content=content, validation=validation)
        except Exception as exc:
            raise ReplyGenerationError(
                "Mistral could not generate a safe reply draft. Please try again."
            ) from exc
