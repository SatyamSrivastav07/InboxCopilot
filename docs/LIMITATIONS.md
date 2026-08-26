# Current Limitations

- The OAuth/token model is local and single-user oriented; it is not multi-tenant identity management.
- Gmail scopes are deliberately limited to `gmail.readonly` and `gmail.send`; the app cannot modify mailbox labels or delete messages.
- Reply All and attachment generation/sending are intentionally unsupported.
- Chroma is embedded persistence for the current project scope, not a large multi-tenant enterprise vector platform.
- LLM classification and summaries are probabilistic and should be evaluated/tuned as inbox content changes.
- Gmail and Mistral API quotas still apply; Phase 7 retries are bounded and avoid unlimited retries.
- Docker Compose is local orchestration, not a cloud HA deployment. Production HTTPS, secrets management, backups, monitoring, and multi-user authorization need further work.
