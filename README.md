NiceView
========

[![CI](https://github.com/clausgf/niceview/actions/workflows/ci.yml/badge.svg)](https://github.com/clausgf/niceview/actions/workflows/ci.yml)

NiceView simplifies [NiceGUI](https://nicegui.io) programming by deriving forms and tables from Pydantic models. Inspired by [MagicGUI](https://magicgui.readthedocs.io/), [NiceCRUD](https://github.com/zauberzeug/nicegui/tree/main/examples/nicecrud) and [Django](https://docs.djangoproject.com/)'s admin integration.


Quick Start
-----------

```python
import pydantic
from nicegui import ui
from niceview.modelform import ModelForm

class User(pydantic.BaseModel):
    name: str = pydantic.Field(default='', max_length=50, title='Name')
    age: int = pydantic.Field(default=0, ge=0, le=150)
    active: bool = True

user = User(name='Alice', age=30)

@ui.page('/')
def main():
    form = ModelForm.from_item(user)
    form.render()

ui.run()
```


Contents
--------

- [API Design](#api-design)
- [ModelForm](#modelform)
- [ModelGrid / ModelGridInlineEdit](#modelgrid--modelgridinlineedit)
- [EditGridWrapper / EditFormWrapper](#editgridwrapper--editformwrapper)
- [ModelList / DrillDownWrapper](#modellist--drilldownwrapper)
- [Data Adapters](#data-adapters)
- [Supported Field Types](#supported-field-types)
- [Field Customization](#field-customization)
- [Validation](#validation)
- [Development](#development)
- [Design Decisions and Accepted Technical Debt](#design-decisions-and-accepted-technical-debt)
- [Open Questions / TODO](#open-questions--todo)


API Design
----------

NiceView follows a consistent factory pattern across all backends and UI components:

| | **ModelForm** (single item, fields only) | **EditFormWrapper** (single item + chrome) | **ModelGrid / ModelGridInlineEdit** (list) |
|---|---|---|---|
| **In-memory** | `ModelForm.from_item(Type, instance)` | `EditFormWrapper.from_item(Type, instance)` | `ModelGrid.from_list(Type, items)`<br>`EditGridWrapper.from_list(Type, items)` |
| **JSON file** | `ModelForm.from_json(Type, path)` | `EditFormWrapper.from_json(Type, path)` | `ModelGrid.from_json(Type, path)`<br>`EditGridWrapper.from_json(Type, path)` |
| **Any adapter** | `ModelForm.from_adapter(Type, adapter, key)` | `EditFormWrapper.from_adapter(Type, adapter, key)` | `ModelGrid.from_adapter(Type, adapter)`<br>`EditGridWrapper.from_adapter(Type, adapter)` |

All `from_*` methods accept the same keyword options (see below).
`ModelGridInlineEdit` uses the same factory methods as `ModelGrid` via inheritance.
`EditFormWrapper` wraps a `ModelForm` and adds a title, description, and action buttons.

**Data adapters** are the abstraction layer between UI components and storage backends.
The `from_*` convenience methods create and hide the adapter; pass an adapter explicitly
for full control or when using SQL / custom backends.


ModelForm
---------

`ModelForm` renders a Pydantic model as an editable form (fields only — no chrome).
Use `EditFormWrapper` to add a title, description, and action buttons.

```python
from niceview.modelform import ModelForm

# In-memory item (explicit type optional)
form = ModelForm.from_item(user)
form = ModelForm.from_item(User, user)

# JSON file — persists on save, supports refresh
form = ModelForm.from_json(User, Path('user.json'))

# Any CollectionAdapter — full control over storage
form = ModelForm.from_adapter(User, adapter, str(key))

form.render()
```

**Options** (apply to all `ModelForm` and `ModelGrid` factory methods):
```python
ModelForm.from_item(user,
    include=['name', 'age'],          # or exclude=['active']
    field_infos={'age': niceview.Field(label='Age')},  # per-field overrides
    autosave=True,                    # save after every validated change
    local_tz='Europe/Berlin',         # timezone for datetime display
    on_change=my_callback,            # called after every validated change
)
```

**Runtime item switching** (master-detail navigation):
```python
# load() switches the displayed item and binds a new adapter
form.load(adapter, str(row_key))     # convenience: wraps in BoundItem
form.load(BoundItem(adapter, key))   # explicit BoundItem

# item setter — only for unbound forms (from_item); raises on adapter-bound forms
form.item = updated_user
```

**Adapter state and validation**:
```python
form.adapter_bound          # True if save()/refresh() are available
form.has_validation_errors  # True if any field or model errors present
form.validation_errors      # dict[str, str] — field-level errors
form.nonfield_validation_errors  # list[str] — model-level errors
```

**Change events** carry field name and old/new value:
```python
form.on_change(lambda e: print(e.field_name, e.previous_value, e.value))
```


ModelGrid / ModelGridInlineEdit
--------------------------------

`ModelGrid` renders a list as a read-only AgGrid table.
`ModelGridInlineEdit` adds per-cell editing with immediate validation and persistence.

```python
from niceview.modelgrid import ModelGrid, ModelGridInlineEdit

# In-memory list
grid = ModelGrid.from_list(User, user_list, include=['name', 'age'])
grid = ModelGridInlineEdit.from_list(User, user_list)

# JSON file: created with [] if missing; Refresh button reloads from disk
grid = ModelGrid.from_json(User, Path('users.json'))
grid = ModelGridInlineEdit.from_json(User, Path('users.json'))

# Any adapter (two equivalent forms)
grid = ModelGrid(User, adapter)                   # constructor
grid = ModelGrid.from_adapter(User, adapter)      # for API symmetry with ModelForm.from_adapter()

grid.render()
grid.on_change(lambda e: print(e.row_key, e.field_name, e.new_value))
grid.adapter      # read-only property — returns the backing CollectionAdapter
```


EditGridWrapper / EditFormWrapper
----------------------------------

Both wrappers add a title, optional description, and action buttons as chrome above their inner component.

```python
from niceview.modeledit import EditGridWrapper, EditFormWrapper

# Grid with CRUD buttons — factory methods create and render in one call
EditGridWrapper.from_list(User, user_list, title='Users')
EditGridWrapper.from_json(User, Path('users.json'), title='Users')
EditGridWrapper.from_adapter(User, adapter, title='Users')

# inline_edit=True uses ModelGridInlineEdit instead of ModelGrid
EditGridWrapper.from_list(User, user_list, title='Users', inline_edit=True)

# Form with chrome — factory methods mirror ModelForm's, accept all ModelForm options plus wrapper options
EditFormWrapper.from_item(user, title='Edit User')
EditFormWrapper.from_json(User, Path('user.json'), title='Config', autosave=True)
EditFormWrapper.from_adapter(User, adapter, key, title='Edit User')

# repositories= wires up modelselect fields (for FK relationships in EditFormWrapper)
EditFormWrapper.from_adapter(Book, books_adapter, book_id, title='Edit Book',
                             repositories={Author: authors_adapter})
```

**`EditGridWrapper` button defaults** — all buttons shown by default (icon only):

| Option | Default | Description |
|---|---|---|
| `add_button` | `''` (icon) | Opens create dialog |
| `edit_button` | `''` (icon) | Opens edit dialog; `None` for `ModelGridInlineEdit` |
| `delete_button` | `''` (icon) | Deletes selected row after confirmation |
| `refresh_button` | `''` (icon) | Reloads from adapter |

**`EditFormWrapper` button defaults** — depend on whether an adapter is bound:

| Factory | `save_button` | `refresh_button` |
|---|---|---|
| `from_item()` | `None` (hidden) | `None` (hidden) |
| `from_json()` | `''` (icon) | `''` (icon) |
| `from_adapter()` | `''` (icon) | `''` (icon) |

Autosave always suppresses `save_button`. Pass `None` to hide any button; pass a string to set its label (`''` = icon only).

**Exposed NiceGUI elements** — chrome elements are accessible for styling after the factory call:
```python
# EditGridWrapper
wrapper = EditGridWrapper.from_list(User, user_list, title='Users')
wrapper.title                              # ui.label | None
wrapper.description                        # ui.markdown | None
wrapper.title_row                          # ui.row | None
wrapper.add_button.props('color=primary')  # ui.button | None
wrapper.edit_button                        # ui.button | None
wrapper.delete_button                      # ui.button | None
wrapper.refresh_button                     # ui.button | None

# EditFormWrapper
wrapper = EditFormWrapper.from_adapter(User, adapter, key, title='Edit User')
wrapper.title.classes('text-primary')      # ui.label | None
wrapper.description                        # ui.markdown | None
wrapper.title_row                          # ui.row | None
wrapper.save_button.props('color=green')   # ui.button | None
wrapper.refresh_button                     # ui.button | None
```

**`EditGridWrapper` options:**
```python
wrapper = EditGridWrapper.from_list(User, users,
    title='Users',        # shown as text-h6; None = no title row
    description='...',    # markdown below the title row
    add_button='Add',     # label or '' for icon-only; None = hidden
    edit_button='',       # same
    delete_button='',     # same
    refresh_button=None,  # same
)
wrapper.with_repositories({Author: authors_adapter})  # type → adapter; for modelselect fields in dialogs
```

**`EditFormWrapper` options** (all `ModelForm` options also accepted):
```python
EditFormWrapper.from_item(user,
    title='Edit User',           # shown as text-h6; None = no title row
    description='...',           # markdown below the title row
    save_button='Save',          # label or '' for icon-only; None = hidden
    refresh_button='',           # same
    repositories={Author: authors_adapter},  # modelselect FK fields
    # ModelForm options:
    include=['name', 'age'],
    autosave=True,
    local_tz='Europe/Berlin',
    on_change=my_callback,
)
```


ModelList / DrillDownWrapper
----------------------------

`ModelList` renders a collection as a Quasar list — tappable rows with a title and subtitle,
suited for mobile-first single-column navigation. `DrillDownWrapper` registers two NiceGUI pages
(list + per-item detail) and wires up navigation between them.

**Responsive layout** is built in — no API changes needed:
- Mobile (< 1024 px): separate list and detail pages with drill-down navigation
- Desktop (≥ 1024 px): split-panel — list on the left, form on the right, side by side

```python
from niceview.modellist import ModelList, DrillDownWrapper

# Standalone list — fire on_select callback when an item is tapped
list_view = ModelList.from_list(User, users,
    title_field='name',               # first visible field by default
    subtitle_fields=['email'],        # next two visible fields by default
)
list_view.on_select(lambda e: print(e.row_key, e.item))
list_view.render()

# Drill-down: register list + detail pages, then ui.run()
DrillDownWrapper.from_list(User, users,
    title='Users',
    title_field='name',
    subtitle_fields=['email', 'active'],
).register('/users')

# Works with any adapter
DrillDownWrapper.from_json(User, Path('users.json'), title='Users').register('/users')
DrillDownWrapper.from_adapter(User, adapter, title='Users').register('/users')
```

**Page structure** after `register(base_path)`:

| Page | URL | Chrome |
|---|---|---|
| List | `base_path` | Header with title + Add button |
| Detail | `base_path/{key}` | Header with Back + item title + Delete button; form with Save/Refresh |

`register()` must be called before `ui.run()`. Multiple wrappers can be registered at different base paths.

**`DrillDownWrapper` options:**
```python
DrillDownWrapper.from_list(User, users,
    title='Users',           # list page header title
    title_field='name',      # field shown as item title (auto-detected if omitted)
    subtitle_fields=['email'],  # fields shown as subtitle (next two visible fields if omitted)
    add_button='',           # '' = icon only; None = hidden
    delete_button='',        # same
    # ModelList options forwarded:
    include=['name', 'email'],
    exclude=['secret'],
)
```


Data Adapters
-------------

Adapters decouple UI components from storage. Pass them explicitly for full control,
or let the `from_*` factory methods create them transparently.

| Adapter | Backs | Description |
|---|---|---|
| `ListAdapter(Type, list)` | Grid | In-memory list |
| `JsonAdapter(Type, path)` | Form | Single object in a JSON file |
| `JsonListAdapter(Type, path)` | Grid | List of objects in a JSON file |
| `SqlModelAdapter(Type, engine)` | Grid, Form | SQLModel / SQLAlchemy table |

All JSON adapters write atomically (`.tmp` → rename).
`JsonListAdapter` and `SqlModelAdapter` both implement `ReloadableAdapter`: `reload()` re-reads
from disk (JSON) or fires a grid-refresh notification (SQL, where every `read()` is already live).

**Adapter protocols** — implement these for custom backends:

| Protocol | Methods | Used by |
|---|---|---|
| `ItemAdapter[T]` | `read() -> T`, `save(item) -> T` | `ModelForm` |
| `CollectionAdapter[T]` | `__iter__`, `key_from_item(item) -> str`, `read(key) -> T`, `create(item) -> T`, `update(item) -> T`, `delete(key)` | `ModelGrid`, `EditGridWrapper` |
| `ReloadableAdapter` | `reload()` | `EditGridWrapper` (Refresh button), `FilteredAdapter` (forwarded) |
| `ReactiveAdapter` | `on_change(handler)` | `ModelGrid` (auto-update) |

`update()` returns the stored item, which may differ from the input (e.g. `SqlModelAdapter` refreshes `updated_at`). `key_from_item()` raises `KeyError` if the item is not in the adapter; `read()` raises `KeyError`/`ValueError` if the key is not found.

`BoundItem(adapter, key)` wraps a `CollectionAdapter` + a string key into an `ItemAdapter` —
the standard bridge for master-detail navigation (e.g. `ModelForm.from_adapter()`).
`BoundItem` can be imported directly from `niceview` (`from niceview import BoundItem`).

**Reactive updates**

All built-in adapters implement `ReactiveAdapter` via the `_ChangeNotifier` mixin.
`ModelGrid.render()` detects this and registers `update_rows()` automatically, so
structural mutations through the adapter (create / update / delete) refresh the grid
without any manual call — for in-memory lists, JSON files, and SQL databases alike.

What is **not** caught automatically: in-place attribute changes on existing items
(`item.name = 'new'`). These bypass the adapter entirely. Use `grid.update_rows()`
or the `EditGridWrapper` Refresh button for that case.

```python
# Adapter mutations → grid auto-updates (all adapter types)
adapter = ListAdapter(User, items)
grid = ModelGridInlineEdit.from_adapter(User, adapter)
grid.render()
adapter.create(User(name='Carol'))   # grid refreshes automatically
adapter.delete(key)                  # grid refreshes automatically

# In-place attribute change → manual refresh needed
items[0].name = 'new name'
grid.update_rows()                   # must call explicitly
```

**ObservableList** additionally catches direct mutations on the list object that
bypass the adapter — useful when non-NiceView code appends to the same list:

```python
from nicegui.observables import ObservableList

obs = ObservableList([User(name='Alice')])
grid = ModelGrid.from_list(User, obs)
grid.render()
obs.append(User(name='Bob'))   # also triggers update_rows(), no adapter call needed
```

```python
from niceview.dataadapter import SqlModelAdapter

adapter = SqlModelAdapter(Book, engine)                    # with optimistic locking (updated_at)
adapter = SqlModelAdapter(Book, engine, lock_field=None)   # without locking

# Form for a specific record (fields only) — key must be str
form = ModelForm.from_adapter(Book, adapter, str(book_id))
form.render()

# Form with chrome (title + save/refresh buttons)
EditFormWrapper.from_adapter(Book, adapter, str(book_id), title='Edit Book')

# Grid over the full table
ModelGrid(Book, adapter).render()
EditGridWrapper.from_adapter(Book, adapter, title='Books')
```


Supported Field Types
---------------------

NiceView automatically selects a widget based on the Python type annotation:

| Python type | Widget |
|---|---|
| `str` | `ui.input` |
| `int`, `float` | `ui.number` |
| `bool` | `ui.switch` |
| `datetime.date` | HTML date input |
| `datetime.time` | HTML time input |
| `datetime.datetime` | HTML datetime-local input |
| `datetime.timedelta` | `ui.input` (ISO 8601 duration) |
| `Literal['a', 'b', ...]` | `ui.select` |
| `list[str]` | `ui.input_chips` |
| `list[BaseModel]` | Inline `EditGridWrapper` |
| `Optional[T]` | Unwrapped to `T`, then same as above |
| SQLModel relationship (single) | `modelselect` (select backed by model repository) |
| SQLModel relationship (list) | Inline `EditGridWrapper` |

Additional widgets can be selected explicitly via `niceview.Field(widget_type='...')`:

| `widget_type` | Widget | Typical use |
|---|---|---|
| `'ui.textarea'` | `ui.textarea` | Long text / multi-line strings |
| `'ui.checkbox'` | `ui.checkbox` | Boolean (alternative to `ui.switch`) |
| `'ui.radio'` | `ui.radio` | `Literal` / enum with radio buttons |
| `'ui.toggle'` | `ui.toggle` | `Literal` / enum with toggle buttons |
| `'ui.color_input'` | `ui.color_input` | Hex color picker |
| `'slider'` | `ui.slider` | `int`/`float` with a visual range slider; `min`/`max` from `ge`/`le` constraints |
| `'rating'` | `ui.rating` | `int` 1–N star rating; `max` from `le` constraint (default 5) |


Field Customization
-------------------

Use `niceview.Field()` as `Annotated` metadata to customize a field:

```python
import niceview
from typing import Annotated

class User(pydantic.BaseModel):
    age: Annotated[int, pydantic.Field(default=0), niceview.Field(min=0, max=150, label="Age")]
    secret: Annotated[str, niceview.Field(hidden=True)] = ''
```

Or via a `Meta` class on the model:

```python
class User(pydantic.BaseModel):
    name: str = ''
    secret: str = ''

    class Meta:
        field_infos = {
            'secret': niceview.Field(hidden=True),
        }
        field_order = ['name', 'secret']   # explicit display order
```

`Meta.field_order` is a list of field names that sets the display order. Fields not listed are appended at the end in their natural order. This is especially useful for SQLModel table classes, which do not guarantee declaration order.

Key `FieldInfo` options: `label`, `placeholder`, `tooltip`, `hidden`, `editable`, `widget_type`, `min`, `max`, `classes`, `select_options`.


Validation
----------

Field-level and model-level (`@model_validator`) errors are displayed in the form. Field errors appear inline below the widget; model-level errors appear at the bottom of the form.


Development
-----------

Install dependencies and run tests:
```bash
uv sync --dev
uv run pytest          # 421 tests
uv run mypy niceview/ --ignore-missing-imports   # 0 errors
```

Run examples:
```bash
uv run python examples/01_form_basic.py
```

The `niceview-split` branch contains only the `niceview/` package directory for easy inclusion as a git subtree in other projects.

Update `niceview-split` from `main`:
```bash
git subtree split --prefix=niceview --branch niceview-split main
git push origin niceview-split --force
```

Pull the latest `niceview-split` into a consuming project:
```bash
git fetch niceview
git subtree pull --prefix=niceview niceview niceview-split --squash
```

Unit tests cover data adapters, field resolution, validation logic, and pure CRUD operations.
Acceptance tests (`tests/test_acceptance.py`) use the NiceGUI `User` fixture (headless, no browser)
to verify render output and widget↔model interaction. AgGrid cell content is JS-rendered and
not inspectable via the `User` fixture; row data is covered by unit tests instead.


Design decisions and Accepted Technical Debt
--------------------------------------------
- **Mobile navigation: `ModelList` + `DrillDownWrapper` as separate components**: A new `ModelList` (Quasar list) and `DrillDownWrapper` (two registered NiceGUI pages) are added alongside `ModelGrid` / `EditGridWrapper` rather than making the existing desktop components responsive. Motivation: the UX patterns are fundamentally different — card list with drill-down vs data table with dialogs — and a single component handling both would need too many conditional paths. The state-sharing problem between pages is solved by the `DrillDownWrapper` instance holding the adapter (shared per Python process, which is the normal NiceGUI single-user model).
- **`DrillDownWrapper` split-panel layout**: Implemented as pure CSS using Quasar breakpoint utility classes (`gt-sm`, `lt-md`, `col-4`, `col-md-8`). No API changes, no JavaScript, no conditional Python logic. The list panel on the detail page is rendered unconditionally but hidden on mobile via `gt-sm`. This means on desktop, clicking a list item in the side panel navigates to a new URL (`base_path/{key}`) which re-renders the same split-panel layout with the new item selected.
- **Form navigation / dirty state**: No detection when the user leaves an unsaved form. Options: (a) track dirty state via `on_change` and expose `is_dirty` property; (b) use a JS `beforeunload` guard (requires NiceGUI `ui.run_javascript`). Neither covers in-app navigation — NiceGUI has no built-in route guard.
- **NiceGUI element lifecycle**: When are elements instantiated, active, deleted? `render()` must be called inside a NiceGUI page context; elements created outside a client context silently fail. No lifecycle hooks for cleanup.
- **Tests for async dialog flows**: `create_item` / `update_item` / `delete_item` open a NiceGUI dialog (`await dialog`) and cannot be tested without a browser. The CRUD data operations are covered via `_apply_create`, `_apply_update`, `_apply_delete` (unit tests) and the render/button presence via acceptance tests. Full dialog flow testing would require the `Screen` fixture (Playwright-based).
- Design decision **date/time/datetime**: Use Python data types and HTML native widgets instead of NiceGUI/Quasar widgets with strings.
- **`ui.notify()` in `save()`/`refresh()`**: Both methods call `ui.notify()` unconditionally. Callers who want custom feedback or suppress the popup have no opt-out today. Options: `notify=True` parameter, or an overridable `_on_save_success()`/`_on_save_error()` hook method. Deferred — the default behaviour is what most apps need, and adding a parameter to every call site adds noise.
- **`ModelForm[T]` generics**: Making `ModelForm` generic would allow `form.item` to return `T` instead of `BaseModel`, eliminating casts in callers. The machinery is non-trivial: `@classmethod` + `TypeVar` generics are awkward pre-3.12, and internal fields (`_current_item`, `_validated_item`) would need careful typing. Deferred — the benefit is modest since callers rarely access `form.item` directly and `model_copy()`/`model_validate()` stay untyped internally anyway.


Open Questions / TODO
---------------------
- EditGridWrapper is not a complete dialog, but the interface needed to edit a collection. The refresh button is the only button to affect the table as a whole (refresh the UI from the model). For collections, we never have a *save* semantics. That to conclude for EditFormWrapper?
  - refresh button possible and makes sense, but already provided by ModelForm
  - save button also provided
- provide examples and tests for nested data structures
- display collections in a responsive card grid in addition got grid/table
- **Context-specific layouts**: How to render the same Pydantic model differently in different forms or grids (different fields, labels, widgets, order)? `include`/`exclude` covers simple filtering; `field_infos={}` allows per-call overrides but requires repetition. Options to decide between: (A) named profiles in `Meta` (`profile='summary'`), (B) Pydantic model subclasses with their own `Meta`, (C) explicit layout classes à la Django's `ModelForm`. Need to decide which fits NiceView's design best.
- provide optional search and filtering mechanims to the tables
- Collections: allow querying specific subsets
- Collections: analyze efficiency, caching, paging
- **Support dataclasses**: In addition to Pydantic models.
