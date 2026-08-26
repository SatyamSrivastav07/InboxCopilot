from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import (
    Runnable,
    RunnableBranch,
    RunnableLambda,
    RunnableParallel,
)
from langchain_mistralai import ChatMistralAI

from app.config import Settings
from app.genai.query_router import QueryRouter
from app.genai.rag import InboxRAG, RAGGenerationError, format_context, format_sources
from app.schemas.query import (
    QueryRoute,
    QueryRouteType,
    RoutedInboxResponse,
    StructuredIntent,
    StructuredItem,
    StructuredQueryResult,
)
from app.schemas.search import InboxSource
from app.schemas.search import SearchFilters
from app.services.structured_query_service import StructuredQueryService
from app.services.reply_service import ReplyService

logger = logging.getLogger(__name__)

UNSUPPORTED_ANSWER = (
    "I can answer questions about your persisted inbox, tasks, deadlines, meetings, "
    "and email discussions, but I can't perform that request in this phase."
)

HYBRID_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Create a concise priority-oriented answer using only the supplied inbox evidence.
Structured database facts are authoritative for counts, task status, deadlines, and priorities.
Retrieved email context may explain why an item matters.
Never invent emails, dates, senders, tasks, actions, or completion status.
If semantic evidence is missing, state that the explanation is limited to structured inbox data.

Structured evidence:
{structured_context}

Semantic email evidence:
{semantic_context}

