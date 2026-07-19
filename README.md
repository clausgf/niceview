NiceView
========

[![CI](https://github.com/clausgf/niceview/actions/workflows/ci.yml/badge.svg)](https://github.com/clausgf/niceview/actions/workflows/ci.yml)

NiceView simplifies [NiceGUI](https://nicegui.io) programming by deriving forms and tables from Pydantic models. Inspired by [MagicGUI](https://magicgui.readthedocs.io/), [NiceCRUD](https://github.com/zauberzeug/nicegui/tree/main/examples/nicecrud) and [Django](https://docs.djangoproject.com/)'s admin integration.


Installation
------------

```bash
uv add git+https://github.com/clausgf/niceview          # or: pip install git+https://...
uv add "niceview[sqlmodel] @ git+https://github.com/clausgf/niceview"   # with SqlModelAdapter
```

`SqlModelAdapter` is the only component with an extra dependency (`sqlmodel`); everything else
works with the base install. All public names are importable directly from `niceview`
(`from niceview import ModelForm, ModelGrid, ...`).


Quick Start
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
    form = ModelForm.from_item(user)
    form.render()

ui.run()
```


Contents
--------

- [Installation](#installation)
- [API Design](#api-design)
- [ModelForm](#modelform)
- [ModelGrid / ModelGridInlineEdit](#modelgrid--modelgridinlineedit)
- [EditGridWrapper / EditFormWrapper](#editgridwrapper--editformwrapper)
- [Card-Based List Editing](#card-based-list-editing)
- [ModelList / DrillDownWrapper](#modellist--drilldownwrapper)
- [Data Adapters](#data-adapters)
- [Supported Field Types](#supported-field-types)
- [Field Customization](#field-customization)
- [Validation](#validation)
- [Dialogs](#dialogs)
- [Development](#development)
- [Design Decisions / TODO](#design-decisions--todo) — details in [DESIGN.md](DESIGN.md) and [TODO.md](TODO.md)


API Design
----------

NiceView follows a consistent factory pattern across all backends and UI components:

| | **ModelForm** (single item, fields only) | **EditFormWrapper** (single item + chrome) | **ModelGrid / ModelGridInlineEdit** (list) |
|---|---|---|---|
| **In-memory** | `ModelForm.from_item(Type, instance)` | `EditFormWrapper.from_item(Type, instance)` | `ModelGrid.from_list(Type, items)`<br>`EditGridWrapper.from_list(Type, items)` |
| **JSON file** | `ModelForm.from_json(Type, path, lock_field=, created_field=)` | `EditFormWrapper.from_json(Type, path, lock_field=, created_field=)` | `ModelGrid.from_json(Type, path)`<br>`EditGridWrapper.from_json(Type, path)` |
| **Any adapter** | `ModelForm.from_adapter(Type, adapter, key?)` | `EditFormWrapper.from_adapter(Type, adapter, key?)` | `ModelGrid.from_adapter(Type, adapter)`<br>`EditGridWrapper.from_adapter(Type, adapter)` |

All `from_*` methods accept the same keyword options (see below); unknown keyword
arguments raise `TypeError` instead of being silently ignored.
All components follow the same create-then-render pattern: the factory returns the
instance, `render()` draws it into the current NiceGUI context and returns the
instance again, so the fluent one-liner `X.from_list(...).render()` always works.
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
from niceview import ModelForm

# In-memory item (explicit type optional)
form = ModelForm.from_item(user)
form = ModelForm.from_item(User, user)

# JSON file — persists on save, supports refresh; optional locking / timestamps
form = ModelForm.from_json(User, Path('user.json'))
form = ModelForm.from_json(User, Path('user.json'), lock_field='updated_at', created_field='created_at')

# CollectionAdapter + key — any storage backend
form = ModelForm.from_adapter(User, adapter, str(key))

# ItemAdapter directly (e.g. JsonAdapter) — no key needed
form = ModelForm.from_adapter(User, json_adapter)

form.render()
```

**Custom field layout** — render fields individually to control placement in rows/columns:
```python
form = ModelForm.from_item(user)
with ui.row():
    with ui.column():
        form.render_field('name').classes('w-full')   # returns the widget for direct styling
        form.render_field('age').classes('w-full')
    with ui.column():
        form.render_field('active')
form.render_nonfield_errors().classes('q-mt-sm')      # returns the ui.label
```
`render_field()` accepts optional `niceview.Field` kwargs to override field metadata for this render only:
```python
form.render_field('name', label='Short name')   # custom label
form.render_field('is_active', label='')        # suppress label
form.render_field('budget', suffix='k€')        # add suffix
```
`render_field()` returns the created widget (`ui.element` subclass) and raises `ValueError` for unknown or hidden fields.
`render_nonfield_errors()` returns the `ui.label`; omit the call to suppress model-level error display.
`render()` is equivalent to calling `render_field()` for all non-hidden fields followed by `render_nonfield_errors()`.

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

form.save()                 # persist to the adapter; shows a ui.notify popup
form.save(notify=False)     # same, but without any popup (programmatic saves)
form.refresh(notify=False)  # reload from the adapter, also without popup
```

**Accessing widgets after render():** every rendered field's widget is available via
`form.widgets[field_name]` (a plain dict) or `form.w(field_name)`. `w()` also offers typed
narrowing — pass the expected widget class and get it back correctly typed, with a
`TypeError` if the field rendered as something else. This is the canonical way to style
or tweak individual widgets after `render()`:
```python
form.w('name')                      # ui.element subclass (or CheckboxGroup/ModelGrid/... for composite fields)
form.w('name', ui.input).props('outlined')   # typed: IDE knows it's a ui.input
form.w('perms', CheckboxGroup).checkboxes['admin'].classes('text-negative')
form.widgets['age'].classes('w-32')          # dict access, untyped
```
`w()` raises `KeyError` for unrendered/excluded fields and `TypeError` on a widget-class mismatch.

**Change events** carry field name and old/new value:
```python
form.on_change(lambda e: print(e.field_name, e.previous_value, e.value))
```


ModelGrid / ModelGridInlineEdit
--------------------------------

`ModelGrid` renders a list as a read-only AgGrid table.
`ModelGridInlineEdit` adds per-cell editing with immediate validation and persistence.

```python
from niceview import ModelGrid, ModelGridInlineEdit

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

# Row selection (rowSelection='single'): e.row_key/e.item mirror ModelList.on_select;
# both are None when the selection is cleared
grid = ModelGrid.from_list(User, users, rowSelection='single')
grid.on_select(lambda e: print(e.row_key, e.item))

# Styling: the canonical way is the exposed .widget after render()
grid.render()
grid.widget.classes('w-full')
```


EditGridWrapper / EditFormWrapper
----------------------------------

Both wrappers add a title, optional description, and action buttons as chrome above their inner component.

```python
from niceview import EditGridWrapper, EditFormWrapper

# Grid with CRUD buttons
EditGridWrapper.from_list(User, user_list, title='Users').render()
EditGridWrapper.from_json(User, Path('users.json'), title='Users').render()
EditGridWrapper.from_adapter(User, adapter, title='Users').render()

# inline_edit=True uses ModelGridInlineEdit instead of ModelGrid
EditGridWrapper.from_list(User, user_list, title='Users', inline_edit=True).render()

# Form with chrome — factory methods mirror ModelForm's, accept all ModelForm options plus wrapper options
EditFormWrapper.from_item(user, title='Edit User').render()
EditFormWrapper.from_json(User, Path('user.json'), title='Config', autosave=True).render()
EditFormWrapper.from_adapter(User, adapter, key, title='Edit User').render()

# repositories= wires up modelselect fields (for FK relationships in EditFormWrapper)
EditFormWrapper.from_adapter(Book, books_adapter, book_id, title='Edit Book',
                             repositories={Author: authors_adapter}).render()
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
wrapper = EditGridWrapper.from_list(User, user_list, title='Users').render()
wrapper.title                              # ui.label | None
wrapper.description                        # ui.markdown | None
wrapper.title_row                          # ui.row | None
wrapper.add_button.props('color=primary')  # ui.button | None
wrapper.edit_button                        # ui.button | None
wrapper.delete_button                      # ui.button | None
wrapper.refresh_button                     # ui.button | None

# EditFormWrapper
wrapper = EditFormWrapper.from_adapter(User, adapter, key, title='Edit User').render()
wrapper.title.classes('text-primary')      # ui.label | None
wrapper.description                        # ui.markdown | None
wrapper.title_row                          # ui.row | None
wrapper.save_button.props('color=green')   # ui.button | None
wrapper.refresh_button                     # ui.button | None
```

**`EditGridWrapper` options:**
```python
wrapper = EditGridWrapper.from_list(User, users,
    title='Users',        # shown as text-h6; omitted or '' = auto title '{Type} List'; None = no title row
    description='...',    # markdown below the title row
    add_button='Add',     # label or '' for icon-only; None = hidden
    edit_button='',       # same
    delete_button='',     # same
    refresh_button=None,  # same
)
wrapper.with_repositories({Author: authors_adapter})  # type → adapter; for modelselect fields in dialogs
wrapper.render()
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
).render()
```


Card-Based List Editing
------------------------

`ModelGrid`/`EditGridWrapper` render a list as a table with Add/Edit/Delete dialogs. For a
mobile-friendly, inline-editable alternative — one card per item, each with its own layout and
autosaving fields — compose `ModelForm.from_adapter()` with a `CollectionAdapter` and
`ui.refreshable` yourself; there is no dedicated wrapper class for this because the layout is
inherently application-specific:

```python
from nicegui import ui
from niceview import JsonListAdapter, ModelForm

adapter = JsonListAdapter(Forwarding, Path('forwardings.json'))

@ui.refreshable
def render_cards() -> None:
    for key, item in adapter.items():
        form = ModelForm.from_adapter(Forwarding, adapter, key, autosave=True)
        with ui.card().classes('w-full'):
            with ui.row().classes('w-full items-center'):
                form.render_field('name').classes('grow')
                ui.button(icon='delete').on_click(lambda _, it=item: delete_row(it))
            with ui.row().classes('w-full'):
                form.render_field('method').classes('w-1/4')
                form.render_field('url').classes('grow')
            form.render_nonfield_errors()

def add_row() -> None:
    adapter.create(Forwarding())
    render_cards.refresh()

def delete_row(item: Forwarding) -> None:
    adapter.delete(adapter.key_from_item(item))
    render_cards.refresh()

render_cards()
ui.button('Add', icon='add', on_click=add_row)
```

Each card is its own `ModelForm` bound to one item via `from_adapter(Type, adapter, key)`, so
`autosave=True` persists every validated field change independently — no shared save button, no
row selection. `render_field()` (see [Custom field layout](#modelform)) places fields freely
within the card instead of the table-column layout `ModelGrid` would use. Add/Delete mutate the
adapter directly and call `render_cards.refresh()` (NiceGUI's `@ui.refreshable`) to re-render the
card list; use a `ReactiveAdapter`/`ObservableList`-backed adapter instead if you want the list to
update automatically on mutation (see "Reactive updates" in [Data Adapters](#data-adapters)).

See `examples/12_card_list.py` for a runnable version.


ModelList / DrillDownWrapper
----------------------------

`ModelList` renders a collection as a Quasar list — tappable rows with a title and subtitle,
suited for mobile-first single-column navigation. `DrillDownWrapper` is an embeddable list
<-> detail navigation widget built on top of it: a title row (Add in list view; Back + item
title + Delete in detail view) plus a body that swaps between the list and a per-item detail
view, with a slide animation on every swap. The title row is built once and only updated in
place on navigation (not the body — see "Styling after render()" below); it owns no NiceGUI
page/route of its own — `render()` draws into whatever context it's called in, same as any
other niceview widget, so it can sit inside a `ui.card()`, a tab panel, or a bigger page layout
without taking it over.

```python
from niceview import ModelList, DrillDownWrapper

# Standalone list — fire on_select callback when an item is tapped
list_view = ModelList.from_list(User, users,
    title_field='name',               # first visible field by default
    subtitle_fields=['email'],        # next two visible fields by default
)
list_view.on_select(lambda e: print(e.row_key, e.item))
list_view.render()

# Drill-down: embed inside your own page/card, then render()
with ui.card().classes('w-full'):
    DrillDownWrapper.from_list(User, users,
        list_title='Users',
        item_title_field='name',
        item_subtitle_fields=['email', 'active'],
    ).render()

# Works with any adapter
DrillDownWrapper.from_json(User, Path('users.json'), list_title='Users').render()
DrillDownWrapper.from_adapter(User, adapter, list_title='Users').render()
```

**`DrillDownWrapper` options:**
```python
DrillDownWrapper.from_list(User, users,
    list_title='Users',              # list view title
    item_title_field='name',         # field shown as detail title (auto-detected if omitted)
    item_subtitle_fields=['email'],  # fields shown as subtitle (next two visible fields if omitted)
    add_button='',                   # '' = icon only; None = hidden
    delete_button='',                # same
    on_add=None,                     # override the Add click handler entirely (see below)
    on_back=None,                    # if set, shows a Back button in the list view too (for nesting)
    render_list_item=None,           # override list row rendering (see below)
    render_list_container=None,      # wrap the rendered rows, e.g. for make_sortable (see below)
    render_detail=None,              # override detail rendering (see below)
    # ModelList options forwarded when render_list_item is not set:
    include=['name', 'email'],
    exclude=['secret'],
)
```
By default, Add creates `item_type()` and navigates straight to its detail view for editing —
no upfront dialog, matching the autosave-first pattern used throughout niceview. `wrapper.open(key)`
navigates to a detail view programmatically, e.g. from a custom `on_add`.

**Styling after render():** like `EditGridWrapper`/`EditFormWrapper`, `DrillDownWrapper` exposes
its title row elements — `wrapper.title_row`, `wrapper.title`, `wrapper.back_button`,
`wrapper.add_button`, `wrapper.delete_button` (all `| None`; the two buttons are `None` only if
disabled entirely via `add_button=None`/`delete_button=None`, never just because they're hidden
in the current view). Unlike a naive refreshable, the title row is built exactly once in
`render()` and only *updated* (text, visibility) on every list<->detail navigation, so styling
applied once (`wrapper.title.classes(...)`) survives navigation instead of being wiped on the
next swap. The body (list/detail content) is deliberately **not** exposed: it's genuinely torn
down and rebuilt on every navigation — that's also where the slide animation lives — so any
styling applied to it would be silently lost on the next swap; offering it would be misleading.
`ModelList` exposes only `.widget` (the `ui.list`) — it has no title row of its own, so there's
nothing else to expose.

**Custom list rows and detail layout.** Both are escape hatches for the two cases the generic
defaults can't handle: hand-placed field layout, and heterogeneous item types.
```python
def render_list_item(key: str, item: Widget, select: Callable[[], None]) -> None:
    with ui.row().classes('items-center gap-2').on('click', lambda: select()):
        ui.icon(WIDGET_ICONS[item.widget_type])
        ui.label(str(item))

def render_detail(adapter: CollectionAdapter, key: str, set_key: Callable[[str], None]) -> None:
    item = adapter.read(key)
    model_cls = WIDGET_MODELS[item.widget_type]           # resolve the concrete type per item
    form = ModelForm.from_adapter(model_cls, adapter, key, autosave=True)
    form.render_field('position_x').classes('w-1/2')
    form.render_field('position_y').classes('w-1/2')
    # ... hand-placed fields per widget type ...

DrillDownWrapper.from_adapter(WidgetModel, widgets_adapter,
    render_list_item=render_list_item, render_detail=render_detail, add_button=None,
).render()
```

**Wrapping the rows** (e.g. drag-to-reorder via `make_sortable`) needs the *container*, not each row, and needs to be re-applied every time the list re-renders — that's what `render_list_container` is for (only used together with `render_list_item`):
```python
def render_list_container(render_rows: Callable[[], None]) -> None:
    with ui.column().classes('w-full gap-1') as container:
        render_rows()
    container.make_sortable(handle='.drag-handle', on_end=handle_reorder)

DrillDownWrapper.from_adapter(WidgetModel, widgets_adapter,
    render_list_item=render_list_item, render_list_container=render_list_container,
    render_detail=render_detail, add_button=None,
).render()
```

`render_detail`'s `set_key` callback is for renaming: call it whenever the item's key changes
(e.g. a "Name" input's `blur` handler that calls `adapter.rename(...)`) to keep the wrapper's
navigation state in sync — it can be called any time, not just synchronously while
`render_detail` runs. There's no dedicated rename feature on the wrapper; a "Name" widget in
`render_detail` wired to `DirectoryAdapter.rename()` (see below) is all it takes.

**Two first-class backends**, both driven entirely through the hooks above:
- **A JSON list in one file** (`JsonListAdapter`, or `ListAdapter` over a nested list field) —
  homogeneous or heterogeneous items, no rename (items aren't named). See `examples/09_drilldown.py`.
- **One file per item in a directory** (`DirectoryAdapter`, below) — items are just filename
  metadata; rename is a "Name" field in `render_detail`, wired to `DirectoryAdapter.rename()`.
  See `examples/13_directory_drilldown.py`.


Data Adapters
-------------

Adapters decouple UI components from storage. Pass them explicitly for full control,
or let the `from_*` factory methods create them transparently.

| Adapter | Backs | Description |
|---|---|---|
| `ListAdapter(Type, list)` | Grid | In-memory list |
| `JsonAdapter(Type, path)` | Form | Single object in a JSON file; supports `lock_field=`, `created_field=`, `strict=` |
| `JsonListAdapter(Type, path)` | Grid | List of objects in a JSON file; supports `created_field=`, `strict=` |
| `SqlModelAdapter(Type, engine)` | Grid, Form | SQLModel / SQLAlchemy table *(requires the `sqlmodel` extra, see [Installation](#installation))* |
| `DirectoryAdapter(dir_path)` | `DrillDownWrapper` | One file per item in a directory; items are filename metadata (`FileEntry`), not parsed content — supports `rename()` |
| `FilteredAdapter(inner, predicate, defaults=)` | Grid, `DrillDownWrapper` | Filtered view of another `CollectionAdapter` (see below) |

All JSON adapters write atomically (`.tmp` → rename).
`JsonListAdapter` and `SqlModelAdapter` both implement `ReloadableAdapter`: `reload()` re-reads
from disk (JSON) or fires a grid-refresh notification (SQL, where every `read()` is already live).

**`DirectoryAdapter`** models "files in a directory" for `DrillDownWrapper`'s file-per-item use
case. `items()`/`read()` return `FileEntry(name, mtime, size)` — metadata only, never the parsed
file content; open the file's own `JsonAdapter`/`JsonListAdapter` for that (typically inside
`render_detail`). Keys never carry the file suffix — `name` is always the bare filename stem, so
a "Name" widget in `render_detail` never has to show or strip `.json` itself; if a user types the
suffix anyway, `create()`/`rename()` strip a trailing match rather than doubling it up
(`"note.json"` → `note`, file `note.json`). `create(item=None)` picks a free `'untitled-01'`,
`'untitled-02'`, ... name and writes `default_content`; `rename(key, new_key)` renames the file
on disk. Both are meant to be called directly by application code (an "Add" handler, a "Name"
widget's `blur` handler), not through `DrillDownWrapper`'s generic `item_type()`-based Add flow
— see `examples/13_directory_drilldown.py`.

**`FilteredAdapter`** wraps any `CollectionAdapter` and filters iteration by a predicate —
the standard way to show a parent-filtered view of a child collection (e.g. only the books of
one author) while mutations still go through the inner adapter for persistence. `defaults=`
injects field values on `create()`, so new items automatically belong to the current parent.
Change notifications and `reload()` are forwarded from/to the inner adapter. See
`examples/11_tree_navigation.py`.

```python
from niceview import FilteredAdapter

books_of_author = FilteredAdapter(books_adapter,
    predicate=lambda b: b.author_id == author.id,
    defaults={'author_id': author.id},   # applied to every create()
)
ModelGrid(Book, books_of_author).render()
```

**Lenient loading (default) vs strict loading:** `JsonAdapter` and `JsonListAdapter` default to
`strict=False`, which means a hand-edited or partially-migrated file does not crash the
application:

- **Malformed JSON** or a non-object/non-array root → `log.error`, return a default instance / empty list.
- **Unknown field** → `log.error`, field ignored.
- **Field with invalid value** → `log.error`, field dropped and replaced by its model default.
- **Required field absent (no default)** → `log.error`, item/load fails and raises (last resort).
- **`OSError` reading the file** (`JsonAdapter` only) → `log.error`, return `Type()` with all defaults.

Set `strict=True` to restore the original behaviour where any read error raises immediately.
The `StorageError` raised by `JsonAdapter.save()` during an optimistic-locking check is only
possible in strict mode (in lenient mode a corrupted file returns `None` lock values, so the
check is skipped).

The helper functions `lenient_model_load` and `lenient_list_load` are also importable from
`niceview` for use outside the built-in adapters.

> **Breaking change (since lenient default):** code that relied on `JsonAdapter.read()` or
> `JsonListAdapter` raising on a malformed file must pass `strict=True` explicitly.

```python
from niceview import lenient_model_load, lenient_list_load

# Load a single model from a JSON string, tolerating bad fields:
item = lenient_model_load(MyModel, json_text, context='myfile.json')

# Load a list, skipping unrecoverable items:
items = lenient_list_load(MyModel, json_text, context='myfile.json')
```

**Optimistic locking:** When `lock_field=` is set, `save()` compares the stored timestamp against
the one in memory before writing. The check only fires when *both* sides have a non-`None` value —
a `None` on either side is treated as "no lock data" and the save proceeds. Two exceptions can be
raised; both are caught by `ModelForm.save()` and `EditGridWrapper` with a user-facing `ui.notify`:

| Exception | When raised |
|---|---|
| `niceview.ConflictError` | Both timestamps are set but differ (concurrent modification) |
| `niceview.StorageError` | The stored file cannot be read during the lock check (corrupted, wrong schema, I/O error) |

Custom code calling `adapter.save()` directly should handle both:

```python
from niceview import ConflictError, StorageError

try:
    adapter.save(item)
except ConflictError:
    ui.notify('Someone else changed this item. Please reload.', color='warning')
except StorageError:
    ui.notify('The data file could not be read. Please contact your administrator.', color='negative')
```

**Adapter protocols** — implement these for custom backends:

| Protocol | Methods | Used by |
|---|---|---|
| `ItemAdapter[T]` | `read() -> T`, `save(item) -> T` | `ModelForm` |
| `CollectionAdapter[T]` | `__iter__`, `key_from_item(item) -> str`, `items() -> Iterator[(str, T)]`, `read(key) -> T`, `create(item) -> T`, `update(item) -> T`, `delete(key)` | `ModelGrid`, `EditGridWrapper` |
| `ReloadableAdapter` | `reload()` | `EditGridWrapper` (Refresh button), `FilteredAdapter` (forwarded) |
| `ReactiveAdapter` | `on_change(handler)` | `ModelGrid` (auto-update) |

`update()` returns the stored item, which may differ from the input (e.g. `SqlModelAdapter` refreshes `updated_at`). `key_from_item()` raises `KeyError` if the item is not in the adapter; `read()` raises `KeyError`/`ValueError` if the key is not found.

`items()` yields `(key, item)` pairs — like `dict.items()`, useful whenever key and item are needed together (e.g. building navigation URLs):
```python
for key, project in projects_adapter.items():
    with ui.card().on('click', lambda k=key: ui.navigate.to(f'/projects/{k}')):
        ui.label(project.name)
```

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
adapter = ListAdapter(User, items, created_field='created_at')   # set created_at on create()
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
from niceview import SqlModelAdapter

adapter = SqlModelAdapter(Book, engine)                                          # optimistic locking on updated_at
adapter = SqlModelAdapter(Book, engine, lock_field=None)                         # without locking
adapter = SqlModelAdapter(Book, engine, created_field='created_at')              # set created_at on create()
adapter = SqlModelAdapter(Book, engine, created_field='created_at', lock_field='updated_at')  # both

# Form for a specific record (fields only) — key must be str
form = ModelForm.from_adapter(Book, adapter, str(book_id))
form.render()

# Form with chrome (title + save/refresh buttons)
EditFormWrapper.from_adapter(Book, adapter, str(book_id), title='Edit Book').render()

# Grid over the full table
ModelGrid(Book, adapter).render()
EditGridWrapper.from_adapter(Book, adapter, title='Books').render()
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
| `list[Literal['a', 'b', ...]]` | `ui.select` (multi-select; options from the `Literal`) |
| `Enum` subclass | `ui.select` (keys = enum members, labels = member names) |
| `list[str]` | `ui.input_chips` |
| `list[Annotated[str, Field(...)]]` | `ui.input_chips` (same as `list[str]`) |
| `list[BaseModel]` | Inline `EditGridWrapper` |
| `Optional[T]` | Unwrapped to `T`, then same as above |
| SQLModel relationship (single) | `modelselect` (select backed by model repository) |
| SQLModel relationship (list) | Inline `EditGridWrapper` |

For `list[Literal[...]]` the widget is a multi-select (`multiple=True`) whose options are the
`Literal` values. With `Optional[list[Literal[...]]]`, a `None` model value shows as an empty
selection, and clearing the selection writes `None` back — so `None` and `[]` are interchangeable.

To show selected values as removable chips instead of comma-separated text, pass Quasar's
`use-chips` prop (same generic `props=` passthrough as `'ui.radio'`'s `inline`):
`niceview.Field(multiple=True, props='use-chips')`. No NiceView-specific support needed —
`ui.select` is a native widget, so `props` is applied directly to the underlying `QSelect`.

`list[Annotated[T, Field(...)]]` items are unwrapped to their base type (`str`, `int`, `float`,
`bool`, ...) for widget selection, so e.g. `list[Annotated[str, Field(pattern=r'^[a-z]+$',
min_length=2, max_length=10)]]` still renders as `ui.input_chips`. The `Field(...)` constraints
are not reinterpreted by NiceView — they stay part of the item's Pydantic annotation and are
enforced by the model's own validation, surfacing as a normal field-level error on the list field.

Additional widgets can be selected explicitly via `niceview.Field(widget_type='...')`:

| `widget_type` | Widget | Typical use |
|---|---|---|
| `'ui.textarea'` | `ui.textarea` | Long text / multi-line strings |
| `'ui.checkbox'` | `ui.checkbox` | Boolean (alternative to `ui.switch`) |
| `'ui.radio'` | `ui.radio` | `Literal` / enum with radio buttons |
| `'ui.toggle'` | `ui.toggle` | `Literal` / enum with toggle buttons |
| `'checkbox_group'` | Row/column of `ui.checkbox` | `list[Literal[...]]` / `Optional[list[Literal[...]]]` as checkboxes instead of a multi-select |
| `'ui.color_input'` | `ui.color_input` | Hex color picker |
| `'ui.slider'` | `ui.slider` | `int`/`float` with a visual range slider; `min`/`max` from `ge`/`le` constraints |
| `'ui.rating'` | `ui.rating` | `int` 1–N star rating; `max` from `le` constraint (default 5) |

`widget_type` values that map directly to a native NiceGUI element are prefixed `'ui.*'`
(`'ui.slider'` → `ui.slider`); niceview-specific widgets that aren't a single native element
(e.g. `'checkbox_group'`, a composite of several `ui.checkbox`) are unprefixed — same as the
type-based widgets `'datetime'`/`'date'`/`'time'`/`'timedelta'`/`'editgrid'`/`'modelselect'`.

`'ui.radio'` and `'checkbox_group'` render vertically by default; pass `props='inline'` for a
horizontal row (`niceview.Field(widget_type='ui.radio', props='inline')`).

**Widget options (choices):** all choice widgets (`ui.select`, `ui.radio`, `ui.toggle`,
`checkbox_group`) read their choices from the same resolution chain: `niceview.Field(options=...)`
first, then `literal_options`, which NiceView extracts automatically from `Literal[...]` —
including inside `list[Literal[...]]` and `Optional[list[Literal[...]]]`, even when
`widget_type` is overridden.
`options` accepts a list, a dict (`value -> label`), or a zero-argument callable returning
either — **sync or async**. An async callable renders the widget with empty choices first and
fills them in as soon as the awaitable resolves (the field's current value is preserved):

```python
async def load_countries() -> list[str]:
    return await fetch_from_api()

class User(pydantic.BaseModel):
    country: Annotated[str, niceview.Field(widget_type='ui.select', options=load_countries)] = ''
```

`None` and `[]` are interchangeable for `Optional[list[Literal[...]]]`, same as with the
multi-select `ui.select`.

`'checkbox_group'` fields render as `CheckboxGroup` — not a `ui.element` subclass
(there is no native NiceGUI/Quasar equivalent), but public and importable like `ModelGrid` /
`EditGridWrapper` for the same reason: `form.widgets[field_name]` and `form.w(field_name, ...)`
return it directly. Its `checkboxes` (`dict[option, ui.checkbox]`) and `widget`
(the `ui.row`/`ui.column`) attributes are public for styling:
```python
from niceview import CheckboxGroup

group = form.w('perms', CheckboxGroup)     # typed narrowing, raises TypeError if not a CheckboxGroup
group.checkboxes['admin'].classes('text-negative')
group.widget.classes('gap-x-8')
```


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

**Context-specific layouts (profiles):** Define named field sets in `Meta.profiles` and select them via `profile=` when creating a form or grid. This lets you render the same model differently in different contexts — e.g. a compact summary list vs a full detail form — without repeating `include=` at every call site:

```python
class User(pydantic.BaseModel):
    name: str = ''
    email: str = ''
    notes: str = ''
    secret: str = ''

    class Meta:
        profiles = {
            'summary': ['name', 'email'],     # compact: name + email only
            'detail': '__all__',              # full: all fields
        }
        field_infos = {
            'secret': niceview.Field(hidden=True),
        }

# Compact list: only name + email columns
ModelGrid.from_list(User, users, profile='summary').render()

# Full detail form: all non-hidden fields
ModelForm.from_item(user, profile='detail').render()

# Works the same on ModelList and DrillDownWrapper
ModelList.from_list(User, users, profile='summary').render()
```

Key `FieldInfo` options: `label`, `placeholder`, `tooltip`, `hidden`, `editable`, `widget_type`, `min`, `max`, `classes`, `options` (see "Widget options" above).


Validation
----------

Field-level and model-level (`@model_validator`) errors are displayed in the form. Field errors appear inline below the widget; model-level errors appear at the bottom of the form.


Dialogs
-------

`niceview.util` provides three async dialog helpers that can be awaited inside a NiceGUI event handler:

```python
from niceview.util import confirm_dialog, input_dialog, submit_dialog
```

**`confirm_dialog`** — ask for confirmation, returns `True` / `False`:

```python
async def on_delete():
    if not await confirm_dialog(
        'Delete Device',
        f'Delete **{name}**? This is irreversible.',
        ok_label='Delete',
        ok_color='negative',
    ):
        return
    device_adapter.delete(key)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `title` | `str` | — | Dialog title |
| `message` | `str` | — | Body text (Markdown) |
| `ok_label` | `str` | `'OK'` | Confirm button label |
| `cancel_label` | `str` | `'Cancel'` | Cancel button label |
| `ok_color` | `str` | `'primary'` | Quasar color for the confirm button |

**`input_dialog`** — ask for a string value, returns the entered string or `None` if cancelled:

```python
async def on_create():
    name = await input_dialog(
        'Create Project',
        label='Project Name',
        placeholder='my-project',
        validator=lambda v: v.isidentifier(),
        error_message='Letters, digits and _ only',
    )
    if name is None:
        return  # cancelled
    project_adapter.create(Project(name=name))
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `title` | `str` | — | Dialog title |
| `label` | `str` | — | Input field label (keyword-only) |
| `placeholder` | `str` | `''` | Input placeholder |
| `value` | `str` | `''` | Pre-filled value |
| `validator` | `Callable[[str], bool] \| None` | `None` | Validation function; `True` = valid |
| `error_message` | `str` | `'Invalid input'` | Error shown when validator fails |

**`submit_dialog`** — generic dialog with custom button list, returns the text of the
pressed button (without prefixes), or `None` if the dialog was dismissed:

```python
result = await submit_dialog('Confirm', 'Proceed?', ['Cancel', '|1OK'])  # 'Cancel' or 'OK'
```

Button labels can be prefixed for spacing (`|`) and color (`1`=primary, `2`=secondary, `a`=accent, `d`=dark, `+`=positive, `-`=negative, `i`=info, `w`=warning). Prefixes can be combined: `'|-OK'` = spacer + negative color.


Development
-----------

Install dependencies and run tests:
```bash
uv sync --dev
uv run pytest          # 657 tests
uv run mypy niceview/ --ignore-missing-imports   # 0 errors
```

Run examples:
```bash
uv run python examples/01_form_basic.py
```

| Example | Topic |
|---|---|
| `01_form_basic.py` | `ModelForm` — basic usage |
| `02_field_types.py` | `ModelForm` — all supported field types |
| `03_form_binding.py` | `ModelForm` — NiceGUI binding |
| `04_form_json.py` | `ModelForm` — JSON persistence |
| `05_grid.py` | `ModelGrid` |
| `06_edit_wrapper.py` | `EditGridWrapper` / `EditFormWrapper` |
| `07_sqlmodel.py` | `SqlModelAdapter` — SQL-backed grid/form, relationships, optimistic locking |
| `08_reactive_grid.py` | Reactive grid — auto-update via `ObservableList` |
| `09_drilldown.py` | `DrillDownWrapper` / `ModelList` — embeddable list <-> detail navigation |
| `10_complex_form_navigation.py` | `ModelForm` in a responsive split-panel: side panel on desktop, full page on mobile |
| `11_tree_navigation.py` | Multi-level tree navigation — URL factory, `FilteredAdapter`, `Meta.profiles` |
| `12_card_list.py` | Card-based list editing — autosaving `ModelForm` per item, `@model_validator`, `confirm_dialog` |
| `13_directory_drilldown.py` | `DrillDownWrapper` over `DirectoryAdapter` — one file per item, rename via a "Name" field |

Unit tests cover data adapters, field resolution, validation logic, and pure CRUD operations.
Acceptance tests (`tests/test_acceptance.py`) use the NiceGUI `User` fixture (headless, no browser)
to verify render output and widget↔model interaction. AgGrid cell content is JS-rendered and
not inspectable via the `User` fixture; row data is covered by unit tests instead.


Design Decisions / TODO
-----------------------

- [DESIGN.md](DESIGN.md) — design decisions and accepted technical debt
- [TODO.md](TODO.md) — open questions and planned work
- License: [MIT](LICENSE)
