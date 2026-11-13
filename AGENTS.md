# Project development

Use **uv** for all Python dependency and virtual-environment management.

- Run commands from the repository root with `uv run --locked ...`.
- Set up or refresh the root `.venv` with `uv sync --locked`; `.python-version` selects Python 3.12.
- Runtime dependencies belong to the backend workspace member: `uv add --package near-echoes <package>`.
- Development/test dependencies belong to the root group: `uv add --dev <package>`.
- Keep `uv.lock` updated with manifest changes. Do not use pip, manually create environments, or add `.vendor` to Python's import path.
- Verify Python changes with `uv run --locked pytest backend/tests -q` and, for renderer/provenance changes, `uv run --locked python scripts/verify_epoch.py`.

Frontend dependencies continue to use npm; Rust dependencies continue to use Cargo.

After completing and validating project changes, create a Git commit as requested by the owner. Include only the intended project changes; never commit credentials, raw captures, private replay state or unrelated files. Prepared public demo assets may be committed after the publisher's verification and allowlist checks pass.
