# Deferred work

## Deferred from: code review of spec-bmad-loop-issue-tracking-integration.md (2026-08-20)

- No pytest cases for `post-issue-comment.yaml` extraction — add in a follow-up test pass
- `gh -R "{host}/{project}"` rejects `host` with scheme — convention already enforced by module's existing config validators
- No input validation guards in `post-issue-comment.yaml` — callers (code-review, dev-story, story-track-review) guarantee variables in scope
- No retry/backoff for transient 5xx/network errors — out of scope for refactor
- No `platform` value validation in story-track-dev step 1 — would need a CHECK before INCLUDE
- `prd.md` missing → no fallback in story-track prompts — indicates a broken setup, deferred to a separate hardening pass
