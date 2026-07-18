Open Questions / TODO
=====================

Open work items and unresolved questions. Design decisions already taken live in
[DESIGN.md](DESIGN.md).

- **Introduce a CHANGELOG and versioning/tags**: breaking changes (strict kwargs,
  explicit `render()`, lenient loading default) are currently only recorded in commit
  messages. Add `CHANGELOG.md`, bump to 0.2.0 and start tagging releases.
- EditGridWrapper is not a complete dialog, but the interface needed to edit a collection. The refresh button is the only button to affect the table as a whole (refresh the UI from the model). For collections, we never have a *save* semantics. What to conclude for EditFormWrapper?
  - refresh button possible and makes sense, but already provided by ModelForm
  - save button also provided
- provide examples and tests for nested data structures
- display collections in a responsive card grid in addition to grid/table
- provide optional search and filtering mechanisms for the tables
- Collections: allow querying specific subsets
- Collections: analyze efficiency, caching, paging
- **Support dataclasses**: In addition to Pydantic models.
