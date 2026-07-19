Field Types & Customization
===========================

How NiceView maps Python types to widgets, and how to customize fields.

[← Back to the README](../README.md)


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
