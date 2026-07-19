Contributing to NiceView
========================

Thanks for your interest in improving NiceView! This project uses
[uv](https://docs.astral.sh/uv/) for dependency management.

Getting started
---------------

```bash
uv sync --dev
```

This also editable-installs `niceview` into `.venv`, so the example scripts and your own code
can `import niceview` directly. In VS Code, select the `.venv` interpreter (auto-detected; the
repo ships a `.vscode/` config) and run any example with the ▶ Run button or F5.

Before opening a pull request
-----------------------------

Run the full check suite and make sure it passes:

```bash
uv run pytest
uv run mypy niceview/ --ignore-missing-imports
uv run ruff check
```

- **Tests**: add unit tests for logic and, where it makes sense, acceptance tests using the
  NiceGUI `User` fixture. Please do **not** change existing acceptance tests without discussing it
  first in an issue.
- **Types**: the library ships a `py.typed` marker; keep the public API fully typed and mypy-clean.
- **Docs**: update the relevant page (the `README.md` landing page or the reference pages under
  `docs/`) when you change behavior.
- **Changelog**: record any user-facing / API change under `[Unreleased]` in
  [`docs/CHANGELOG.md`](docs/CHANGELOG.md).

Design notes
------------

Architectural decisions and consciously accepted trade-offs are recorded in
[`DESIGN.md`](DESIGN.md); open questions and planned work live in [`TODO.md`](TODO.md).
If your change touches one of those, update it in the same PR.

Reporting bugs / requesting features
------------------------------------

Please use the GitHub [issue tracker](https://github.com/clausgf/niceview/issues). A minimal
reproducer (a small Pydantic model plus the NiceView call) helps enormously.
