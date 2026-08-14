Components
==========

Reference for the NiceView UI components. See also [Data Adapters](adapters.md), [Field Types & Customization](field-types.md), [Field Metadata Comparison](field-metadata-comparison.md) and [Dialogs](dialogs.md).

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
Events fire when a value is committed, not when it is typed — see Validation below. One
interaction can therefore emit several events (every field that changed), and an edit that was
blocked by a validation error is reported when the error clears.

### Layout

By default a form stacks its fields. A **layout** arranges them: a nested list of field names,
either in `Meta.profiles` (when the arrangement belongs to the model) or as `layout=` for a
single form.

```python
class Contact(pydantic.BaseModel):
    ...
    class Meta:
        profiles = {
            'card': [
                ['# Name', ['first_name', 'last_name']],
                ['# Address', 'street', ['zip_code:sm:w-1/3', 'city']],
            ],
        }

ModelForm.from_item(contact, profile='card').render()
ModelForm.from_item(contact, layout=['name', ['zip_code', 'city']]).render()
```

| Notation | Meaning |
|---|---|
| `'city'` | the field |
| `'zip_code:sm:w-1/3'` | the field, with CSS classes — only the **first** colon separates, so Tailwind prefixes (`sm:`, `hover:`) survive |
| `['zip_code', 'city']` | a nested list opens a container; rows and columns alternate with each level |
| `'# Address'` | as the **first** element of a group: it becomes a `ui.card` (flat, bordered) with that title, and always stacks |
| `'## Address'` | the same section heading, but no card around it — a plain `ui.column` that stacks just as well |
| `':gap-8 items-end'` | as the **first** element of a group: replaces the container's default classes |

A **section** is a group with a title. The number of `#` picks its shape, not its heading:
`'# Address'` draws the flat bordered card, `'## Address'` leaves the frame away and renders
only the heading above the fields. Both use `section_title_classes`, so the two look alike
wherever they sit; both always stack, and both take a `':classes'` of their own for their
container (`'w-full'` for the card, `'w-full gap-4'` for the plain column). Three or more `#`
raise `ValueError` — there is no third shape.

A layout is a profile with an arrangement: it defines **which** fields are rendered, in which
order — `Meta.field_order` does not apply on top of it. Grids and lists read the same entry and
ignore the nesting, so one profile can serve a form and a table. Unknown, duplicated or
excluded field names raise `ValueError` naming the position (`layout[1][0]`).

Two rules exist to avoid fighting Tailwind, and both are worth knowing:

- Fields in a row share the width evenly (`flex-1 min-w-0`). A field that brings classes of its
  own gets those **instead** — `flex-1` sets `flex-basis: 0` and would silently override any
  width that was asked for. (`min-w-0` is always added: it is layout mechanics, not styling.)
- Container classes **replace** the defaults (`w-full items-start gap-4` for a row) rather than
  adding to them: `gap-4 gap-8` is resolved by stylesheet order, not by the order in the class
  list.

Without a layout no container is created at all, so the fields become direct children of
whatever the caller opened — which is what makes the `ui.grid()` two-column trick work:

```python
with ui.grid().classes('w-full grid-cols-1 lg:grid-cols-2'):
    ModelForm.from_item(contact).render()
```

**Uniform styling** is a separate knob. `base_props` and `default_classes` apply to every widget
of the form, whatever its type — `ui.select`, `ui.input_chips` and `ui.color_input` included,
which `ui.input.default_props()` would miss (`ui.textarea` inherits from `ui.input`, the others
do not):

```python
ModelForm.from_item(contact, base_props='outlined dense', default_classes='w-full').render()
```

#### How props and classes travel down the cascade

Props and classes are **not** handled the same way, and the difference is not arbitrary: a
Quasar prop has a key, a CSS class does not.

| | `props` — additive | `classes` — replacing |
|---|---|---|
| How sources combine | merged **per key**, later source wins | the most specific source **replaces** the others |
| Why | `props('outlined dense')` is a dict; `dense=false` from a later source simply overwrites the earlier `dense` | `'w-full w-1/2'` is decided by stylesheet order, not by the order in the class list — merging cannot mean anything |
| Form-wide knob | `base_props` — a **base** every field builds on | `default_classes` — a **fallback** for fields that bring none |

