Changelog
=========

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

[0.21.3] - 2026-08-18
---------------------

### Changed

- **The application-wide `FieldStyle` now reaches the model-free `render_field()`**, not only a
  `ModelForm`. `input_props` / `control_props` (by widget category) and the `default_classes`
  fallback apply to a standalone field too; a field's own props/classes still win, and a
  ModelForm's per-form layers (`base_props`, its own `default_classes`, the layout) remain
  form-only. The shared `field_style_props()` helper keeps the two paths from drifting.

- **`timedelta` fields accept tolerant input.** Besides the canonical ISO 8601 duration they
  accept it case-insensitively (`p7d`), the fixed-length calendar units pydantic understands
  (`P1Y` = 365 d, `P1M` = 30 d, `P1W` = 7 d), and a human shorthand of `<number><unit>` parts
  with units `y w d h m s` (`7d`, `2h30m`, `1.5h`, `-2h`); on blur the field rewrites the entry
  to its canonical form. A bare number is still rejected — pydantic would read `7` as 7 seconds.
  New helper `niceview.widgets.parse_timedelta()`.

[0.21.2] - 2026-08-18
---------------------

### Fixed

- **`niceview.Field(label='')` in a model annotation now suppresses the label**, overriding both
  the auto-generated name and a `pydantic.Field(title=…)` — the same as passing it at the
  constructor. Previously an empty label in the annotation was indistinguishable from an unset
  one and fell back to the generated name.

[0.21.1] - 2026-08-18
---------------------

### Added

- **Form layout containers and two field bits are chrome knobs now.** `ChromeStyle` gains
  `form_row_classes`, `form_column_classes`, `form_card_classes` and `form_card_props` for the
  containers a layout builds; `FieldStyle` gains `caption_classes` (the label above radio /
  toggle / checkbox_group / slider / rating) and `checkbox_group_classes` (the checkbox
  container). Defaults are unchanged, so nothing renders differently — but a row's alignment no
  longer needs a `':classes'` first element on every layout. See [Layout](components.md#layout).

[0.21.0] - 2026-08-16
---------------------

An application's own button reaches every title row, and the examples become documentation pages
of their own.

### Added

- **`chrome_actions=` on every wrapper.** `EditGridWrapper` and `DrillDownWrapper` now take the
  same `FormAction` table in their title row that `EditFormWrapper` already did — rendered left of
  niceview's own buttons, exposed as `wrapper.action_buttons`. A title row without a form has no
  item to hand over, so each place sends the event arguments of what it is about:
  `GridActionEventArguments` (`e.row_key`, `e.item` — the selected row, both `None` when nothing
  is selected) and `DrillDownActionEventArguments` (`e.key`, `e.item` — the item on screen),
  beside the existing `FormActionEventArguments` (`e.form`). All three are exported from
  `niceview`, so a handler can spell out what it takes. A drill-down's actions sit left of
  Delete and are hidden in the list view, where there is no single item to act on.
  `requires_valid` follows the detail form such a wrapper builds itself; where there is no form to
  ask — an `EditGridWrapper`, a `DrillDownWrapper` with a `render_detail` of its own — it raises
  instead of leaving the button enabled without a word.

- **The examples are part of the documentation site.** One page per example, generated at build
  time from the example's own docstring — the text the app already prints on its first page — with
  a screenshot of it running, a link to the source and the source itself. Nothing to keep in sync
  by hand: a new example appears in the navigation on its own. The screenshots are committed and
  refreshed with `docs/screenshots/capture_examples.py`, so building the docs needs no browser.

### Changed

- `modelform.render_action_button()` builds every action button now — a form's `'@name'` and
  every wrapper's `chrome_actions` — so the two cannot drift apart, and `FormAction.on_click` is
  typed as the union of the three handlers.


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


