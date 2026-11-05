# Project workflow

- After each complete, coherent round of changes, commit and push to `origin` (`https://github.com/lvmingjin77-ui/paperAgents.git`) so the user can roll back. This is standing user authorization; do not ask again for routine commits and pushes. If pushing fails, preserve the local commit and report the reason.
- Keep commits focused, describe the completed change, and preserve existing history. Do not force-push.
- Never commit API keys, credentials, local environments, research run outputs, or local backup directories.
- The user operates research runs and experiments. Do not start them unless explicitly requested.
- Keep the research workflow and code simple; avoid redundant stages and defensive patches.
