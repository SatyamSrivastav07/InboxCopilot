# Free demo deployment

This path deploys the public demo without paid Render instances. It is intentionally
user-triggered: Gmail sync and reprocessing run inside the browser request instead of
requiring an always-on Celery worker. Keep each sync small (five messages is best).

It is appropriate for a portfolio/demo launch, not an SLA-backed production service.
Free services may sleep, have quotas, and do not retain the embedded Chroma index after
a restart. PostgreSQL remains the source of truth; syncing again rebuilds the index.

## Included free resources

The root `render.yaml` creates these resources in the same Render region:

1. One free Docker web service.
2. One free Render Postgres database.
3. One free Render Key Value (Redis-compatible) instance.

Render links `DATABASE_URL` and `REDIS_URL` internally. Do not put either value in
GitHub or in a `VITE_*` variable.

## Render

1. Create a **Blueprint** from this repository's `main` branch. The root `render.yaml`
   creates the free API, Postgres, and Key Value resources.
2. When Render asks for environment values, enter:

   ```text
   MISTRAL_API_KEY=<your Mistral server key>
   TOKEN_ENCRYPTION_KEY=<stable Fernet key>
   SESSION_SECRET=<stable random secret>
   GOOGLE_CLIENT_ID=<Google OAuth client ID>
   GOOGLE_CLIENT_SECRET=<Google OAuth client secret>
   GOOGLE_REDIRECT_URI=https://inbox-copilot-woad.vercel.app/api/gmail/callback
   FRONTEND_ORIGINS=https://inbox-copilot-woad.vercel.app
   FRONTEND_URL=https://inbox-copilot-woad.vercel.app
   ```

   Generate the two stable app secrets locally:

   ```powershell
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

3. After Render creates the service, copy its HTTPS URL and confirm
   `/health/ready` responds successfully.

## Finish the connection

1. Check that the `/api/*` rewrite destination in `frontend/vercel.json` matches your public Render API URL, then deploy or redeploy Vercel. Do not set `VITE_API_BASE_URL`.
2. In Google Cloud OAuth credentials, add this exact redirect URI:

   ```text
   https://inbox-copilot-woad.vercel.app/api/gmail/callback
   ```

3. Keep the Google consent screen in Testing while you validate the flow. Public Gmail
   access still requires Google's restricted-scope verification; hosting it on a free
   tier does not bypass that review.

## Free-tier limits

- The Render API may take time to wake after inactivity.
- Keep Gmail syncs to five messages and wait on the page until it returns.
- Chroma semantic search is rebuilt after a Render restart; durable email, task, meeting,
  draft, and encrypted credential records live in PostgreSQL.
- Render free Postgres expires after 30 days; export important data before that deadline.
- Render Key Value can restart and lose cache/rate-limit counters. Mistral quotas can
  also stop requests after their included allowance is used.
