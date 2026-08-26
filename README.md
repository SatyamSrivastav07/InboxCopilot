# AI Inbox Copilot — Phase 6

AI Inbox Copilot now adds thread-aware reply drafting with a mandatory human approval gate and minimal Gmail send permission. PostgreSQL stores both the AI-generated text and the exact user-approved text. The system never sends during generation.

Phase 6 does not include attachments, Reply All, background sending, Redis, Celery, Docker, or deployment.

## Architecture

```text
Gmail sync -> analysis -> PostgreSQL -> VectorIndexer -> Chroma

Question -> RunnablePassthrough + retriever -> compact context
         -> RAG prompt -> Mistral -> StrOutputParser -> answer + sources

Inbox question -> QueryRoute -> RunnableBranch
  ├── structured -> validated parameters -> repository -> deterministic answer
  ├── semantic   -> existing Phase 4 RAG
  ├── hybrid     -> RunnableParallel(PostgreSQL, Chroma) -> Mistral synthesis
  └── unsupported -> safe deterministic response

Persisted email -> fetch Gmail thread -> compact chronological context
  -> LCEL reply prompt -> safety validation -> PostgreSQL draft
  -> user edits -> explicit approval -> final confirmation -> Gmail send
```

Newly persisted and cached Gmail messages pass through the indexer. Unchanged messages are skipped using deterministic chunk IDs and a content hash. Existing PostgreSQL data can rebuild Chroma at any time.

## Phase 6 Reply Copilot

Created modules:

```text
backend/app/
├── api/drafts.py
├── database/models/draft.py
├── database/repositories/draft_repository.py
├── genai/reply_chain.py
├── gmail/sender.py
├── schemas/draft.py
├── services/reply_service.py
└── services/thread_context_service.py
backend/alembic/versions/0002_email_drafts.py
backend/tests/test_reply_copilot.py
frontend/src/components/DraftReplyPanel.jsx
```

Modified integration files include Gmail OAuth/parser/dependencies, application dependencies and error handlers, email relationships, Assistant routing/UI, persisted email details, frontend API helpers, `.env.example`, and this README.

### OAuth scope change

The Gmail connection now requests exactly:

```text
https://www.googleapis.com/auth/gmail.readonly
https://www.googleapis.com/auth/gmail.send
```

It does not request `gmail.modify`. Existing read-only tokens cannot send and must be re-authorized:

In Google Cloud Console, open **Google Auth Platform → Data Access**, add the Gmail API `.../auth/gmail.send` scope alongside the existing read-only scope, and save. Keep the app in Testing with your Gmail address listed as a test user for local development.

```powershell
cd C:\Users\Redmi\Desktop\AI_IN_BOX\ai-inbox-copilot\backend
Remove-Item -LiteralPath .\token.json
```

Then restart the backend, open `/gmail`, select **Connect Gmail**, and approve the updated read + send scopes. Only delete this exact token file; PostgreSQL and Chroma are unrelated.

### Database migration

Apply the new `email_drafts` table:

```powershell
cd C:\Users\Redmi\Desktop\AI_IN_BOX\ai-inbox-copilot\backend
.\.venv\Scripts\Activate.ps1
alembic upgrade head
alembic current
```

Expected head: `0002_email_drafts`. The table stores source IDs/thread IDs, recipient, reply headers, tone/instruction, `generated_body`, `edited_body`, status, safety notes, failure state, Gmail sent ID, and timestamps.

`generated_body` is immutable AI output. `edited_body` is the current user-controlled text. Editing an approved draft resets it to `draft`; Gmail send always reads `edited_body` and never `generated_body`.

### Thread context

`ThreadContextService` loads the source email from PostgreSQL, fetches its Gmail thread, parses messages, sorts them chronologically, strips common quoted reply blocks, and retains sender, timestamp, subject, and clean body. It keeps the most recent 8 messages and at most 12,000 characters by default:

```dotenv
REPLY_THREAD_MAX_CHARS=12000
REPLY_THREAD_RECENT_MESSAGES=8
```

Reply recipient is the source message's valid `Reply-To` when present, otherwise its `From` address. `no-reply`/`noreply`/`do-not-reply` recipients are blocked at send time. `Message-ID` and `References` become MIME `In-Reply-To`/`References`, and Gmail receives the original `threadId`.

### Reply LCEL and validation

The readable LCEL chain maps `thread_context`, persisted `email_analysis`, optional `instruction`, and `tone`, then executes:

```python
mapped_evidence | reply_prompt | ChatMistralAI | PydanticOutputParser
```

The prompt forbids invented facts, attachments, completed-action claims, availability, acceptance, and unsupported commitments. A `RunnableLambda` validation step checks high-risk attachment/completion/attendance language. If unsafe, one correction chain runs and the result is checked once more. Remaining issues are persisted and approval is rejected until the user edits them.

Attachment requests create a visible warning. Phase 6 cannot attach files and the validator rejects language claiming a file is attached.

### Approval and send lifecycle

```text
draft -> user edit (draft) -> approved -> Gmail success -> sent
                                  └── Gmail failure -> failed -> edit/approve again
```

- Generate only creates a PostgreSQL draft; it cannot send.
- PATCH persists the exact edited text and resets approval.
- Approve validates the current edited text but still does not send.
- Send requires `approved`, non-empty text, a valid non-no-reply recipient, connected Gmail, and `gmail.send` scope.
- The database row is locked during send. A `sent` draft returns HTTP 409 and cannot be changed, approved, or sent again.
- A final React confirmation names the recipient and subject before calling send.

