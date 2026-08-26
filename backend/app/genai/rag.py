from __future__ import annotations

import logging
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_mistralai import ChatMistralAI

from app.config import Settings
from app.schemas.search import AskInboxResponse, InboxSource, SearchFilters
from app.vectorstore.retriever import RetrievedEmail, VectorRetriever

logger = logging.getLogger(__name__)
NO_EVIDENCE_ANSWER = "I couldn't find relevant information in your inbox."


class RAGGenerationError(RuntimeError):
    """Raised when grounded answer generation fails after successful retrieval."""

RAG_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You answer questions using only the retrieved email context below.
Never invent emails, dates, senders, decisions, actions, or completion status.
If the context is insufficient, say the information could not be found in the inbox.
Be concise and factual, preserve uncertainty, and refer to source numbers when useful.

Retrieved inbox context:
{context}""",
        ),
        ("human", "Question: {question}"),
    ]
)


def format_context(results: list[RetrievedEmail]) -> str:
    return "\n\n".join(
        (
            f"[Source {index}]\n"
            f"Email ID: {item.email_id}\n"
            f"Subject: {item.subject}\n"
            f"Sender: {item.sender}\n"
            f"Received At: {item.received_at or 'Unknown'}\n"
            f"Relevant content:\n{item.content}"
        )
        for index, item in enumerate(results, start=1)
    )


def format_sources(results: list[RetrievedEmail]) -> list[InboxSource]:
    return [
        InboxSource(
            email_id=item.email_id,
            subject=item.subject,
            sender=item.sender,
            received_at=item.received_at or None,
            snippet=item.snippet(),
        )
        for item in results
    ]


class InboxRAG:
    def __init__(
        self,
        retriever: VectorRetriever,
        settings: Settings,
        model: ChatMistralAI | None = None,
    ) -> None:
        self.retriever = retriever
        self.settings = settings
        self.model = model

        # RunnablePassthrough preserves the original question/filters while
        # RunnableLambda adds retrieved evidence to the same state dictionary.
        self.retrieval_chain = RunnablePassthrough.assign(
            results=RunnableLambda(self._retrieve)
        )

    def _retrieve(self, payload: dict[str, Any]) -> list[RetrievedEmail]:
        return self.retriever.search(
            payload["question"],
            top_k=payload["top_k"],
            filters=payload.get("filters"),
        )

    def _answer_chain(self):
        if self.model is None:
            self.model = ChatMistralAI(
                api_key=self.settings.require_mistral_api_key(),
                model=self.settings.mistral_model,
                temperature=0,
                max_retries=2,
            )
        return (
            {
                "context": RunnableLambda(lambda state: format_context(state["results"])),
                "question": RunnableLambda(lambda state: state["question"]),
            }
            | RAG_PROMPT
            | self.model
            | StrOutputParser()
        )

    def ask(
        self,
        question: str,
        *,
        top_k: int | None = None,
        filters: SearchFilters | None = None,
    ) -> AskInboxResponse:
        results = self.retrieve(question, top_k=top_k, filters=filters)
        if not results:
            logger.info("RAG generation skipped because evidence was insufficient")
            return AskInboxResponse(answer=NO_EVIDENCE_ANSWER, sources=[])
        state = {"question": question, "results": results}

        logger.info("RAG generation started with %s sources", len(results))
        try:
            answer = self._answer_chain().invoke(state)
        except Exception as exc:
            logger.exception("RAG generation failed")
            raise RAGGenerationError(
                "Mistral could not generate an inbox answer. Please try again."
            ) from exc
        logger.info("RAG generation completed")
        return AskInboxResponse(answer=answer.strip(), sources=format_sources(results))

    def retrieve(
        self,
        question: str,
        *,
        top_k: int | None = None,
        filters: SearchFilters | None = None,
    ) -> list[RetrievedEmail]:
        """Expose the existing Phase 4 retrieval stage for hybrid composition."""
        logger.info("RAG retrieval started")
        state = self.retrieval_chain.invoke(
            {
                "question": question,
                "top_k": top_k or self.settings.rag_top_k,
                "filters": filters,
            }
        )
        results: list[RetrievedEmail] = state["results"]
        results = [
            item
            for item in results
            if item.score >= self.settings.rag_score_threshold
        ]
        return results
