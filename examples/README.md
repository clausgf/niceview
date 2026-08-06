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
| 08 | `08_reactive_grid.py` | Reactive grids: adapter mutations auto-update the grid; ObservableList also catches direct list mutations | in-memory |
| 09 | `09_drilldown.py` | `DrillDownWrapper` / `ModelList`: embeddable list <-> detail navigation | in-memory |
| 10 | `10_complex_form_navigation.py` | Responsive split-panel master-detail around `ModelForm` | in-memory |
| 11 | `11_tree_navigation.py` | URL-addressable drill-down over three levels, explicit back buttons | in-memory |
| 12 | `12_card_list.py` | Card-based list editing: one autosaving `ModelForm` per item | JSON file |
| 13 | `13_directory_drilldown.py` | `DirectoryAdapter`: one file per item, with rename | directory |
| 14 | `14_render_field.py` | `render_field` / `field_value`: a form built from field metadata, no model | in-memory |
