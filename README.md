# AI Inbox Copilot — Phase 4

AI Inbox Copilot now provides semantic search and grounded question answering over persisted Gmail history. PostgreSQL remains the source of truth; Chroma is a rebuildable local retrieval index. Mistral supplies `mistral-embed` embeddings and the existing chat model.

Phase 4 does not include reply drafting, Gmail sending, SQL/RAG routing, Redis, Celery, Docker, or deployment.

## Architecture

```text
Gmail sync -> analysis -> PostgreSQL -> VectorIndexer -> Chroma

Question -> RunnablePassthrough + retriever -> compact context
         -> RAG prompt -> Mistral -> StrOutputParser -> answer + sources
```

Newly persisted and cached Gmail messages pass through the indexer. Unchanged messages are skipped using deterministic chunk IDs and a content hash. Existing PostgreSQL data can rebuild Chroma at any time.

## Phase 4 structure

```text
backend/app/
├── api/{chat.py,search.py}
├── genai/rag.py
├── schemas/search.py
├── services/reindex.py
└── vectorstore/
    ├── dependencies.py
    ├── embeddings.py
    ├── errors.py
    ├── indexer.py
    ├── retriever.py
    └── store.py

frontend/src/
├── pages/{AssistantPage.jsx,InboxPage.jsx}
├── components/AppHeader.jsx
├── services/api.js
└── App.jsx
```

Integration updates also touch `backend/app/config.py`, `backend/app/main.py`, `backend/app/services/dependencies.py`, `backend/app/services/gmail_sync.py`, `backend/app/database/repositories/email_repository.py`, `backend/.env.example`, `backend/requirements.txt`, `.gitignore`, and backend tests.

## Dependencies and environment

Phase 4 adds only:

```text
chromadb>=1.0,<2.0
langchain-text-splitters>=0.3,<2.0
```

Install from `backend`:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Keep values in `backend/.env`; never place secrets in React:

```dotenv
MISTRAL_API_KEY=replace_with_your_key
MISTRAL_MODEL=mistral-small-latest
DATABASE_URL=postgresql+psycopg2://postgres:password@localhost:5432/inbox_copilot
GOOGLE_CLIENT_ID=replace_with_google_client_id
GOOGLE_CLIENT_SECRET=replace_with_google_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/gmail/callback
GMAIL_TOKEN_FILE=token.json
FRONTEND_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
FRONTEND_URL=http://localhost:5173
CHROMA_PERSIST_DIRECTORY=./data/chromadb
CHROMA_COLLECTION_NAME=inbox_emails
RAG_TOP_K=4
RAG_SCORE_THRESHOLD=0.2
EMAIL_CHUNK_SIZE=1000
EMAIL_CHUNK_OVERLAP=100
```

The Chroma path resolves relative to `backend/` and is excluded by `.gitignore`.

## Run

Backend terminal:

```powershell
cd C:\Users\Redmi\Desktop\AI_IN_BOX\ai-inbox-copilot\backend
.\.venv\Scripts\Activate.ps1
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Frontend terminal:

```powershell
cd C:\Users\Redmi\Desktop\AI_IN_BOX\ai-inbox-copilot\frontend
npm install
npm run dev
```

Open <http://localhost:5173/assistant>. API documentation is at <http://localhost:8000/docs>.

## Indexing and consistency

`retrieval_text()` includes subject, sender, received time, cleaned body, and AI summary. `RecursiveCharacterTextSplitter` defaults to 1,000-character chunks with 100-character overlap. Every chunk preserves:

- `email_id`, `gmail_message_id`, and `gmail_thread_id`
- sender, subject, and received time
- category and priority
- chunk number and content hash

IDs are deterministic: `email_<email_id>_chunk_<chunk_number>`. Normal Gmail sync skips embedding when the content hash and chunk count are unchanged. Changed or explicitly reindexed emails have old chunks removed and deterministic IDs safely upserted.

Matching chunks collapse to one result per email, with at most two emails from one Gmail thread. Phase 4 uses normal cosine similarity instead of MMR to keep the Chroma abstraction simple and replaceable.

`VectorIndexer` exposes `index_email`, `reindex_email`, and `delete_email_vectors` for future lifecycle work. Local email deletion itself is not added.

## API usage

Rebuild Chroma from PostgreSQL:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/search/reindex
```