The chain, lowest priority first:

| # | Source | `props` | `classes` |
|---|---|---|---|
| 1 | `ModelForm(base_props=…)` / `(default_classes=…)`, or the same names in `Meta` | base | used only if 2–5 set nothing |
| 2 | `Annotated[str, niceview.Field(props=…, classes=…)]` on the model field | merged over 1 | replaces 1 |
| 3 | `Meta.field_infos` | merged over 2 | replaces 2 |
| 4 | `ModelForm(field_infos=…)` | merged over 3 | replaces 3 |
| 5 | the layout's `'zip_code:sm:w-1/3'` | — | replaces 4 |
| 6 | `form.render_field('zip_code', classes=…)` | merged over 4 | replaces 4 |

Steps 2–4 are a `FieldInfo` merge, so a later source only overrides what it sets explicitly.
Steps 5 and 6 never meet: the layout applies to `render()`, the kwargs to `render_field()`.

```python
class Contact(pydantic.BaseModel):
    name: str
    zip_code: Annotated[str, niceview.Field(classes='text-right')]

ModelForm.from_item(contact, base_props='outlined dense', default_classes='w-full',
                    layout=['name', ['zip_code:sm:w-1/3', 'city']]).render()
# name      -> classes 'w-full'                  (the default; nothing more specific applies)
# zip_code  -> classes 'sm:w-1/3 min-w-0'        (layout wins — 'text-right' is gone)
# city      -> classes 'w-full flex-1 min-w-0'   (default + its even share of the row)
# all three -> props 'outlined dense'
```

One consequence is worth stating plainly: because classes replace, `'zip_code:sm:w-1/3'` drops
the field's own `text-right`. Put both in the layout (`'zip_code:sm:w-1/3 text-right'`) when you
want them together.

The other, from props being additive: a boolean prop from `base_props` cannot be taken back
declaratively for a single field — `props='dense=false'` parses to the *string* `'false'`, which
Quasar reads as truthy. Do it imperatively on the returned element instead:

```python
form.render_field('notes').props(remove='dense')
form.w('notes').classes(replace='w-1/3')      # the only way to remove, for classes too
```

What the layout notation cannot express, `render_field()` still can: it renders one field
wherever you call it, and honours the same form-level defaults.

### Validation

Three layers run in a fixed order. The first two are the widget's own and behave exactly the
same in `render_field()` without any model; the third is what `ModelForm` adds.

| | Layer | Runs on | Message shown |
|---|---|---|---|
| 1a | `required` — rejects an empty value (`None`, `''`, `[]`; never `False`/`0`) | the raw widget value | below the widget |
| 1b | `niceview.Field(validation=...)` — a callable or a `{message: predicate}` dict, NiceGUI's own contract | the raw widget value | below the widget |
| 2 | value conversion to the field's Python type | the raw widget value | `'Error interpreting widget value'` |
| 3 | **`ModelForm` only:** `model_validate()` over the whole item after every change | the converted draft | field errors below the widget, model-level errors in `render_nonfield_errors()` |

A value rejected by layer 1 is never converted and never reaches the model, so Pydantic never
sees a value the user was already told is wrong. A field's own message wins over the model's
message for the same field.

```python
class User(pydantic.BaseModel):
    # required (no default) + a widget-level rule + a model constraint, in that order
    name: Annotated[str, pydantic.Field(max_length=20),
                    niceview.Field(validation=lambda v: 'no digits' if any(c.isdigit() for c in v) else None)]

form = ModelForm.from_item(user, required_marker=' *', required_message='Required').render()
```

**The item is written only when it validates as a whole.** `form.item` is the last state that
passed every layer — the state `save()` would persist — and it is written *in place*, so
`bind_text_from(form.item, 'name')` keeps working across edits. The values currently in the
widgets, valid or not, are `form.draft` (a copy):

```python
form.item          # last fully valid state; identity stable; what save() writes
form.draft         # what the widgets currently hold, including invalid values
form.has_validation_errors, form.validation_errors, form.nonfield_validation_errors
```

