# Current Limitations

- Phase 9 persists encrypted per-user connection records, but the current browser OAuth flow still uses the legacy local connection. Google sign-in, sessions, and user-scoped API enforcement arrive in Phase 10; do not launch this version publicly as a multi-user service.
- Gmail scopes are deliberately limited to `gmail.readonly` and `gmail.send`; the app cannot modify mailbox labels or delete messages.
- Reply All and attachment generation/sending are intentionally unsupported.
- Chroma is embedded persistence for the current project scope, not a large multi-tenant enterprise vector platform.
- LLM classification and summaries are probabilistic and should be evaluated/tuned as inbox content changes.
- Gmail and Mistral API quotas still apply; Phase 7 retries are bounded and avoid unlimited retries.
- Docker Compose is local orchestration, not a cloud HA deployment. Production backups, monitoring, Google OAuth verification, and multi-user authorization enforcement need further work.
