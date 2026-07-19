Components
==========

Reference for the NiceView UI components. See also [Data Adapters](adapters.md), [Field Types & Customization](field-types.md) and [Dialogs](dialogs.md).

[← Back to the README](../README.md)


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
update automatically on mutation (see "Reactive updates" in [Data Adapters](adapters.md)).

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
`render_detail` wired to `DirectoryAdapter.rename()` (see [Data Adapters](adapters.md)) is all it takes.

**Two first-class backends**, both driven entirely through the hooks above:
- **A JSON list in one file** (`JsonListAdapter`, or `ListAdapter` over a nested list field) —
  homogeneous or heterogeneous items, no rename (items aren't named). See `examples/09_drilldown.py`.
- **One file per item in a directory** (`DirectoryAdapter`, see [Data Adapters](adapters.md)) — items are just filename
  metadata; rename is a "Name" field in `render_detail`, wired to `DirectoryAdapter.rename()`.
  See `examples/13_directory_drilldown.py`.
