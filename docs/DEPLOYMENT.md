# Public deployment guide

This project is designed for a Vercel frontend and a Render API, PostgreSQL, and Redis deployment. The Vercel project includes a same-origin `/api/*` proxy so the signed session cookie remains first-party in the browser. Do not expose the Render API URL to browser code unless you deliberately choose a cross-origin deployment.

## 1. Deploy the API on Render

1. In Render, create a **Blueprint** from this repository. It reads `render.yaml` and creates the API, managed PostgreSQL, and Key Value (Redis).
2. Use a plan that supports the configured persistent disk. Chroma is an embedded, rebuildable index and needs `/app/data` to survive deploys.
3. Set these secret environment variables in the Render service:

   ```text
   MISTRAL_API_KEY
   GOOGLE_CLIENT_ID
   GOOGLE_CLIENT_SECRET
   TOKEN_ENCRYPTION_KEY
   SESSION_SECRET
   FRONTEND_ORIGINS=https://YOUR_VERCEL_DOMAIN
   FRONTEND_URL=https://YOUR_VERCEL_DOMAIN
   GOOGLE_REDIRECT_URI=https://YOUR_VERCEL_DOMAIN/api/gmail/callback
   ```

   Generate `TOKEN_ENCRYPTION_KEY` once with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`, and generate `SESSION_SECRET` once with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Keep both values stable; rotating either invalidates stored credentials or signs users out.
4. Deploy. Render runs Alembic before starting the API. Confirm `https://YOUR_RENDER_DOMAIN/health/ready` returns `status: ready`.

The Render start script supervises Celery: if a worker exits it is restarted, while a normal Render deploy stops both the worker and API cleanly.

## 2. Deploy the frontend on Vercel

1. Import the same GitHub repository, with **Root Directory** set to `frontend`.
2. Add one server-only Vercel environment variable:

   ```text
   BACKEND_ORIGIN=https://YOUR_RENDER_DOMAIN
   ```

   Do **not** name it `VITE_BACKEND_ORIGIN`; values beginning with `VITE_` are built into client-side JavaScript.
3. Do not set `VITE_API_BASE_URL` for this Vercel deployment. Production defaults to the included same-origin proxy.
4. Deploy and copy the final HTTPS Vercel URL into the Render values in step 1, then redeploy both services.

The Vercel function forwards `/api/*` to Render without changing the URL shown to the browser. It forwards secure session cookies as first-party Vercel cookies, avoiding third-party-cookie restrictions.

## 3. Configure Google OAuth

In Google Cloud Console:

1. Enable Gmail API.
2. Configure the OAuth consent screen with truthful application and privacy/contact details.
3. Under **Authorized redirect URIs**, add exactly:

   ```text
   https://YOUR_VERCEL_DOMAIN/api/gmail/callback
   ```

4. Add the production Vercel domain under **Authorized JavaScript origins** if Google Cloud asks for it.
5. In the OAuth branding/App Domain page, set the final Vercel URLs for the homepage, privacy policy, and terms of service:

   ```text
   https://YOUR_VERCEL_DOMAIN/
   https://YOUR_VERCEL_DOMAIN/privacy
   https://YOUR_VERCEL_DOMAIN/terms
   ```

   The home page links to the same privacy policy shown on the consent screen and includes clear Gmail data-use notices.
6. Keep the consent screen in Testing only for named test accounts. To let the general public connect Gmail, submit the app for Google verification. `gmail.readonly` and `gmail.send` are restricted Gmail scopes, so approval and any required security assessment are external Google requirements.

## 4. Launch smoke test

Run this after every production deployment:

1. Open the Vercel URL in an incognito/private window.
2. Select **Sign in with Google**, then accept the consent flow.
3. Confirm the browser returns to `/gmail`, shows the connected account, and `https://YOUR_RENDER_DOMAIN/health/ready` remains ready.
4. Sync one or two messages. Confirm the job completes and the same email does not appear under a different Google account.
5. Generate a reply draft, edit it, explicitly approve it, and send only to a test recipient.
6. Check Render logs for request IDs and worker restart errors. Never paste OAuth tokens, Gmail content, database URLs, or API keys into logs or issues.

Users can remove saved Gmail credentials from **Gmail Inbox → Your data controls → Disconnect Gmail**. They can permanently remove their stored workspace data only after typing `DELETE`; the app clears the user-scoped Chroma vectors before deleting the database account.

## Operational limits

- The Render blueprint intentionally co-locates API and worker because a single persistent Chroma disk cannot be shared by independent Render services. Move semantic indexing to managed vector storage before horizontally scaling workers.
- PostgreSQL is the durable product data source. Chroma can be rebuilt by running a user-scoped reindex.
- Google verification is not automated by this repository. Until it is approved, only configured test users can complete the Gmail OAuth flow.
