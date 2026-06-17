# NiceView Examples

Run any example from the project root:
```bash
uv run python examples/01_form_basic.py
```

| # | File | Shows | Backend |
|---|---|---|---|
| 01 | `01_form_basic.py` | `ModelForm` with a simple model, `on_change` callback | in-memory |
| 02 | `02_field_types.py` | All supported field types in one form | in-memory |
| 03 | `03_form_binding.py` | NiceGUI `bind_text_from` tracking form changes in a second panel | in-memory |
| 04 | `04_form_json.py` | JSON persistence: autosave variant, save/refresh buttons, raw JSON viewer | JSON file |
| 05 | `05_grid.py` | `ModelGrid` (read-only), `ModelGridInlineEdit`, JSON backend | in-memory + JSON |
| 06 | `06_edit_wrapper.py` | `EditGridWrapper` and `EditFormWrapper` (Add / Edit / Delete dialogs) | in-memory |
| 07 | `07_sqlmodel.py` | `SqlModelAdapter` with two related SQLModel tables | SQLite |