Model-level (`@model_validator`) errors have no field to attach to. `render()` places the label
for them automatically; with a hand-built layout of `render_field()` calls, call
`form.render_nonfield_errors()` yourself — otherwise a cross-field error blocks every commit
without showing why (the form logs a warning when that happens).

Two limits worth knowing: an **async** validation function is displayed by the widget but
cannot block a commit (the commit path is synchronous), and `required` is skipped for disabled
fields so a non-editable empty field cannot block the form forever.


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

### Chrome styling

Styling elements one by one is the fine adjustment. The *shared* look of the chrome — the title
row of every wrapper, its buttons, the title of a section inside a form — is a `ChromeStyle`,
set once for the whole application:

```python
from niceview import ChromeStyle, get_chrome_style, set_chrome_style

set_chrome_style(button_props='dense outline', tooltips=False)   # change single attributes
set_chrome_style(ChromeStyle(title_classes='text-h5 grow'))      # or replace it wholesale
```

Call it at startup, before the first page is built: wrappers read the style when they render.
A single wrapper can opt out with `chrome_style=` — which *replaces* the default rather than
adding to it, so derive it from the current one:

```python
EditGridWrapper.from_list(User, users,
    chrome_style=get_chrome_style().replace(button_group=False),
).render()
```

| Attribute | Default | Applies to |
|---|---|---|
| `title_row_classes` | `'w-full items-center flex-nowrap'` | the title row of every wrapper |
| `title_classes` | `'text-h6 grow'` | the title label (`grow` pushes the buttons right) |
| `section_title_classes` | `'text-subtitle2'` | a layout section's title (`'# …'` and `'## …'` alike), an embedded grid's label |
| `button_props` | `''` | every chrome button |
| `icon_button_props` / `labelled_button_props` | `''` / `''` | a button without / with a label |
| `shape_in_group` | `False` | whether that shape also applies inside a button group |
| `add_button_props` … `back_button_props` | `''`, `delete`: `'color=negative'` | merged on top of the two above, per button kind |
| `button_group` | `True` | whether buttons that show together are joined in a `ui.button_group` |
| `button_group_style` | `'width: fit-content; flex: none'` | inline style of that group |
| `button_row_classes` | `'flex items-center gap-1 w-fit flex-none'` | the container used instead of the group |
| `tooltips` | `True` | whether the buttons carry their default tooltips |
| `list_props` | `'dense separator'` | a `ModelList`'s `ui.list` |
| `list_item_classes` | `'cursor-pointer'` | one row (`ui.item`) |
| `list_title_props` / `list_subtitle_props` | `''` / `'caption'` | the two `ui.item_label`s of a row |
| `list_chevron_icon` | `'chevron_right'` | drill-down hint at the right edge; `None` renders none |
| `list_chevron_classes` | `'text-grey'` | that icon |

A button's props are layered **base → shape → role**: `button_props` is what every chrome button
shares, the shape comes from whether the button carries a label, and the role
(`delete_button_props` …) has the last word. Shape follows the button, not the place it is used —
a lone Refresh looks the same in a form as in a grid.

The base and shape layers ship **empty**: the chrome decides where a button goes and what it
means, the application decides what it looks like. Only the role layer has an opinion of its
own, and only where it is meaning rather than taste (a delete button is `color=negative`). The
common setup is one line at startup:

```python
set_chrome_style(button_props='dense flat', icon_button_props='round')  # icon-only → circles
```

