# Current Limitations

- Phase 12 adds public homepage, privacy, terms, and data-deletion pages for OAuth launch readiness. Public use of `gmail.readonly`/`gmail.send` still requires a correctly configured Google OAuth consent screen and Google's verification/security review process where applicable.
- Gmail scopes are deliberately limited to `gmail.readonly` and `gmail.send`; the app cannot modify mailbox labels or delete messages.
- Reply All and attachment generation/sending are intentionally unsupported.
- Chroma is embedded persistence for the current project scope, not a large multi-tenant enterprise vector platform.
- LLM classification and summaries are probabilistic and should be evaluated/tuned as inbox content changes.
- Gmail and Mistral API quotas still apply; Phase 7 retries are bounded and avoid unlimited retries.
- Docker Compose is local orchestration, not a cloud HA deployment. Production backups, monitoring, Google OAuth verification, and cookie behavior across custom frontend/backend domains need deployment validation.