### Reply APIs

```text
POST  /api/emails/{email_id}/draft-reply
GET   /api/drafts/{draft_id}
PATCH /api/drafts/{draft_id}
POST  /api/drafts/{draft_id}/approve
POST  /api/drafts/{draft_id}/send
```

Draft request example:

```json
{"instruction":"Ask whether Friday afternoon works.","tone":"professional"}
```

Assistant questions such as `Draft a reply to the latest HR email saying thank you` may create a draft only when one concrete email is clear. Ambiguous matches return candidate sources. Bulk reply drafting is blocked. Assistant generation opens the same editor and never approves or sends.

Phase 6 adds no Python or frontend dependencies. It adds two optional context-limit environment values shown above.

## Phase 5 intelligent query router

Created modules:

```text
backend/app/genai/query_router.py
backend/app/genai/inbox_workflow.py
backend/app/schemas/query.py
backend/app/services/structured_query_service.py
backend/tests/test_query_router.py
```

`QueryRouter` uses explicit LCEL `ChatPromptTemplate | ChatMistralAI | PydanticOutputParser` chains. It first returns a validated `QueryRoute` with `route`, `intent`, `reason`, and routing `confidence`. Structured and hybrid paths then extract a separate validated `StructuredQuery`.

The actual workflow uses `RunnableBranch`, not an API-level if/else router:

```python
RunnableLambda(route_question) | RunnableBranch(
    structured_condition_and_chain,
    semantic_condition_and_chain,
    hybrid_condition_and_chain,
    unsupported_fallback,
)
```

Supported structured intents are `list_tasks`, `count_tasks`, `list_deadlines`, `list_meetings`, `count_emails`, `list_emails`, `needs_reply`, and `priority_summary`. The model never writes SQL. `StructuredQueryService` maps the allow-listed intent and validated filters to repository methods.

Hybrid execution explicitly uses:

```python
RunnableParallel(
    structured=validated_postgresql_query,
    semantic=existing_phase_4_retrieval,
)
```

The synthesis prompt receives only those two evidence sets. Structured facts are authoritative for counts/status/deadlines; semantic evidence explains relevant email context. Returned citations are built from retrieved/database records rather than model output.

Small deterministic route guards correct high-signal cases where an SQL-only answer would discard useful email evidence: inbox prioritization, deadlines explicitly described as "mentioned in emails," and urgent-email action summaries are promoted to the hybrid branch. The LLM still performs the initial classification; the actual workflow still executes through `RunnableBranch`.

The existing endpoint is upgraded in place:

```http
POST /api/chat/inbox
Content-Type: application/json

{"question":"What should I prioritize today?"}
```

Its response now includes `answer`, `sources`, `route`, `intent`, `reason`, and `confidence`. The React Assistant displays the chosen route and confidence. Semantic Search remains retrieval-only at `POST /api/search/semantic`.

Phase 5 adds no dependencies and no environment variables.

## Phase 4 retrieval structure

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

Phase 4 added only:

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
14. For Reply Copilot, use a Gmail test account and reconnect after deleting the old read-only `token.json`.
15. Sync Inbox, open a persisted email, and select **Draft Reply**.
16. Enter `Thank them and ask whether Friday afternoon works.`, choose a tone, and generate.
17. Confirm the thread-message indicator, recipient, normalized `Re:` subject, warnings, and editable body.
18. Edit one sentence and select **Save Changes**. Verify `generated_body` stayed unchanged while `edited_body` changed:

    ```sql
    SELECT id, generated_body, edited_body, status FROM email_drafts ORDER BY id DESC LIMIT 1;
    ```

19. Select **Approve Exact Text**. Confirm no Gmail message has been sent yet.
20. Select **Send Reply**, review the final recipient/subject confirmation, then select **Send Reply** again.
21. Verify Gmail Sent contains the exact edited text in the original thread and PostgreSQL status is `sent`.
22. Attempt send again through the API/UI and verify it is disabled or returns HTTP 409.

Automated checks:

```powershell
cd C:\Users\Redmi\Desktop\AI_IN_BOX\ai-inbox-copilot\backend
.\.venv\Scripts\python.exe -m pytest -q

cd C:\Users\Redmi\Desktop\AI_IN_BOX\ai-inbox-copilot\frontend
npm run build
```

Tests use SQLite, ephemeral Chroma, fake embeddings, fake reply generation, and mocked Gmail send resources—automated tests never send real email.

## Limitations

- Single-user local Chroma collection; future user isolation is not implemented.
- Gmail sync is still an explicit UI/API action. Phase 4 indexes automatically during sync but adds no scheduled/background polling because that is outside this phase.
- Semantic retrieval uses cosine similarity; hybrid routing combines it with safe structured repository queries but does not implement arbitrary SQL generation or a general SQL query planner.
- Direct out-of-app PostgreSQL changes can leave stale vectors until reindex.
- Reply is single-recipient only; Reply All is intentionally absent.
- Attachments cannot be sent. Attachment requests are warnings and attachment claims are blocked.
- Draft generation requires the Gmail thread to remain available and OAuth to contain both minimal scopes.
- No background send queue, scheduled retry, advanced monitoring, multi-user authentication, or production deployment.
- Gmail send and PostgreSQL commit are separate external systems; an extremely narrow crash after Gmail accepts a message but before local status commit requires manual reconciliation.

Phase 6 stops here. Phase 7 infrastructure and production features are intentionally excluded.
