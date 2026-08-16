niceview
========

NiceView simplifies [NiceGUI](https://nicegui.io) programming by deriving forms and tables from Pydantic or SqlModel models: the widget for each type, the layout, and validation against the model, shown inline at the field it belongs to, cross-field rules included. Persistence is a swappable adapter (a JSON file, a directory of files, SQL through SqlModel, or your own) with save, refresh, autosave and optimistic locking already wired up. The same model renders as a desktop table or as a mobile list ↔ detail drill-down.

<p align="center">
  <img src="img/hero.png" width="430" alt="A ModelForm rendered from a Pydantic model — text, select, toggle, number, slider, switch, multi-select chips, color and textarea widgets"><br>
  <sub>One <code>ModelForm.from_item(...)</code> call, rendered from a Pydantic model.</sub>
</p>


Installation
------------

```bash
uv add git+https://github.com/clausgf/niceview          # or: pip install git+https://...
uv add "niceview[sqlmodel] @ git+https://github.com/clausgf/niceview"   # with SqlModelAdapter
```

`SqlModelAdapter` is the only component with an extra dependency (`sqlmodel`); everything else
works with the base install. All public names are importable directly from `niceview`
(`from niceview import ModelForm, ModelGrid, ...`).


Quick start
-----------

```python
import pydantic
from nicegui import ui
from niceview import ModelForm

class User(pydantic.BaseModel):
    name: str = pydantic.Field(default='', max_length=50, title='Name')
    age: int = pydantic.Field(default=0, ge=0, le=150)
    active: bool = True

user = User(name='Alice', age=30)

@ui.page('/')
def main():
    ModelForm.from_item(user).render()

ui.run()
```

Every component follows the same create-then-render pattern: the factory returns the instance,
`render()` draws it into the current NiceGUI context and returns the instance again — so the
fluent one-liner `X.from_list(...).render()` always works. Unknown keyword arguments raise
`TypeError` rather than being silently dropped.


Components at a glance
----------------------

| Component | Purpose |
|---|---|
| [`ModelForm`](components.md#modelform) | A Pydantic model as an editable form (fields only, no chrome) |
| [`ModelGrid` / `ModelGridInlineEdit`](components.md#modelgrid--modelgridinlineedit) | A list as a read-only or inline-editable AgGrid table |
| [`EditGridWrapper` / `EditFormWrapper`](components.md#editgridwrapper--editformwrapper) | Grid/form plus title, description and CRUD/action buttons |
| [Card-based list editing](components.md#card-based-list-editing) | One autosaving `ModelForm` per item, custom layout |
| [`ModelList` / `DrillDownWrapper`](components.md#modellist--drilldownwrapper) | Mobile-first list ↔ detail drill-down navigation |
| [`render_field` / `field_value`](components.md#render_field--a-single-widget-without-a-model) | One widget from one `Field()`, without a model |

<table>
  <tr>
    <td align="center" valign="top">
      <img src="img/grid.png" width="440" alt="EditGridWrapper: a table with add, edit, delete and refresh buttons"><br>
      <sub><b>EditGridWrapper</b> — table with add / edit / delete / refresh</sub>
    </td>
    <td align="center" valign="top">
      <img src="img/drilldown.gif" width="250" alt="DrillDownWrapper: tapping a row slides to its detail form and back"><br>
      <sub><b>DrillDownWrapper</b> — mobile list ↔ detail drill-down</sub>
    </td>
  </tr>
</table>


Where to go next
----------------

- **[Concepts](CONCEPT.md)** — how the chrome, field and text cascades fit together
- **[Components](components.md)** — the guide: layout, actions, validation, chrome styling, the
  model-free `render_field`
- **[Data adapters](adapters.md)** — storage backends, lenient loading, optimistic locking,
  reactive updates, the adapter protocols
- **[Field types](field-types.md)** — type→widget mapping, `niceview.Field()` options,
  `Meta` profiles
- **[API reference](api/forms.md)** — every public class and function, generated from the source
- **[Design decisions](DESIGN.md)** — what was decided against, and why

The [examples](https://github.com/clausgf/niceview/tree/main/examples) are runnable: each one is
a single file that starts a NiceGUI app and explains itself on its own first page.