Rounding icon buttons has one limit, and it is Quasar's rather than ours: a button group joins
straight edges, and a circle has none. Inside a group the shape layer is therefore skipped, so
grouped icon buttons stay square. It is *joined or round, not both* — `button_group=False` gives
you round icon buttons everywhere, and `shape_in_group=True` lets a group-compatible shape
through (Quasar's `rounded` survives being joined, `round` does not).

A button group is only used when there is something to join: Quasar styles it as one control —
squared-off inner edges, a shared border — so a group of one would be a button wearing a group's
clothes. What counts is how many buttons are on screen *together*, not how many are configured:
an `EditFormWrapper` with `autosave=True` shows only Refresh, and a `DrillDownWrapper` shows Add
in the list view and Delete in the detail view, never both. Those go into `button_row_classes`
instead.

The `list_*` attributes are what a `ModelList` is made of — it has no title row, and styling
`.widget` afterwards would not reach the rows, which `update_rows()` rebuilds. A style set on a
`DrillDownWrapper` reaches the list it renders, so one `chrome_style=` covers both:

```python
ModelList.from_list(User, users, chrome_style=get_chrome_style().replace(list_chevron_icon=None))
DrillDownWrapper.from_list(User, users, chrome_style=get_chrome_style().replace(list_props='separator'))
```

Props are additive and classes replace, the same rule as the [field cascade](#how-props-and-classes-travel-down-the-cascade)
and for the same reason: a Quasar prop has a key, a CSS class does not. `ChromeStyle` is frozen —
`replace()` returns a copy, so a style handed to one wrapper cannot be mutated by another.

**`EditGridWrapper` options:**
```python
wrapper = EditGridWrapper.from_list(User, users,
    title='Users',        # shown as text-h6; omitted or '' = auto title '{Type} List'; None = no title row
    description='...',    # markdown below the title row
    add_button='Add',     # label or '' for icon-only; None = hidden
    edit_button='',       # same
    delete_button='',     # same
    refresh_button=None,  # same
    chrome_style=None,    # look of the title row (see Chrome styling)
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
    chrome_style=None,           # look of the title row (see Chrome styling)
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
    chrome_style=None,                # look of the list and its rows (see Chrome styling)
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
    list_title='Users',              # list view title; None or '' = none (the detail view shows the item title)
    description='...',               # markdown below the title row, in both views
    item_title_field='name',         # field shown as detail title (auto-detected if omitted)
    item_subtitle_fields=['email'],  # fields shown as subtitle (next two visible fields if omitted)
    add_button='',                   # '' = icon only; None = hidden
    delete_button='',                # same
    back_button='',                  # same — None leaves the detail view without a way back
    chrome_style=None,               # look of the title row (see Chrome styling)
    on_add=None,                     # override the Add click handler entirely, sync or async (see below)
    on_back=None,                    # if set, shows a Back button in the list view too (for nesting), sync or async
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

`on_add` and `on_back` may be written as `def` or as `async def`; an async handler is awaited
before the click is done. That's what you want when the item needs an answer before it can
exist — the dialogs in [Dialogs](dialogs.md) are all async:

```python
async def handle_add() -> None:
    name = await input_dialog('New project', label='Name')
    if name is None:
        return  # cancelled — nothing created
    item = adapter.create(Project(name=name))
    wrapper.open(adapter.key_from_item(item))

wrapper = DrillDownWrapper.from_adapter(Project, adapter, on_add=handle_add)
```

The same holds for the event callbacks elsewhere in niceview (`ModelForm.on_change`,
`ModelGrid.on_select`, `ModelList.on_select`, `EditGridWrapper.on_change`), for a field's
`options=` callable, and for a field's `validation=` function. The renderer callbacks
(`render_detail`, `render_list_item`, `render_list_container`) are the exception: they run
inside a refreshable body and must be synchronous. Load slow data before calling `render()`,
or render a placeholder and fill it from a task.

**Styling after render():** like `EditGridWrapper`/`EditFormWrapper`, `DrillDownWrapper` exposes
its title row elements — `wrapper.title_row`, `wrapper.title`, `wrapper.description`,
`wrapper.back_button`, `wrapper.add_button`, `wrapper.delete_button` (all `| None`; the buttons
are `None` only if disabled entirely via `add_button=None`/`delete_button=None`/`back_button=None`,
never just because they're hidden in the current view). Its title row is built by the same
[chrome style](#chrome-styling) as the other two wrappers. Unlike a naive refreshable, the title row is built exactly once in
`render()` and only *updated* (text, visibility) on every list<->detail navigation, so styling
applied once (`wrapper.title.classes(...)`) survives navigation instead of being wiped on the
next swap. The body (list/detail content) is deliberately **not** exposed: it's genuinely torn
down and rebuilt on every navigation — that's also where the slide animation lives — so any
styling applied to it would be silently lost on the next swap; offering it would be misleading.
`ModelList` exposes only `.widget` (the `ui.list`) — it has no title row of its own, so there's
nothing else to expose. Its rows are styled through the [chrome style](#chrome-styling), not
through `.widget`: `update_rows()` rebuilds them.

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


render_field — a single widget without a model
----------------------------------------------

`niceview.render_field()` renders one widget from one `FieldInfo`, with no Pydantic model
involved, and `niceview.field_value()` reads it back with the same value conversions
`ModelForm` applies. Use them when your code — not a model class — decides what a field is:
an interpreter for a schema you must not turn into a class, a hand-built form, a widget in a
dialog. `ModelForm` is built on the same functions, so both paths produce identical widgets.

```python
from niceview import Field, render_field, field_value

fi = Field(label='Name', widget_type='ui.input', props='outlined dense', classes='w-full')

widget = render_field(fi, 'Alice')      # renders in the current NiceGUI context
...
name = field_value(widget, fi)          # -> 'Alice'
```

A small form is a loop plus a dict:

```python
FIELDS = {
    'name':   Field(label='Name', widget_type='ui.input', props='outlined dense', classes='w-full'),
    'age':    Field(label='Age', widget_type='ui.number', field_type=int, min=0, max=120),
    'start':  Field(label='Start', widget_type='date'),
    'color':  Field(label='Color', widget_type='ui.select', options=['red', 'green']),
}

with ui.column().classes('w-full gap-3'):
    widgets = {key: render_field(fi, values.get(key)) for key, fi in FIELDS.items()}

def collect() -> dict:
    return {key: field_value(w, FIELDS[key]) for key, w in widgets.items()}
```

**What render_field() does** — everything `ModelForm` does to build a widget, and nothing that
needs a model: it creates the widget for `field_info.widget_type`, applies `label`,
`placeholder`, `hint`, `options` (list, dict, or a sync/async callable),
`min`/`max`/`step`/`multiple` and the other widget-specific attributes, then `props`, `classes`,
`style`, `tooltip` and `editable=False` (disabled). A `description` — help text that came from a
schema rather than from whoever laid out the form — is placed by `description_as`, exactly as in
a `ModelForm`: `render_field(fi, value, description_as='hint')`. Validation layer 1 is wired up as well:
`required` appends the marker to the label and rejects an empty value, then
`field_info.validation` runs. It sets the initial value — and stops there. There is no change
event, no autosave, no validation against a model, no `widgets` registry: the caller owns the
widget.

**Differences to a `ModelForm` field:**

| | `ModelForm` | `render_field()` |
|---|---|---|
| `widget_type` | inferred from the annotation | **required** — there is nothing to infer from |
| `field_type` | from the annotation | set it explicitly (default `str`), see below |
| `required` | from `is_required()` (no default) | set it explicitly |
| Value | read from / written to the item | passed in, read back via `field_value()` |
| Validation | layers 1–3 (model validation on top) | layers 1–2 (identical behaviour, no model) |
| `'editgrid'`, `'modelselect'` | supported | `ValueError` — both need a model type and a repository |

`field_type` drives the conversions in `field_value()` that depend on the target type:
`Field(widget_type='ui.number', field_type=int)` reads back `int` instead of `float`,
`field_type=list[str] | None` maps an empty multi-selection back to `None`, and
`field_type=list[int], item_type=int` splits a comma-separated `ui.input`. Everything else
works with the default.

For `'date'`, `'time'`, `'datetime'` and `'timedelta'` the value may be passed either as the
Python object or as the ISO string a JSON document already contains — both render; `field_value()`
always returns the Python object. `local_tz=` on both functions controls the display timezone
of `'datetime'`, exactly as `ModelForm`'s option of the same name.

`required` needs no model here: `niceview.Field(required=True)` appends `' *'` to the label
(`render_field(fi, value, required_marker=None)` switches that off) and rejects an empty value,
which is what makes a JSON Schema `required` list directly usable.

See `examples/14_render_field.py` for a runnable version that builds its fields from a
schema-like dict instead of a model.
