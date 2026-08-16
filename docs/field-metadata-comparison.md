Concepts — Field Metadata Across Four Vocabularies
==================================================

The same field is described in up to four places, each with its own vocabulary:

| Layer | What it describes | Who reads it |
|---|---|---|
| **`niceview.Field()`** (`FieldInfo`) | how the field looks and behaves in the UI | `ModelForm`, `ModelGrid`, `render_field()` |
| **NiceGUI widget options** | the concrete Quasar element | NiceGUI |
| **`pydantic.Field()`** + `annotated-types` constraints | the data: type, defaults, validity | Pydantic |
| **JSON Schema** | the same data contract, serialized | anything but niceview |

The tables below map them onto each other. **`-` means: no equivalent, or not supported.**

Three things to keep in mind while reading:

- **niceview never reads JSON Schema.** The JSON Schema column is a translation guide, not a
  feature: it is what you need when *your* code interprets a schema and builds `FieldInfo`s
  from it — see [`render_field()`](components.md#render_field--a-single-widget-without-a-model).
  There is no `from_json_schema()`, deliberately (a schema must never become a class).
- **The pydantic column is the automatic direction.** `Fields` resolves it when a `ModelForm` /
  `ModelGrid` is built; everything marked `-` there has to be set explicitly on
  `niceview.Field()`. Explicit values always win over resolved ones.
- **`niceview.Field()` is NiceGUI's vocabulary plus a named set of extensions.** Every
  constructor argument of every supported widget is either a `FieldInfo` attribute of the same
  name, set by niceview itself, or deliberately left to `props=` — declared in
  `WIDGET_OPTIONS` and checked by `tests/test_widget_option_coverage.py`, so a NiceGUI upgrade
  cannot widen the gap unnoticed.

[← Back to the overview](index.md) · See also [Field Types & Customization](field-types.md)


Identity and text
-----------------

| `niceview.Field()` | NiceGUI widget option | pydantic / annotated-types | JSON Schema | Notes |
|---|---|---|---|---|
| `label` | `label=` (`text=` on `ui.checkbox` / `ui.switch`) | `title` | `title` | Falls back to the capitalized field name, plus the required marker. Widgets without a label parameter get a caption above them → [D9](#deviations) |
| `hint` | Quasar `hint` prop | `description` | `description` | Help text below the widget. Widgets without a hint slot ignore it → [D3](#deviations) |
| `placeholder` | `placeholder=` | `examples[0]` | `examples` | An example of the expected input, not a description → [D2](#deviations) |
| `tooltip` | `.tooltip()` | `-` | `-` | Opt-in: it would only repeat the hint on hover → [D2](#deviations) |
| `-` | `value=` | `default` / `default_factory` | `default` | The value comes from the item (`ModelForm`) or the `value` argument (`render_field()`), never from the metadata |
| `-` | `-` | `examples` | `examples` | |
| `-` | `-` | `alias`, `validation_alias`, `serialization_alias` | property name | Naming/serialization only |


Requiredness, visibility, state
-------------------------------

| `niceview.Field()` | NiceGUI widget option | pydantic / annotated-types | JSON Schema | Notes |
|---|---|---|---|---|
| `required` | `validation=` (layer 1a) | `is_required()` (no default) | `required: [...]` | Appends `' *'` to the label and rejects an empty value, with or without a model → [D4](#deviations) |
| `editable=False` | `.disable()`, AgGrid `editable` | `frozen=True` | `readOnly` | Pydantic emits no `readOnly` for frozen → [D5](#deviations) |
| `hidden` | `-` | `-` | `-` | niceview-only: skipped by `render()` and by the grid |
| `validation` | `validation=` | field/model validators | `-` | Layer 1b, runs before the model → [D14](#deviations) |
| `-` | `-` | `deprecated`, `exclude` | `deprecated`, `writeOnly` | |


Numbers and ranges
------------------

| `niceview.Field()` | NiceGUI widget option | pydantic / annotated-types | JSON Schema | Notes |
|---|---|---|---|---|
| `min` | `ui.number(min=)`, `ui.slider(min=)` | `ge=`, `gt=` | `minimum`, `exclusiveMinimum` | Exclusive bounds are treated as inclusive → [D1](#deviations). Always stored as `float` → [D8](#deviations) |
| `max` | `ui.number(max=)`, `ui.slider(max=)`, `ui.rating(max=)` | `le=`, `lt=` | `maximum`, `exclusiveMaximum` | Same as `min`. For `ui.rating` it is the number of stars (default 5) |
| `step` | `ui.number(step=)`, `ui.slider(step=)` | `multiple_of=` | `multipleOf` | Different meanings → [D6](#deviations) |
| `precision` | `ui.number(precision=)` | `-` | `-` | Decimal places; JSON Schema has no equivalent |
| `prefix` / `suffix` | `ui.number(...)`, `ui.input(...)` | `-` | `-` | |
| `number_format` | `ui.number(format=)` | `-` | `-` | A printf format like `'%.2f'`. Named apart from JSON Schema's `format`, which maps to `widget_type` → [D7](#deviations) |


Choices
-------

| `niceview.Field()` | NiceGUI widget option | pydantic / annotated-types | JSON Schema | Notes |
|---|---|---|---|---|
| `options` | `ui.select/radio/toggle(options)` | `Literal[...]` args, `Enum` members | `enum` | List, dict (`value -> label`), or a sync/async callable. `Enum` keys are the members → [D13](#deviations) |
| `literal_options` | as above | `Literal[...]` args | `enum` | Resolved automatically, not user-settable; fallback when `options` is unset |
| `multiple` | `ui.select(multiple=)` | `list[Literal[...]]` | `type: array` + `items.enum` | `None` and `[]` are interchangeable |
| `with_input` | `ui.select(with_input=)` | `-` | `-` | Searchable select |
| `clearable` | `ui.select`, `ui.toggle`, `ui.input_chips` (argument); every text input incl. `ui.color_input` (prop) | `-` | `-` | Not derived from `Optional` → [D11](#deviations) |
| `new_value_mode` | `ui.input_chips`, `ui.select` | `-` | `uniqueItems` (loosely) | `'add-unique'` by default |
| `key_generator` | `ui.select(key_generator=)` | `-` | `-` | |
| `item_type` | `-` | `list[T]` argument, relationship target | `items`, `$ref` | Drives `editgrid` / `modelselect` and comma-separated `ui.input` lists |


Type → widget
-------------

`widget_type` is what `render_field()` needs explicitly; `ModelForm` infers it from the
annotation. In JSON Schema the same decision is a `type` + `format` pair.

| `widget_type` | Python type | JSON Schema | Notes |
|---|---|---|---|
| `'ui.input'` | `str`, unknown types | `type: string` | |
| `'ui.textarea'` | `-` (explicit) | `-` | No JSON Schema keyword — a UI decision |
| `'ui.number'` | `int`, `float` | `type: integer` / `number` | Set `field_type=int` in the model-free path |
| `'ui.switch'` | `bool` | `type: boolean` | `'ui.checkbox'` is the explicit alternative |
| `'ui.select'` | `Literal[...]`, `Enum`, `list[Literal[...]]` | `enum` (+ `type: array`) | `'ui.radio'` / `'ui.toggle'` / `'checkbox_group'` are explicit alternatives |
| `'date'` | `datetime.date` | `type: string, format: date` | Native HTML input |
| `'time'` | `datetime.time` | `type: string, format: time` | Native HTML input |
| `'datetime'` | `datetime.datetime` | `type: string, format: date-time` | Native HTML input; `local_tz` controls the displayed zone |
| `'timedelta'` | `datetime.timedelta` | `type: string, format: duration` | ISO 8601 duration in a `ui.input` |
| `'ui.input_chips'` | `list[str]` | `type: array, items: {type: string}` | |
| `'ui.input'` (comma-separated) | `list[int]`, `list[float]`, `list[bool]` | `type: array` | Needs `item_type` |
| `'ui.color_input'` | `-` (explicit) | `format: color` (non-standard) | |
| `'ui.slider'`, `'ui.rating'` | `-` (explicit) | `-` | Bounds from `min`/`max` |
| `'checkbox_group'` | `-` (explicit) | `type: array` + `items.enum` | Composite of `ui.checkbox`, see [Field Types](field-types.md) |
| `'editgrid'` | `list[BaseModel]` | `type: array, items: {$ref}` | `ModelForm` only — needs a model type |
| `'modelselect'` | SQLModel relationship | `$ref` | `ModelForm` only — needs a repository |
| `'ui.input'` (password) | `pydantic.SecretStr` | `format: password`, `writeOnly` | Set automatically → [D10](#deviations) |


Widget extras and presentation
------------------------------

Pure UI concerns: nothing in pydantic or JSON Schema corresponds to them.

| `niceview.Field()` | NiceGUI widget option | pydantic / annotated-types | JSON Schema |
|---|---|---|---|
| `password`, `password_toggle_button` | `ui.input(password=, password_toggle_button=)` | `-` | `-` |
| `autocomplete` | `ui.input(autocomplete=)` | `-` | `-` |
| `color_preview` | `ui.color_input(preview=)` | `-` | `-` |
| `props` | `.props()` | `-` | `-` |
| `classes` | `.classes()` | `-` | `-` |
| `style` | `.style()` | `-` | `-` |
| `-` | `on_change=` | `-` | `-` |
| `-` | `ui.rating(icon=, color=, size=)` — via `props=` → [D12](#deviations) | `-` | `-` |

`on_change` and the remaining NiceGUI constructor arguments are not exposed as field metadata:
`ModelForm` owns the change handling (`form.on_change(...)`), and everything else is reachable
on the rendered widget — `form.w('name')` or the return value of `render_field()`.


Table / grid columns
--------------------

Only relevant for `ModelGrid` / `ModelGridInlineEdit`; these map to AgGrid column definitions
rather than to a widget. (`ModelList` / `DrillDownWrapper` read only `hidden` and their own
`title_field` / `subtitle_fields` options.)

| `niceview.Field()` | AgGrid column property | pydantic / annotated-types | JSON Schema |
|---|---|---|---|
| `table_label` | `headerName` | `title` (via `label`) | `title` |
| `table_hidden` | column omitted | `-` | `-` |
| `table_align`, `table_cell_style` | `cellStyle` | `-` | `-` |
| `table_sortable` | `sortable` | `-` | `-` |
| `table_sort` | `sort` | `-` | `-` |
| `table_filterable` | `filter` (type inferred) | `-` | `-` |
| `table_floating_filter` | `floatingFilter` | `-` | `-` |
| `aggrid_type` | `type` | `-` | `-` |
| `aggrid` | any column property (verbatim) | `-` | `-` |


Constraints niceview does not render
------------------------------------

These are real constraints — Pydantic enforces them and the error message shows up in the form
as a normal field error — but no widget option is derived from them.

| Constraint | `niceview.Field()` | NiceGUI widget option | pydantic / annotated-types | JSON Schema |
|---|---|---|---|---|
| String length | `-` | `-` | `min_length=`, `max_length=` | `minLength`, `maxLength` |
| String pattern | `-` | `-` | `pattern=` | `pattern` |
| List length | `-` | `-` | `min_length=`, `max_length=` on a list | `minItems`, `maxItems` |
| Unique items | `-` | `-` | `-` | `uniqueItems` |
| Alternatives | `-` | `-` | `Union[...]` with >1 non-None type | `oneOf`, `anyOf` |
| Nested object | `-` | `-` | `BaseModel` field (not in a list) | `type: object`, `$ref` |
| Free-form mapping | `-` | `-` | `dict[...]` | `additionalProperties` |

The last three fall back to a plain `ui.input` showing the value's `str()` — a `Union` with more
than one non-`None` member additionally logs a warning. A single-member `Optional[T]` is unwrapped
and treated as `T`, and a single-value `Literal['x']` (JSON Schema `const`) renders as a
`ui.select` with exactly one option.


Deviations
----------

Where the four vocabularies do not line up, this is what niceview actually does.

**D1 — Exclusive bounds become inclusive.** `gt`/`lt` (JSON Schema `exclusiveMinimum` /
`exclusiveMaximum`) are copied into `min`/`max` unchanged, so `gt=0` renders a widget that
allows `0`. Pydantic still rejects it — the value is refused on validation, not in the widget.

**D2 — One text, one destination.** `title` becomes the `label`, `description` becomes the
`description`, `examples[0]` becomes the `placeholder` (an example of the expected input). Set
any of them explicitly to override the inference — an empty string counts as explicit, so
`niceview.Field(placeholder='')` renders no placeholder at all.

`hint` and `tooltip` are deliberately *not* in that list: nothing is inferred into them, they
are the form author's. Instead, `description_as` decides at render time where the description is
shown — `'tooltip'` (default), `'hint'`, or `None` for nowhere — per form
(`ModelForm(description_as=...)`, `Meta.description_as`) or per call
(`render_field(..., description_as=...)`). A field that sets `hint` or `tooltip` explicitly
always wins: the description then does not fill that slot, and never spills into the other one.

**D3 — Widgets without a hint slot ignore `hint`.** Checkbox, switch, radio, toggle, slider,
rating and `checkbox_group` have nowhere to put it. Use the `label` or a `tooltip` there —
which is also why `description_as` defaults to the tooltip, the one slot every widget has.

**D4 — `required` is display *and* a rule, but not enforcement.** It appends `' *'` to the
label (`required_marker=None` switches that off) and rejects an empty value — `None`, `''` or
an empty collection, never `False` and never `0`. That works without a model, so a JSON Schema
`required` means the same thing as a Pydantic field without a default. What it is not is
enforcement of the model's own constraints: those stay with Pydantic, and a disabled field is
skipped entirely so it cannot block a form forever.

**D5 — `frozen` disables the widget, `readOnly` is not what Pydantic emits.**
`niceview.Field(editable=False)` disables the widget and switches off inline editing in the
grid; `pydantic.Field(frozen=True)` and `model_config = ConfigDict(frozen=True)` resolve to it,
because Pydantic raises on every assignment to a frozen field, including on the working copy a
form edits. An explicit `editable=True` still wins and logs a warning. Note that Pydantic does
*not* emit `readOnly` in the generated schema for frozen fields (checked on 2.13), so the JSON
Schema column is a translation, not a round trip.

**D6 — `step` and `multipleOf` mean different things.** `multiple_of` is a divisibility
*constraint*; niceview reuses it as the widget's stepper increment. They agree for the common
case (`multiple_of=0.5`), but a `step` set by hand constrains nothing, and Pydantic enforces
`multiple_of` regardless of what the stepper offers.

**D7 — `format` is a name collision, so ours is called `number_format`.**
`FieldInfo.number_format` is NiceGUI's `ui.number` display format (`'%.2f'`). JSON Schema's
`format` (`date`, `date-time`, `duration`, `password`, ...) corresponds to `widget_type`
instead — see the type table above.

**D8 — `min`/`max` are floats.** `ge=0` on an `int` field yields `min=0.0`. Harmless for the
widget; notable when comparing values. Use `field_type=int` / `precision=0` to keep integers
integral on the way back.

**D9 — Widgets without a label parameter get a caption.** `ui.radio`, `ui.toggle`,
`checkbox_group`, `ui.slider` and `ui.rating` have no NiceGUI label argument, so niceview
renders a `text-caption` label above them — a form in which some fields have no label is not a
form. `label=''` opts out.

**D10 — `SecretStr` is inferred.** A `pydantic.SecretStr` field renders as a password input
with a reveal button, and `field_value()` wraps the text back into a `SecretStr`.

**D11 — `clearable` is not derived from `Optional`.** Whether a field may be cleared in the UI
is a UI decision; `Optional[T]` only says the model accepts `None`. Set `clearable=True`
explicitly — and make the field accept `None`, because that is what clearing writes.

**D12 — Not every NiceGUI option is a `FieldInfo` attribute.** `ui.rating`'s `icon`, `color` and
`size` are plain Quasar props and stay reachable through `props=`. Which option lives where is
declared in `WIDGET_OPTIONS` and enforced by `tests/test_widget_option_coverage.py`.

**D13 — `Enum` options are keyed by the member.** For an `Enum` field the options dict is
`{member: member.name}`, so the widget's value is the enum member itself, not its `.value` and
not its name — which is what a JSON Schema `enum` would list.

**D14 — Three validation layers, in this order.** Layer 1 is the widget's own: `required`
first, then `field_info.validation` (a callable or a `{message: predicate}` dict, exactly as in
NiceGUI). Layer 2 is the conversion of the widget value to the field's Python type. Layer 3 is
`ModelForm`'s addition: the whole item is validated against the model after every change, and
its message for the field is shown when layer 1 passed. A value rejected by layer 1 is never
converted and never reaches the model. Nothing is written to `form.item` while any layer
reports an error, including model-level (`@model_validator`) errors, which have no field to
attach to and are shown by `render_nonfield_errors()`. One exception: an **async** validation
function is displayed by the widget but cannot block a synchronous commit.