Example: `{"emails_indexed":100,"emails_skipped":0,"chunks_created":237}`.

Retrieval-only semantic search (no chat-model call):

```powershell
$body = @{ query = "deployment issues"; top_k = 5 } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/search/semantic -ContentType "application/json" -Body $body
```

Optional filters under `filters`: `sender`, `category`, `priority`, `date_from`, and `date_to`.

Grounded question:

```powershell
$body = @{ question = "What did HR say about onboarding?" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/chat/inbox -ContentType "application/json" -Body $body
```

Responses contain short source snippets with email IDs, subjects, senders, and dates. If no result meets `RAG_SCORE_THRESHOLD`, the chat model is not called and the safe no-evidence answer is returned.

## LCEL and RunnablePassthrough

Retrieval in `backend/app/genai/rag.py` is explicit:

```python
retrieval_chain = RunnablePassthrough.assign(
    results=RunnableLambda(self._retrieve)
)
```

1. Initial state contains `question`, `top_k`, and optional `filters`.
2. `RunnablePassthrough` preserves those values.
3. `.assign(...)` runs retrieval and adds `results` to the same state.
4. Weak/no evidence is rejected before model invocation.

Grounded generation is:

```python
{
    "context": RunnableLambda(lambda state: format_context(state["results"])),
    "question": RunnableLambda(lambda state: state["question"]),
}
| RAG_PROMPT
| model
| StrOutputParser()
```

1. Retrieved emails become numbered compact context.
2. The original question remains unchanged.
3. `{context, question}` fills the strict prompt.
4. Mistral generates from evidence at temperature zero.
5. `StrOutputParser` produces the answer string.
6. Citations come from the same retrieval objects, never from model-generated metadata.

The prompt forbids invented emails, senders, dates, decisions, actions, and completion claims, while preserving uncertainty.

## Complete test flow

1. Start PostgreSQL and confirm database `inbox_copilot` exists.
2. Activate `backend/.venv`, run `alembic upgrade head`, then start Uvicorn.
3. Start the frontend with `npm run dev`.
4. Open `/gmail`, connect Gmail, and sync a small known set.
5. Verify PostgreSQL:

   ```sql
   SELECT id, gmail_message_id, subject, category, priority
   FROM emails ORDER BY id DESC LIMIT 10;
   ```

6. Sync automatically indexes each saved/cached email; no per-email indexing step is required.
7. Call `POST /api/search/reindex` once to rebuild all historical rows.
8. Open `/assistant`, choose **Semantic Search**, and search for a known topic.
9. Confirm ranked results show short source metadata and snippets.
10. Choose **Ask Inbox**, ask a natural-language question, and verify the answer against listed sources.
11. Click a source and confirm its persisted Inbox detail opens.
12. Ask about an absent topic and confirm the safe no-evidence response.
13. Optionally stop the backend, remove only `backend/data/chromadb`, restart, and reindex. PostgreSQL remains intact.

Automated checks:

```powershell
cd C:\Users\Redmi\Desktop\AI_IN_BOX\ai-inbox-copilot\backend
.\.venv\Scripts\python.exe -m pytest -q

cd C:\Users\Redmi\Desktop\AI_IN_BOX\ai-inbox-copilot\frontend
npm run build
```

Tests use SQLite, an ephemeral Chroma collection, and fake deterministic embeddings—no live Gmail or Mistral calls.

## Limitations

- Single-user local Chroma collection; future user isolation is not implemented.
- Gmail sync is still an explicit UI/API action. Phase 4 indexes automatically during sync but adds no scheduled/background polling because that is outside this phase.
- Semantic cosine retrieval only; no SQL/vector router, hybrid search, or MMR.
- Direct out-of-app PostgreSQL changes can leave stale vectors until reindex.
- No attachment indexing, full conversation memory, reply generation, Gmail sending, or production deployment.

Phase 4 stops here. Phase 5 features are intentionally excluded.
