Changelog
=========

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

[Unreleased]
------------

(nothing yet)


[0.11.0] - 2026-08-05
---------------------

### Changed

- `DirectoryAdapter`: hidden dotfiles and `name_filter` now apply in **both** modes, not just
  all-files mode. Previously a `name_filter` passed together with a `suffix` was silently
  ignored. Dotfile exclusion is a real change for suffix mode — `pathlib`'s `glob('*.json')`
  matches `.hidden.json`, so such files were listed before and are not any more.
- `DirectoryAdapter`: `name_filter` receives the full filename (extension included) in both
  modes, never the stripped key.

### Fixed

- `DirectoryAdapter`: a single file whose key cannot round-trip no longer breaks the entire
  listing. A bare `.json` (empty key) or a name containing a path separator raised
  `ValueError` for the whole iteration; such files are now skipped. Addressing one explicitly
  by key still raises.

### Performance

- `DirectoryAdapter` iteration uses `os.scandir` and its cached `DirEntry` stat, halving the
  syscalls per file (`is_file()` + `Path.stat()` previously stat'd every entry twice).
  Measured 3.6x faster at 1000 files and 4.1x at 5000, with identical results. This matters
  because `DrillDownWrapper` iterates synchronously on the NiceGUI event loop, where a slow
  scan stalls every connected client.


[0.10.0] - 2026-08-01
---------------------

### Added

- `DirectoryAdapter`: all-files mode via `suffix=None` (or `''`) — a general, mixed-extension
  file browser. Keys are full filenames (no suffix stripping), every regular file is listed
  (hidden dotfiles excluded, plus an optional `name_filter=Callable[[str], bool]`), and
  `create()` takes a full name. The default `suffix='.json'` document-collection mode and all
  existing calls are unchanged (opt-in, backward-compatible).


[0.9.1] - 2026-07-24
--------------------

### Changed

- Pinned dev/test environment updated to NiceGUI 3.15.0 (declared floor stays `>=3.0`).

### Fixed

- `ModelForm`: clearing a `ui.number` field no longer raises `TypeError` and leaves a stale
  value. A cleared field now maps to `None`, so `Optional` number fields round-trip and required
  number fields fail validation cleanly.
- `ModelForm`: `Optional[int]` number fields are no longer coerced to `float` (e.g. `50` stayed
  `50.0`); the field type is unwrapped so integers stay integers.


[0.9.0] - 2026-07-19
--------------------

### Added

- README screenshots (hero `ModelForm`, `EditGridWrapper` table, `DrillDownWrapper` GIF),
  generated reproducibly by `docs/screenshots/capture.py` (optional `screenshots` dependency group).

### Changed

- Example scripts no longer manipulate `sys.path`; they rely on the editable install created by
  `uv sync`. A `.vscode/` config is included so examples run directly via the Run button / F5.


[0.2.0] - 2026-07-19
--------------------

First tagged release. Everything below is relative to earlier, untagged git installs.

### Breaking changes

- `Edit*Wrapper` factory methods (`from_list`/`from_json`/`from_adapter`/`from_item`) no longer
  render automatically. Call `render()` explicitly — the factories return the instance and
  `render()` returns it again, so the fluent `EditGridWrapper.from_list(...).render()` works.
- Unknown keyword arguments now raise `TypeError` across all component constructors and factories
  instead of being silently ignored.
- The `select_options` / `radio_options` / `toggle_options` / `checkbox_group_options` attributes
  were removed. Use the unified `options` (with `literal_options` still auto-extracted from
  `Literal[...]`). Passing a removed alias raises `TypeError`.
- `util.submit_dialog` is now async and returns the pressed button's text (or `None` on dismissal)
  instead of returning a dialog to await.
- `create_if_not_exist`, `lock_field` and `created_field` are keyword-only in the `from_json`
  factories.
- `FieldInfo` raises `TypeError` (not `ValueError`) on unknown keyword arguments.
- Internal modules renamed for consistency with their class names: `form.py` → `modelform.py`,
  `grid.py` → `modelgrid.py`, `wrapper.py` → `editwrapper.py`; `DrillDownWrapper` moved to a new
  `drilldown.py`. The canonical import path is unchanged (`from niceview import ...`); only code
  importing private submodules directly is affected.
- `JsonAdapter`/`JsonListAdapter` default to lenient loading (`strict=False`); code that relied on
  a malformed file raising must pass `strict=True`.

### Added

- The full public API is exported from the top-level `niceview` package (all UI components,
  adapters, protocols, errors, and the lenient-load helpers).
- `options` accepts sync **or async** callables; async sources render the widget empty and fill in
  choices when the awaitable resolves, preserving the field's value.
- `notify=False` on `ModelForm.save()` / `refresh()` to suppress the `ui.notify` popups.
- `ModelGrid.on_select` delivers `TableItemSelectEventArguments` with `row_key`/`item`
  (both `None` when the selection is cleared), mirroring `ModelList.on_select`.
- `py.typed` marker so downstream type checkers use NiceView's annotations.
- MIT `LICENSE`; richer packaging metadata; `ruff` linting and a mypy step plus a
  Python 3.12/3.13 matrix in CI.
- Documentation split into a slim landing README plus `docs/` reference pages; `DESIGN.md` and
  `TODO.md` for design decisions and open work.

### Fixed

- README quick-start and examples imported non-existent modules (`niceview.modelform`, etc.);
  imports now use the canonical top-level package.
- `pydantic` is declared as a direct dependency (previously only transitive via NiceGUI).
