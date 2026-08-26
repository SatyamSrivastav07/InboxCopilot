# AI Inbox Copilot — Interview Guide

## Why PostgreSQL and Chroma both exist

PostgreSQL is the source of truth for durable emails, tasks, meetings, entities, draft state, and deterministic filters/counts. Chroma stores chunk embeddings for semantic retrieval over email meaning. This split keeps structured facts queryable without an LLM and makes Chroma rebuildable from PostgreSQL.

## Why not use RAG for every query

Counts, deadlines, task status, and meeting filters are precise relational queries. Using RAG for those would add latency and could make a factual count less reliable. Semantic RAG is used when the answer depends on the wording or meaning of email content.

## Why RunnableBranch was used

`RunnableBranch` expresses the route decision as an executable LCEL graph: structured, semantic, hybrid, reply-draft, or unsupported. It keeps the API layer thin and avoids a hidden chain of imperative conditionals.

## Why RunnableParallel was used

Email analysis fans out independent classification, summary, task, meeting, and entity extraction work. Hybrid inbox questions also run a structured PostgreSQL query and semantic retrieval together, then synthesize only their evidence.

## How duplicate processing is prevented

`gmail_message_id` is unique in PostgreSQL. A worker reserves a pending row before analysis; overlapping jobs recover safely from the unique constraint. Redis prevents accidental concurrent sync storms, while the database remains the final race guard.

## How hallucinations are reduced

RAG answers receive compact retrieved source context, expose citations from retrieval objects rather than model-made metadata, and return a deterministic no-evidence response before a model call when retrieval is weak. Structured facts bypass free-form generation where possible.

## Why Gmail send requires approval

Draft generation only persists a draft. Users can edit it, approve the exact text, then explicitly send. The row is locked during send and sent drafts are immutable, which prevents silent sending and double-send races.

## Why PostgreSQL is the source of truth

It is transactional, durable, and holds user-visible lifecycle state. Chroma is derived data: it can be deleted and rebuilt by a background reindex job without losing inbox intelligence.

## How background processing works

FastAPI queues JSON-safe IDs/parameters to Celery through Redis. Each worker creates its own SQLAlchemy session, calls existing services, reports small progress metadata, and releases its lock. Email bodies are not stored in Redis job results.

## How the system could scale

Move OAuth/token storage to per-user encrypted storage, isolate collections per tenant, use managed Postgres/Redis/vector infrastructure, add worker autoscaling and observability, and place the app behind managed HTTPS. The service boundaries already separate API, workers, persistence, indexing, and integrations.
