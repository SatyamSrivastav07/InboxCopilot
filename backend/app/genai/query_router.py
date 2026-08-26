from __future__ import annotations

from datetime import date
import re

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_mistralai import ChatMistralAI

from app.config import Settings
from app.schemas.query import QueryRoute, QueryRouteType, StructuredQuery


class QueryRoutingError(RuntimeError):
    """Raised when an inbox query cannot be classified or validated."""


ROUTER_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Classify an inbox question before any retrieval happens.

Routes:
- structured: counts, filters, pending tasks, deadlines, meetings, priorities, or reply-required status available in PostgreSQL.
- semantic: what someone said, what was discussed, topic search, or content summary that requires email meaning.
- hybrid: prioritization or synthesis that needs both structured tasks/status and semantic email explanations.
- reply_draft: writing or drafting a reply to one identifiable email. This creates a draft only and never sends.
- unsupported: sending, deleting, mailbox mutation, external web knowledge, or anything outside the persisted inbox.

Use an intent name that concisely describes the request. Confidence is only a routing estimate.
Do not answer the question.
{format_instructions}""",
        ),
        ("human", "Question: {question}"),
    ]
)


STRUCTURED_QUERY_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Extract a safe structured inbox query. Today is {today}.

Allowed intents:
- list_tasks, count_tasks, list_deadlines, list_meetings
- count_emails, list_emails, needs_reply, priority_summary

Resolve today, tomorrow, and this week into ISO date_from/date_to values.
Use completed=false only when pending/incomplete is requested.
Use priority/category/reply_required only when explicitly requested.
For hybrid prioritization choose priority_summary.
Never produce SQL and never invent unsupported filters.
{format_instructions}""",
        ),
        (
            "human",
            "Router intent: {route_intent}\nQuestion: {question}",
        ),
    ]
)


class QueryRouter:
    def __init__(
        self,
        settings: Settings,
        *,
        model: ChatMistralAI | None = None,
        route_chain: Runnable | None = None,
        structured_chain: Runnable | None = None,
    ) -> None:
        self.settings = settings
        self.model = model
        self._route_chain = route_chain
        self._structured_chain = structured_chain

    def _get_model(self) -> ChatMistralAI:
        if self.model is None:
            self.model = ChatMistralAI(
                api_key=self.settings.require_mistral_api_key(),
                model=self.settings.mistral_model,
                temperature=0,
                max_retries=2,
            )
        return self.model

    def _get_route_chain(self) -> Runnable:
        if self._route_chain is None:
            parser = PydanticOutputParser(pydantic_object=QueryRoute)
            prompt = ROUTER_PROMPT.partial(
                format_instructions=parser.get_format_instructions()
            )
            # Explicit LCEL: prompt -> Mistral -> Pydantic route.
            self._route_chain = prompt | self._get_model() | parser
        return self._route_chain

    def _get_structured_chain(self) -> Runnable:
        if self._structured_chain is None:
            parser = PydanticOutputParser(pydantic_object=StructuredQuery)
            prompt = STRUCTURED_QUERY_PROMPT.partial(
                format_instructions=parser.get_format_instructions()
            )
            # A second constrained LCEL chain extracts only allow-listed parameters.
            self._structured_chain = prompt | self._get_model() | parser
        return self._structured_chain

    def route(self, question: str) -> QueryRoute:
        try:
            result = self._get_route_chain().invoke({"question": question})
            route = QueryRoute.model_validate(result)
            return self._validate_route(question, route)
        except Exception as exc:
            raise QueryRoutingError(
                "The inbox question could not be routed. Please try again."
            ) from exc

    @staticmethod
    def _validate_route(question: str, route: QueryRoute) -> QueryRoute:
        """Apply small high-signal guards where SQL-only routing loses evidence."""
        normalized = re.sub(r"\s+", " ", question.lower()).strip()
        hybrid_rules = (
            (
                r"\b(prioriti[sz]e|priority|focus on)\b.*\b(today|now|first|should)\b|"
                r"\bwhat should i\b.*\b(prioriti[sz]e|do|focus)\b",
                "prioritize_inbox",
                "Prioritization needs structured task status plus semantic email context.",
            ),
            (
                r"\b(deadline|deadlines)\b.*\b(mentioned|emails?|messages?|recent)\b|"
                r"\b(recent|emails?|messages?)\b.*\b(deadline|deadlines)\b",
                "email_deadline_summary",
                "Mentioned deadlines may exist in email text as well as structured tasks.",
            ),
            (
                r"\bsummari[sz]e\b.*\b(urgent|important|priority)\b.*\b(tasks?|do|action)\b",
                "urgent_action_summary",
                "The request combines structured priority/action data with email meaning.",
            ),
        )
        if re.search(r"\b(draft|write|compose)\b.*\b(reply|response|email)\b", normalized):
            return QueryRoute(
                route=QueryRouteType.REPLY_DRAFT,
                intent="draft_reply",
                reason="The user requested a reply draft; sending still requires explicit UI approval.",
                confidence=max(route.confidence, 0.97),
            )
        for pattern, intent, reason in hybrid_rules:
            if re.search(pattern, normalized):
                return QueryRoute(
                    route=QueryRouteType.HYBRID,
                    intent=intent,
                    reason=reason,
                    confidence=max(route.confidence, 0.95),
                )
        return route

    def structured_query(self, question: str, route: QueryRoute) -> StructuredQuery:
        try:
            result = self._get_structured_chain().invoke(
                {
                    "question": question,
                    "route_intent": route.intent,
                    "today": date.today().isoformat(),
                }
            )
            return StructuredQuery.model_validate(result)
        except Exception as exc:
            raise QueryRoutingError(
                "The structured inbox filters could not be validated."
            ) from exc
