Open Questions / TODO
=====================

Open work items and unresolved questions. Design decisions already taken live in
[DESIGN.md](docs/DESIGN.md).

- Create JsonSchemaForm
- EditGridWrapper is not a complete dialog, but the interface needed to edit a collection. The refresh button is the only button to affect the table as a whole (refresh the UI from the model). For collections, we never have a *save* semantics. What to conclude for EditFormWrapper?
  - refresh button possible and makes sense, but already provided by ModelForm
  - save button also provided
- provide examples and tests for nested data structures
- display collections in a responsive card grid in addition to grid/table
- provide optional search and filtering mechanisms for the tables
- Collections: allow querying specific subsets
- Collections: analyze efficiency, caching, paging
- **Support dataclasses**: In addition to Pydantic models.
- **Multi-key modelselect (n:m references)**: the plural of the key-select field — a `list[str]`
  of foreign keys into a CollectionAdapter, edited via a searchable multi-select showing the
  collection's labels. Distinct from `editgrid` (which embeds child objects, i.e. composition).
  Reuse the key-select resolution (field-name repositories, existence validation) with
  `multiple=True`.