Semantic evidence status: {semantic_status}
Only say the explanation is limited to structured data when this status is "missing".""",
        ),
        ("human", "Question: {question}"),
    ]
)


def _structured_sources(result: StructuredQueryResult) -> list[InboxSource]:
    sources: list[InboxSource] = []
    seen: set[int] = set()
    for item in result.items:
        if item.email_id is None or item.email_id in seen:
            continue
        seen.add(item.email_id)
        sources.append(
            InboxSource(
                email_id=item.email_id,
                subject=item.subject or item.title,
                sender=item.sender or "Unknown sender",
                received_at=item.date.isoformat() if item.date else None,
                snippet=item.description or item.title,
            )
        )
    return sources


def _item_line(item: StructuredItem) -> str:
    details: list[str] = []
    if item.date:
        details.append(item.date.isoformat())
    if item.time:
        details.append(item.time)
    if item.priority:
        details.append(f"{item.priority} priority")
    if item.completed is not None:
        details.append("completed" if item.completed else "pending")
    suffix = f" ({', '.join(details)})" if details else ""
    return f"- {item.title}{suffix}"


def format_structured_context(result: StructuredQueryResult) -> str:
    lines = [f"Intent: {result.intent.value}"]
    if result.count is not None:
        lines.append(f"Count: {result.count}")
    if result.priority_counts:
        counts = ", ".join(
            f"{name}={value}" for name, value in sorted(result.priority_counts.items())
        )
        lines.append(f"Email priority counts: {counts}")
    lines.extend(_item_line(item) for item in result.items)
    return "\n".join(lines)


def format_structured_answer(result: StructuredQueryResult) -> str:
    count = result.count or 0
    if result.intent == StructuredIntent.COUNT_TASKS:
        return f"You currently have {count} matching tasks."
    if result.intent == StructuredIntent.COUNT_EMAILS:
        return f"You currently have {count} matching emails."
    if result.intent == StructuredIntent.NEEDS_REPLY:
        lead = f"You currently have {count} emails that need a reply."
    elif result.intent == StructuredIntent.PRIORITY_SUMMARY:
        counts = ", ".join(
            f"{name}: {value}" for name, value in sorted(result.priority_counts.items())
        ) or "no emails"
        lead = f"Email priority summary — {counts}."
    elif result.intent == StructuredIntent.LIST_MEETINGS:
        lead = f"I found {count} matching meetings."
    elif result.intent == StructuredIntent.LIST_DEADLINES:
        lead = f"I found {count} matching deadlines."
    elif result.intent == StructuredIntent.LIST_TASKS:
        lead = f"I found {count} matching tasks."
    else:
        lead = f"I found {count} matching emails."

    if not result.items:
        return lead
    return f"{lead}\n" + "\n".join(_item_line(item) for item in result.items)


class InboxQueryWorkflow:
    """Routes one question through an explicit LCEL RunnableBranch."""

    def __init__(
        self,
        router: QueryRouter,
        structured_service: StructuredQueryService,
        rag: InboxRAG,
        settings: Settings,
        *,
        hybrid_model: ChatMistralAI | None = None,
        hybrid_answer_chain: Runnable | None = None,
        reply_service: ReplyService | None = None,
    ) -> None:
        self.router = router
        self.structured_service = structured_service
        self.rag = rag
        self.settings = settings
        self.hybrid_model = hybrid_model
        self._hybrid_answer_chain = hybrid_answer_chain
        self.reply_service = reply_service

        self.hybrid_parallel = RunnableParallel(
            question=RunnableLambda(lambda state: state["question"]),
            structured=RunnableLambda(self._hybrid_structured),
            semantic=RunnableLambda(self._hybrid_semantic),
        )

        self.branch = RunnableBranch(
            (
                lambda state: state["route"].route == QueryRouteType.STRUCTURED,
                RunnableLambda(self._run_structured),
            ),
            (
                lambda state: state["route"].route == QueryRouteType.SEMANTIC,
                RunnableLambda(self._run_semantic),
            ),
            (
                lambda state: state["route"].route == QueryRouteType.HYBRID,
                RunnableLambda(self._run_hybrid),
            ),
            (
                lambda state: state["route"].route == QueryRouteType.REPLY_DRAFT,
                RunnableLambda(self._run_reply_draft),
            ),
            RunnableLambda(self._run_unsupported),
        )
        # Explicit LCEL sequence: classification state -> RunnableBranch workflow.
        self.chain = RunnableLambda(self._route_state) | self.branch

    def _route_state(self, payload: dict[str, Any]) -> dict[str, Any]:
        question = payload["question"]
        route = self.router.route(question)
        logger.info(
            "Inbox query routed to %s with intent=%s confidence=%.2f",
            route.route.value,
            route.intent,
            route.confidence,
        )
        return {
            "question": question,
            "route": route,
            "top_k": payload.get("top_k"),
            "filters": payload.get("filters"),
        }

    @staticmethod
    def _response(
        route: QueryRoute, answer: str, sources: list[InboxSource]
    ) -> RoutedInboxResponse:
        return RoutedInboxResponse(
            answer=answer,
            sources=sources,
            route=route.route,
            intent=route.intent,
            reason=route.reason,
            confidence=route.confidence,
        )

    def _structured_result(self, state: dict[str, Any]) -> StructuredQueryResult:
        query = self.router.structured_query(state["question"], state["route"])
        return self.structured_service.execute(query)

    def _run_structured(self, state: dict[str, Any]) -> RoutedInboxResponse:
        result = self._structured_result(state)
        return self._response(
            state["route"],
            format_structured_answer(result),
            _structured_sources(result),
        )

    def _run_semantic(self, state: dict[str, Any]) -> RoutedInboxResponse:
        result = self.rag.ask(
            state["question"],
            top_k=state.get("top_k"),
            filters=state.get("filters"),
        )
        return self._response(state["route"], result.answer, result.sources)

    def _hybrid_structured(self, state: dict[str, Any]) -> StructuredQueryResult:
        return self._structured_result(state)

    def _hybrid_semantic(self, state: dict[str, Any]):
        return self.rag.retrieve(
            state["question"],
            top_k=state.get("top_k"),
            filters=state.get("filters"),
        )

    def _get_hybrid_answer_chain(self) -> Runnable:
        if self._hybrid_answer_chain is None:
            if self.hybrid_model is None:
                self.hybrid_model = ChatMistralAI(
                    api_key=self.settings.require_mistral_api_key(),
                    model=self.settings.mistral_model,
                    temperature=0,
                    max_retries=2,
                )
            self._hybrid_answer_chain = HYBRID_PROMPT | self.hybrid_model | StrOutputParser()
        return self._hybrid_answer_chain

    def _run_hybrid(self, state: dict[str, Any]) -> RoutedInboxResponse:
        logger.info("Hybrid SQL and semantic retrieval started")
        evidence = self.hybrid_parallel.invoke(state)
        structured: StructuredQueryResult = evidence["structured"]
        semantic = evidence["semantic"]
        if not structured.items and not structured.count and not semantic:
            answer = "I couldn't find relevant structured or semantic information in your inbox."
            return self._response(state["route"], answer, [])

        try:
            answer = self._get_hybrid_answer_chain().invoke(
                {
                    "question": evidence["question"],
                    "structured_context": format_structured_context(structured),
                    "semantic_context": format_context(semantic)
                    if semantic
                    else "No relevant semantic email evidence was found.",
                    "semantic_status": "present" if semantic else "missing",
                }
            )
        except Exception as exc:
            logger.exception("Hybrid synthesis failed")
            raise RAGGenerationError(
                "Mistral could not synthesize the hybrid inbox answer."
            ) from exc

        sources = _structured_sources(structured) + format_sources(semantic)
        deduplicated = list({source.email_id: source for source in sources}.values())
        logger.info("Hybrid synthesis completed with %s sources", len(deduplicated))
        return self._response(state["route"], answer.strip(), deduplicated)

    def _run_unsupported(self, state: dict[str, Any]) -> RoutedInboxResponse:
        return self._response(state["route"], UNSUPPORTED_ANSWER, [])

    @staticmethod
    def _reply_instruction(question: str) -> str | None:
        match = re.search(
            r"\b(?:saying|and (?:say|ask|tell)|tell them|ask them)\b\s*[:,-]?\s*(.+)$",
            question,
            re.IGNORECASE,
        )
        return match.group(1).strip() if match else None

    @staticmethod
    def _result_time(item) -> datetime:
        try:
            value = datetime.fromisoformat(item.received_at)
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            return datetime.min.replace(tzinfo=timezone.utc)

    def _run_reply_draft(self, state: dict[str, Any]) -> RoutedInboxResponse:
        question = state["question"]
        if re.search(r"\b(all|every)\b.*\b(email|message|reply)", question, re.IGNORECASE):
            return self._response(
                state["route"],
                "Bulk reply drafting is disabled. Select one concrete email before drafting.",
                [],
            )
        candidates = self.rag.retrieve(question, top_k=3, filters=state.get("filters"))
        if not candidates:
            return self._response(
                state["route"],
                "I couldn't identify an email to reply to. Open an email in Inbox and choose Draft Reply.",
                [],
            )

        selected = None
        if len(candidates) == 1:
            selected = candidates[0]
        elif re.search(r"\b(latest|most recent|newest)\b", question, re.IGNORECASE):
            selected = max(candidates, key=self._result_time)
        elif candidates[0].score - candidates[1].score >= 0.15:
            selected = candidates[0]

        sources = format_sources(candidates)
        if selected is None:
            return self._response(
                state["route"],
                "I found multiple possible emails. Choose one of the sources to open it, then select Draft Reply.",
                sources,
            )
        if self.reply_service is None:
            return self._response(
                state["route"],
                "Open the selected source and choose Draft Reply to continue.",
                format_sources([selected]),
            )

        from app.schemas.draft import ReplyDraftRequest

        draft = self.reply_service.generate(
            selected.email_id,
            ReplyDraftRequest(instruction=self._reply_instruction(question)),
        )
        response = self._response(
            state["route"],
            "A reply draft is ready for review. It has not been approved or sent.",
            format_sources([selected]),
        )
        return response.model_copy(update={"draft": draft})

    def ask(
        self,
        question: str,
        *,
        top_k: int | None = None,
        filters: SearchFilters | None = None,
    ) -> RoutedInboxResponse:
        return self.chain.invoke(
            {"question": question, "top_k": top_k, "filters": filters}
        )
