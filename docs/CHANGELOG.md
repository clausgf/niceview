Changelog
=========

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

[Unreleased]
------------

(nothing yet)


[0.20.0] - 2026-08-16
---------------------

A form gets buttons that are not fields, and the documentation gets a home of its own at
[clausgf.github.io/niceview](https://clausgf.github.io/niceview/).

### Added

- **Actions in a form.** A button that is not a field — "Test connection" next to the host,
  "Generate" next to the password. It has no value, no validation and no place in the model, so
  it is a layout element rather than a pseudo-field: `Fields` stays a mapping of model fields and
  every path that walks it needs no exception. Two parts, because a callback cannot live in a
  layout string:

  ```python
  ModelForm.from_item(cfg,
      layout=[['# Server', ['host', 'port', '@test']]],
      actions={'test': FormAction('Test', icon='bolt', on_click=test_connection)},
  ).render()
  ```

  `'@name'` places the button, `actions` says what it does. `FormAction` carries `label`,
  `on_click`, `icon`, `tooltip`, `props`, `classes` and `requires_valid`; the handler receives a
  `FormActionEventArguments` with the form, whose `item` and `draft` are what an action almost
  always needs. `label` and `tooltip` also take a callable, like every `ChromeText` slot.

- **`requires_valid`** disables an action while the form has validation errors — the one bit of
  state worth taking over, since niceview knows `has_validation_errors` and the application would
  have to wire it up by hand.

- **`EditFormWrapper(chrome_actions=…)`** puts the same `FormAction` in the title row, left of
  Refresh and Save, exposed as `wrapper.action_buttons`. Otherwise the half between the fields
  would exist and the more obvious one — an own button next to Save — would still have no way in.

- **`widgets.reserves_bottom_space()`** answers whether a field is taller than its box — Quasar
  keeps 20px free below one that can show a message (a validation, a hint), so that the layout
  does not jump when one appears. An action in a row uses it to align itself with the box of its
  neighbours (`self-center mb-5`) rather than with the middle of their total height; next to a
  switch or a slider, which reserve nothing, the plain `self-center` is already right.

- **`ModelForm.render_action('test')`** places one action in a layout built by hand, as
  `render_field()` does for a field. Rendered actions are reachable as `form.w('@test')` (the
  layout's spelling) and in `form.action_buttons` — `widgets` stays keyed by field name.

- **A documentation site** at [clausgf.github.io/niceview](https://clausgf.github.io/niceview/):
  the pages under `docs/` as they are, plus an API reference generated from the docstrings
  (MkDocs Material + mkdocstrings, deployed by `.github/workflows/docs.yml`). The keyword options
  of every component are documented there too — they live in the `TypedDict`s the factories
  unpack, which is where their descriptions have always been.

### Changed

- `style.chrome_button()` accepts `kind=None` for a button without one of niceview's roles. The
  roles are a closed vocabulary of what niceview itself means by a button; an application's action
  skips that layer and styles itself, while place and shape still apply so it fits its neighbours.


[0.19.0] - 2026-08-16
---------------------

Chrome styling gets a second axis, field styling and texts get an application-wide default, and
everything niceview says out loud becomes replaceable. See [CONCEPT.md](CONCEPT.md) for how the
three cascades fit together.

### Added

- **The `place` axis.** Every chrome button now sits in one of three places — `'toolbar'` (a
  wrapper's own action row), `'form'` (the same row for a wrapper embedded in a form), `'dialog'`
  (a dialog footer) — styled with `toolbar_button_props`, `form_button_props`,
  `dialog_button_props`. Place and role are orthogonal (a Delete exists in both a toolbar and a
  dialog), so they are two layers rather than combined keys:

  ```
  {place}_button_props → shape → {role}_button_props
  ```

  Wrappers take `place=` and pass it on; `ModelForm` renders an embedded editgrid with
  `place='form'`.
- **Per-place icon shape**: `toolbar_icon_button_props`, `form_icon_button_props`,
  `dialog_icon_button_props`. `None` inherits `icon_button_props`, `''` suppresses the shape,
  a value replaces it — replacing rather than adding, because Quasar's shapes are separate
  boolean props and `round rounded` cancels nothing. "Round in a toolbar, square in a dialog"
  is now one line.
- **`ok` and `cancel` roles**, both without a default.
- **Dialog chrome**: `dialog_props`, `dialog_style`, `dialog_card_classes`,
  `dialog_title_classes`, `dialog_button_row_classes`, plus `chrome_style=` / `chrome_text=` on
  `confirm_dialog`, `input_dialog` and `submit_dialog`. The four hard-coded copies of
  `':maximized=… width: 400px'` are gone.
- **Notification chrome**: `notify_position`, `notify_timeout`, `notify_close_button`, and a
  `notify` hook `(message, kind) -> None` for an application with its own messaging.
- **`ChromeText`** (`niceview.text`) with `get_chrome_text()` / `set_chrome_text()` and a
  `chrome_text=` option on the widgets — every tooltip, dialog label, notification and field
  marker niceview shows, in one replaceable table. Placeholders are named (`{key}`, `{error}`)
  and every slot also accepts a callable, resolved at render time, so a multilingual application
  can resolve per client (a NiceGUI locale is per client, gettext's is per process).

  ```python
  set_chrome_text(add_tooltip='Neuen Eintrag anlegen', ok_label='Ok')
  ```
- **`FieldStyle`** with `get_field_style()` / `set_field_style()`: an application-wide default
  for form fields, by widget category — `input_props` for the QInput/QSelect based widgets,
  `control_props` for checkbox, switch, radio, toggle, checkbox_group, slider, rating, plus
  `default_classes`. The cascade below it is unchanged (`ModelForm(base_props=…)`, then the
  field's own props).
- **`widgets.INPUT_BASED_WIDGETS` / `widgets.CONTROL_WIDGETS`** name those two categories.
- **`ChromeStyle.derived()` / `FieldStyle.derived()` / `ChromeText.derived()`** — the
  application-wide value with single attributes changed, which is what a per-widget override
  almost always wants.
- **`card_title_classes`**: `'# Title'` (with card) and `'## Title'` (without) can now be styled
  apart. Both default to `'text-subtitle2'`, so nothing changes until it is set.
- **`chrome_style=` on `ModelForm`**, which styles its section titles and reaches the editgrid
  wrappers it embeds. `EditFormWrapper` passes its own style and texts down to its form.
- `examples/17_styling.py` — styling presets (Quasar / compact / touch) and a German text set,
  switchable at runtime. Presets are example code on purpose: the defaults stay empty.

### Changed

- **BREAKING: `ChromeStyle.button_props` is gone.** "Every button of this application is dense"
  is a statement about a type, and NiceGUI owns it. Use `ui.button.default_props('dense flat')`
  for all buttons, or `toolbar_button_props` (and its siblings) for niceview's chrome.
- **BREAKING: `confirm_dialog(ok_color=…)` → `ok_role=…`.** The confirm button is picked from the
  role layer instead of being handed a color, so `ok_role='delete'` follows whatever the
  application's delete buttons look like. `ok_label` / `cancel_label` now default to `None`,
  meaning "take it from `ChromeText`". The explicit `color=primary` on the confirm button is
  gone — a `ui.button` is primary anyway.
- **BREAKING: `widgets.REQUIRED_MARKER` / `widgets.REQUIRED_MESSAGE` are gone**, replaced by
  `ChromeText.required_marker` / `.required_message`. `render_field()` and `create_widget()`
  default to `FROM_CHROME_TEXT`, resolved at render time; passing an explicit string or `None`
  works as before.
- Notifications use Quasar's `type=` instead of `color=`, which brings the matching icon along.
  A `notify` hook or `notify_*` options change how they are delivered.
- Two texts that were duplicated in the code — the optimistic-lock message in `ModelGrid` and
  `EditGridWrapper`, `'Required'` in `widgets` and `ModelForm` — are now one slot each.
- The dialog confirm button reads `'OK'` where it used to read `'Ok'` for an edit.

### Notes

- `ModelGrid` takes no `chrome_style=`: it renders no chrome of its own, so its messages follow
  the application-wide style.
- A `list` place for buttons inside `ModelList` rows was considered and dropped — the row's job
  is to navigate, and the detail view already carries the item's actions. A `grid` place is not
  possible the same way at all: AG Grid cells live client-side, where Quasar props do not reach.
  Both are written up under "Possible extensions" in [CONCEPT.md](CONCEPT.md).


[0.18.1] - 2026-08-14
---------------------

### Fixed

- `clearable=True` had no effect on `ui.color_input`, `ui.input`, `ui.number`, `ui.textarea` and
  the `date`/`time`/`datetime`/`timedelta` widgets: NiceGUI has a `clearable` argument only on
  `ui.select`, `ui.toggle` and `ui.input_chips`, and the flag was silently dropped everywhere
  else. It is now set as a Quasar prop on the `q-input` those widgets are built from, so the
  clear button appears wherever a widget has somewhere to put it. Clearing writes `None`, so the
  field has to accept it (`str | None`) — as before, `clearable` is never inferred from
  `Optional`. Widgets without a clear affordance (checkbox, switch, radio, slider, rating,
  checkbox_group) still ignore the flag.


[0.18.0] - 2026-08-14
---------------------

### Added

- A form layout section without a card: `'## Title'` as the first element of a group renders the
  same heading as `'# Title'`, but stacks the fields in a plain `ui.column` instead of framing
  them in a `ui.card`. The number of `#` picks the shape, everything else is unchanged — the
  heading uses `ChromeStyle.section_title_classes` either way, the group still always stacks,
  and `':classes'` still replaces the container's defaults.

  ```python
  profiles = {'detail': [
      ['# Name', ['first_name', 'last_name']],    # card with a heading
      ['## Address', 'street', ['zip_code', 'city']],   # heading only
  ]}
  ```

### Changed

- Three or more `#` in a layout title now raise `ValueError` (`'###' is not a heading level`).
  They used to be stripped, so `'## Address'` and `'### Address'` were titled cards; `'##'` now
  means the section without the card, and there is no third shape to spell.


[0.17.0] - 2026-08-14
---------------------

### Changed

- `ChromeStyle.button_props` and `icon_button_props` ship **empty**. The chrome decides where a
  button goes and what it means; what it looks like is the application's call. Only the role
  layer keeps a default, and only where it carries meaning rather than taste
  (`delete_button_props='color=negative'`).

  This changes how every wrapper's buttons look: they are plain Quasar buttons now, where they
  used to be `dense flat` — a look that predates `ChromeStyle` and was never a decision anyone
  made. One line at startup brings it back, `round` included:

  ```python
  set_chrome_style(button_props='dense flat', icon_button_props='round')
  ```


[0.16.2] - 2026-08-14
---------------------

### Added

- A chrome button's shape now follows the button itself: without a label it is round, with one
  it stays square. The props of a chrome button are layered base → shape → role, with the two
  new `ChromeStyle` attributes `icon_button_props` (default `'round'`) and
  `labelled_button_props` (default `''`) in the middle; a role such as `delete_button_props`
  still wins. Icon-only buttons outside a button group therefore look different than before —
  `DrillDownWrapper`'s Back/Add/Delete, the lone Refresh of an autosaving `EditFormWrapper`,
  and any toolbar with `button_group=False`. Set `icon_button_props=''` for the old look.
- `ChromeStyle.shape_in_group` (default `False`): inside a `ui.button_group` the shape layer is
  skipped, because a group joins straight edges and a circle has none — joined or round, not
  both. `button_group=False` gives round icon buttons everywhere; `shape_in_group=True` lets a
  group-compatible shape through (Quasar's `rounded` survives being joined, `round` does not).


[0.16.1] - 2026-08-14
---------------------

### Changed

- Chrome buttons are only joined in a `ui.button_group` when more than one of them is on
  screen at the same time. Quasar styles a group as one joined control — squared-off inner
  edges, a shared border — so a group of one made a lone button look like part of something
  that was not there. Affected, all with a single visible button: `EditFormWrapper` with
  `autosave=True` (Save is suppressed, Refresh remains), an `EditGridWrapper` with all but one
  button hidden, and `DrillDownWrapper`, whose Add belongs to the list view and Delete to the
  detail view — configured together, never shown together. The new `ChromeStyle` attribute
  `button_row_classes` (default `'flex items-center gap-1 w-fit flex-none'`) styles the
  container used instead of the group; `button_group=False` now goes through it as well,
  rather than dropping the buttons loose into the title row without a gap.


[0.16.0] - 2026-08-13
---------------------

### Added

- `niceview.ChromeStyle` plus `set_chrome_style()` / `get_chrome_style()`: the shared look of
  everything the wrappers draw *around* a form, grid or list — title row classes, button props
  per button kind, the button group, tooltips, the size of a section title inside a form, and
  the props and classes of a `ModelList`'s list, rows, labels and chevron.
  Set once for the application, or per widget with the new `chrome_style=` option on
  `EditGridWrapper`, `EditFormWrapper`, `DrillDownWrapper` and `ModelList`:

  ```python
  set_chrome_style(button_props='dense outline', tooltips=False)
  EditGridWrapper.from_list(User, users, chrome_style=get_chrome_style().replace(button_group=False))
  ```

  Props are additive and classes replace, the same rule as the field cascade. Until now the
  three title rows were built from literals copied between the wrappers, and the only way to
  change their look was styling each exposed element in every application. A `ModelList` had
  no such way at all: its rows are rebuilt by `update_rows()`, so styling `.widget` after
  `render()` never reached them. `list_chevron_icon=None` renders rows without the drill-down
  chevron, for a list that is not one. A style set on a `DrillDownWrapper` also styles the
  `ModelList` it renders.
- `DrillDownWrapper(description=...)`, exposed as `wrapper.description` after `render()` —
  markdown below the title row, as `EditGridWrapper`/`EditFormWrapper` already had.
- `DrillDownWrapper(back_button=...)`: label the Back button, `''` for icon-only (the default),
  `None` to hide it — the same `''`/label/`None` semantics as the other buttons.

### Changed

- `DrillDownWrapper`'s title row now looks like the other two wrappers: its buttons are joined
  in a `ui.button_group` at the right edge, the row no longer wraps (`flex-nowrap` instead of
  `gap-2`), and the buttons carry tooltips. The redundant `round` and `color=primary` props are
  gone — `color=primary` was NiceGUI's own default for `ui.button`, and neither is set on the
  equivalent buttons of `EditGridWrapper`.
- `DrillDownWrapper(list_title=None)` shows no title in the list view (the detail view keeps
  showing the current item's title). It previously rendered the string `'None'`.
- Deleting a row in `EditGridWrapper` now asks through `util.confirm_dialog` with a red
  **Delete** button, the same confirmation `DrillDownWrapper` already used, instead of a
  neutral Cancel/OK `submit_dialog`.
- The create/edit dialog of `EditGridWrapper` uses the same button row as `niceview.util`'s
  dialogs: right-aligned, with the confirming button in the primary color.
- The label of a read-only embedded grid (`editgrid` field) renders as `text-subtitle2`, like
  every other section title inside a form — it was `text-h6`, the size of the page title.
- `util.submit_dialog`'s title no longer carries the class `center`, which is neither a Quasar
  nor a Tailwind class and never had an effect.


[0.15.0] - 2026-08-13
---------------------

### Added

- `DrillDownWrapper(on_add=..., on_back=...)` accept `async def` handlers. An async handler is
  awaited inside the click, in the click's own slot context, so it can open a dialog and act on
  the answer before returning — the reason `on_add` exists in the first place:

  ```python
  async def handle_add() -> None:
      name = await input_dialog('New project', label='Name')
      if name is None:
          return  # cancelled — nothing created
      item = adapter.create(Project(name=name))
      wrapper.open(adapter.key_from_item(item))
  ```

  Previously the coroutine was dropped without being awaited: the button did nothing at all,
  with a `RuntimeWarning` as the only trace. Sync handlers are unaffected.
- `util.input_dialog(validator=...)` accepts an async validator, for checks whose answer is not
  local ("is this name still free?"). It gates the OK button exactly as a sync one does. Async
  validators cannot go into Quasar's sync-only validation dict, so they are wrapped in a
  NiceGUI `ValidationFunction`; previously the coroutine object was truthy and every value
  passed.
- `util.maybe_await(result)`: awaits a value if it is awaitable, passes it through otherwise.
  Used internally wherever niceview invokes a caller-supplied callback directly.

### Changed

- `DrillDownWrapper` now raises `TypeError` at construction when `render_detail`,
  `render_list_item` or `render_list_container` is an `async def`. These run inside the
  refreshable body and cannot be awaited; they used to fail silently with an empty body.
- Internal: `DrillDownWrapper._handle_add()` and `_handle_back_click()` are coroutines. A
  synchronous `on_add`/`on_back` therefore runs one event-loop tick after the click instead of
  during it — invisible in a browser, but a `nicegui.testing.User` test that clicks Add and
  asserts without an intervening `await` needs one now.

Callbacks that already accepted async handlers and are unchanged: `ModelForm.on_change`,
`ModelGrid.on_select` / `on_change`, `ModelList.on_select`, `EditGridWrapper.on_change` (all
dispatched through NiceGUI's `handle_event`), a field's `options=` callable, and a field's
`validation=` function. Deliberately left synchronous: the adapter protocol
(`ReactiveAdapter.on_change`, `FilteredAdapter`'s predicate, `DirectoryAdapter`'s `name_filter`
and `default_content`), which has no NiceGUI dependency at all, and the per-value mappers
`cell_renderers` / `cell_readers` / `key_generator`, which run while building rows.


[0.14.1] - 2026-08-07
---------------------

### Security

- `aiohttp` 3.14.1 -> 3.14.3 in `uv.lock`, closing three advisories reported against the
  locked version: an out-of-bounds heap read in the C HTTP response parser (high), HTTP
  request smuggling via a WebSocket upgrade, and a WebSocket client accepting compressed
  frames without a negotiated `permessage-deflate`. A transitive dependency through NiceGUI;
  no declared requirement changed.

### Changed

- Internal: `_create_checkbox_group_widget()` no longer disables the group itself — since
  0.14.0 `apply_field_info()` reaches composite widgets, so a non-editable checkbox group was
  being disabled twice. No behaviour change.


[0.14.0] - 2026-08-07
---------------------

### Added

- `ModelForm(description_as=...)` / `Meta.description_as` / `render_field(..., description_as=...)`:
  where a field's `description` is rendered — `'tooltip'` (the new default), `'hint'` below the
  widget, or `None` for nowhere.

### Changed

- **Breaking:** a model's `description` no longer becomes the field's `hint`. It is resolved
  into the new `FieldInfo.description` and rendered wherever `description_as` says — as a
  **tooltip** by default. `hint` and `tooltip` are now purely the form author's: nothing is
  inferred into them, and whatever a field sets explicitly always wins over the description,
  which then neither fills that slot nor spills into the other one. The old behaviour is
  `description_as='hint'`. Rationale: a hint costs vertical space in every row and only exists
  on the hint-capable widget types, so a description silently vanished on radio, toggle,
  slider, rating and checkbox_group — a tooltip works everywhere.
- **Breaking:** `ModelForm(field_props=...)` is now `base_props`, `field_classes` is now
  `default_classes` — in kwargs and in `Meta`. No alias: the semantics of the classes knob
  changed with the name (see below), so an alias would keep the call working and quietly
  change what it does.
- **Breaking:** form-wide and per-field CSS classes no longer accumulate. `props` still merge
  per key (a Quasar prop has a key, so a later source overrides that one prop and nothing else);
  `classes` are now **replaced** wholesale by the most specific source, because `'w-full w-1/2'`
  is resolved by stylesheet order rather than by the order in the class list — accumulating them
  only looked like it worked. `default_classes` is therefore a fallback for fields that bring no
  classes of their own, and a field's classes in the layout (`'zip_code:sm:w-1/3'`) replace the
  ones on the model field instead of adding to them. To combine, write both in the winning
  source; to remove, use the element API (`form.render_field('x').classes(replace='w-1/3')`).
  See [Components](components.md#how-props-and-classes-travel-down-the-cascade).

### Fixed

- `checkbox_group` fields ignored `classes`, `style`, `props` and `tooltip` from their
  `FieldInfo`, and with them the form-wide styling — the composite widget was skipped when the
  field's styling was applied. `CheckboxGroup` now forwards those four to its container, so a
  checkbox group is styled like every other field. `hint` remains unsupported there (no hint
  slot, same as radio/toggle/slider/rating), and `props='inline'` is still consumed as a layout
  directive rather than passed on.


[0.13.0] - 2026-08-06
---------------------

### Added

- **Form layouts**: a nested list of field names arranges a form instead of stacking it —
  `['# Address', 'street', ['zip_code:sm:w-1/3', 'city']]`. A nested list opens a container
  (rows and columns alternate), a leading `'# Title'` makes the group a card, a leading
  `':classes'` replaces the container's classes, and a field may carry classes after the first
  colon (Tailwind prefixes such as `sm:` stay intact). Written in `Meta.profiles` — a profile
  entry may now be nested, and is still a plain field list for grids and lists — or as the new
  `layout=` option for a single form. Unknown, duplicated or excluded names raise `ValueError`
  naming the position (`layout[1][0]`). See [Components](components.md#layout) and
  `examples/16_form_layout.py`.
- `ModelForm(field_props=..., field_classes=...)`: Quasar props and CSS classes for **every**
  widget of a form, whatever its type. `ui.input.default_props()` reaches `ui.textarea` (a
  subclass) but not `ui.select`, `ui.number`, `ui.input_chips` or `ui.color_input`. The cascade
  is form defaults → the field's own `props`/`classes` → the layout's classes.
- `Fields.layout` exposes the parsed tree; `field_names` stays flat, so grids and lists are
  unaffected by an arrangement.

### Changed

- An explicit field list now defines the **order**, whether written as a list or as a
  comma-separated string: `include=['c', 'a']` and `include='c, a'` both render c before a.
  Previously the order came from the model annotations and the list was only a selection.
  `include='__all__'` and `Meta.field_order` are unchanged; a layout defines the order itself,
  so `field_order` does not apply on top of it.
- Naming the same field twice in `include`, a profile or a layout raises `ValueError` instead
  of rendering it twice.


[0.12.0] - 2026-08-06
---------------------

Field metadata now mirrors NiceGUI's widget options, validation runs in documented layers, and
the edited item is written only when it validates as a whole. See
[Field Metadata Comparison](field-metadata-comparison.md) for the full mapping and
[Validation](components.md#validation) for the layers.

### Breaking changes

- **`form.item` no longer updates while any validation error is present.** It is now, by
  definition, the last state that validated as a whole — the state `save()` would persist.
  What the widgets currently hold is `form.draft`. Previously a field was committed as soon as
  that field alone was valid, which left `form.item` in states `save()` refused (a cross-field
  `@model_validator` error did not block the write-back at all).
- **`on_change` fires on commit, per changed field.** One interaction can emit several events,
  and an edit blocked by a validation error is reported when the error clears. Only fields
  whose value actually changed emit an event.
- **`FieldInfo.validation` now runs inside a `ModelForm`**, before the model's message. It used
  to be overwritten by the model-error lookup on every widget that could display a message,
  i.e. it never ran.
- **`FieldInfo.format` is now `number_format`** — JSON Schema's `format` corresponds to
  `widget_type`, and the collision would have hit the planned schema-driven form first.
  No alias; the old name raises `TypeError`.
- **`FieldInfo.help_text` is replaced by `hint`**, which is actually rendered (Quasar's `hint`
  prop, below the widget). `help_text` never rendered anything. No alias.
- **`description` no longer fills `placeholder` and `tooltip`.** One source, one destination:
  `title` -> `label`, `description` -> `hint`, `examples[0]` -> `placeholder`. `tooltip` is
  opt-in. This changes the look of every form whose model uses `description`.
- **`required` is rendered and enforced at the widget level**: the label gets a `' *'` marker
  (`required_marker=None` to switch off) and an empty value (`None`, `''`, `[]` — never `False`
  or `0`) is rejected with `'Required'` (`required_message=` to change). A field without a
  default that legitimately held an empty string is now blocked.
- **`pydantic.Field(frozen=True)` (and `model_config = ConfigDict(frozen=True)`) implies
  `editable=False`.** Pydantic raises on every assignment to a frozen field, so such a field
  used to render enabled and answer the first keystroke with "Error interpreting widget value".
  An explicit `niceview.Field(editable=True)` still wins and logs a warning.
- **`pydantic.SecretStr` renders as a password input** with a reveal button instead of plain
  text, and `field_value()` returns a `SecretStr`.
- **`ModelGridInlineEdit` honours `editable=False`**; it used to make every column editable.
- **`save()` and `refresh()` write into the existing item** instead of replacing it, so
  bindings on `form.item` survive them. `load(key)` still rebinds — it navigates to a
  different item.

### Added

- **Model-free field rendering**: `niceview.render_field(field_info, value)` renders a single
  widget from a `niceview.Field()` in the current NiceGUI context, and
  `niceview.field_value(widget, field_info)` reads it back with the same value conversions
  `ModelForm` applies (`niceview.to_widget_value()` is the other direction). No Pydantic model,
  no `create_model()` — for callers that decide themselves what a field is, e.g. an interpreter
  for an untrusted schema. `widget_type` is required; `'editgrid'` and `'modelselect'` raise
  `ValueError` because both need a model type and a repository. Validation layers 1 and 2 work
  there exactly as they do in a form. See
  [Components](components.md#render_field--a-single-widget-without-a-model).
- `field_type` is now a documented `niceview.Field()` argument. `ModelForm` still takes it from
  the model annotation; setting it by hand drives `field_value()`'s type-dependent conversions
  (e.g. `field_type=int` to read a `'ui.number'` back as `int` instead of `float`).
- `ModelForm.draft`: the current widget values as a model instance, including values that fail
  validation and are therefore not in `item` yet.
- `ModelForm(required_marker=..., required_message=...)`, also available on
  `render_field(..., required_marker=...)`.
- `niceview.widgets.run_validation()`, `required_error()` and `is_empty()` — the widget-level
  validation layer, shared by `ModelForm` and `render_field()`. Async validation functions are
  supported for display (they cannot block the synchronous commit).
- `FieldInfo.key_generator` (`ui.select`), plus the previously dropped forwards: `prefix`/
  `suffix` on `ui.input`, `clearable` on `ui.toggle` and `ui.input_chips`, `new_value_mode` on
  `ui.select`.
- `FieldInfo.hint` renders on all QInput/QSelect based widgets; `label` renders as a caption
  above the widgets that have no label parameter (`ui.radio`, `ui.toggle`, `checkbox_group` —
  joining `ui.slider` and `ui.rating`, which already did).
- `niceview.widgets.WIDGET_OPTIONS` declares, per widget, which NiceGUI constructor argument is
  a `FieldInfo` attribute, owned by niceview, or left to `props=`.
  `tests/test_widget_option_coverage.py` checks it against the installed NiceGUI, so an
  upgrade that adds an argument fails the suite instead of drifting silently.
- `ModelForm` logs a warning when model-level validation errors are blocking commits but no
  `render_nonfield_errors()` label is on screen to show them.
- `examples/14_render_field.py` covers the model-free path; `examples/02_field_types.py` now
  shows hint, required, frozen and `SecretStr`.

### Changed

- `ModelForm` builds its widgets through the new `niceview/widgets.py` — the same code path as
  `render_field()`, so both render identical widgets. `CheckboxGroup` moved there too and is
  still importable from `niceview` and `niceview.modelform`.

### Documentation

- New [Field Metadata Comparison](field-metadata-comparison.md) page: a side-by-side table of
  `niceview.Field()`, the NiceGUI widget options, `pydantic.Field()` / `annotated-types`
  constraints and their JSON Schema equivalents, with `-` for everything unsupported and the
  deviations between them spelled out.
- [Components](components.md#validation) documents the validation layers, the commit policy and
  the `item` / `draft` contract. The three principles behind this release are recorded in
  [DESIGN.md](DESIGN.md).


[0.11.0] - 2026-08-05
---------------------

### Changed

- `DirectoryAdapter`: hidden dotfiles and `name_filter` now apply in **both** modes, not just
  all-files mode. Previously a `name_filter` passed together with a `suffix` was silently
  ignored. Dotfile exclusion is a real change for suffix mode — `pathlib`'s `glob('*.json')`
  matches `.hidden.json`, so such files were listed before and are not any more.
- `DirectoryAdapter`: `name_filter` receives the full filename (extension included) in both
  modes, never the stripped key.

### Fixed

- `DirectoryAdapter`: a single file whose key cannot round-trip no longer breaks the entire
  listing. A bare `.json` (empty key) or a name containing a path separator raised
  `ValueError` for the whole iteration; such files are now skipped. Addressing one explicitly
  by key still raises.

### Performance

- `DirectoryAdapter` iteration uses `os.scandir` and its cached `DirEntry` stat, halving the
  syscalls per file (`is_file()` + `Path.stat()` previously stat'd every entry twice).
  Measured 3.6x faster at 1000 files and 4.1x at 5000, with identical results. This matters
  because `DrillDownWrapper` iterates synchronously on the NiceGUI event loop, where a slow
  scan stalls every connected client.


[0.10.0] - 2026-08-01
---------------------

### Added

- `DirectoryAdapter`: all-files mode via `suffix=None` (or `''`) — a general, mixed-extension
  file browser. Keys are full filenames (no suffix stripping), every regular file is listed
  (hidden dotfiles excluded, plus an optional `name_filter=Callable[[str], bool]`), and
  `create()` takes a full name. The default `suffix='.json'` document-collection mode and all
  existing calls are unchanged (opt-in, backward-compatible).


[0.9.1] - 2026-07-24
--------------------

### Changed

- Pinned dev/test environment updated to NiceGUI 3.15.0 (declared floor stays `>=3.0`).

### Fixed

- `ModelForm`: clearing a `ui.number` field no longer raises `TypeError` and leaves a stale
  value. A cleared field now maps to `None`, so `Optional` number fields round-trip and required
  number fields fail validation cleanly.
- `ModelForm`: `Optional[int]` number fields are no longer coerced to `float` (e.g. `50` stayed
  `50.0`); the field type is unwrapped so integers stay integers.


[0.9.0] - 2026-07-19
--------------------

### Added

- README screenshots (hero `ModelForm`, `EditGridWrapper` table, `DrillDownWrapper` GIF),
  generated reproducibly by `docs/screenshots/capture.py` (optional `screenshots` dependency group).

### Changed

- Example scripts no longer manipulate `sys.path`; they rely on the editable install created by
  `uv sync`. A `.vscode/` config is included so examples run directly via the Run button / F5.


[0.2.0] - 2026-07-19
--------------------

First tagged release. Everything below is relative to earlier, untagged git installs.

### Breaking changes

- `Edit*Wrapper` factory methods (`from_list`/`from_json`/`from_adapter`/`from_item`) no longer
  render automatically. Call `render()` explicitly — the factories return the instance and
  `render()` returns it again, so the fluent `EditGridWrapper.from_list(...).render()` works.
- Unknown keyword arguments now raise `TypeError` across all component constructors and factories
  instead of being silently ignored.
- The `select_options` / `radio_options` / `toggle_options` / `checkbox_group_options` attributes
  were removed. Use the unified `options` (with `literal_options` still auto-extracted from
  `Literal[...]`). Passing a removed alias raises `TypeError`.
- `util.submit_dialog` is now async and returns the pressed button's text (or `None` on dismissal)
  instead of returning a dialog to await.
- `create_if_not_exist`, `lock_field` and `created_field` are keyword-only in the `from_json`
  factories.
- `FieldInfo` raises `TypeError` (not `ValueError`) on unknown keyword arguments.
- Internal modules renamed for consistency with their class names: `form.py` → `modelform.py`,
  `grid.py` → `modelgrid.py`, `wrapper.py` → `editwrapper.py`; `DrillDownWrapper` moved to a new
  `drilldown.py`. The canonical import path is unchanged (`from niceview import ...`); only code
  importing private submodules directly is affected.
- `JsonAdapter`/`JsonListAdapter` default to lenient loading (`strict=False`); code that relied on
  a malformed file raising must pass `strict=True`.

### Added

- The full public API is exported from the top-level `niceview` package (all UI components,
  adapters, protocols, errors, and the lenient-load helpers).
- `options` accepts sync **or async** callables; async sources render the widget empty and fill in
  choices when the awaitable resolves, preserving the field's value.
- `notify=False` on `ModelForm.save()` / `refresh()` to suppress the `ui.notify` popups.
- `ModelGrid.on_select` delivers `TableItemSelectEventArguments` with `row_key`/`item`
  (both `None` when the selection is cleared), mirroring `ModelList.on_select`.
- `py.typed` marker so downstream type checkers use NiceView's annotations.
- MIT `LICENSE`; richer packaging metadata; `ruff` linting and a mypy step plus a
  Python 3.12/3.13 matrix in CI.
- Documentation split into a slim landing README plus `docs/` reference pages; `DESIGN.md` and
  `TODO.md` for design decisions and open work.

### Fixed

- README quick-start and examples imported non-existent modules (`niceview.modelform`, etc.);
  imports now use the canonical top-level package.
- `pydantic` is declared as a direct dependency (previously only transitive via NiceGUI).
