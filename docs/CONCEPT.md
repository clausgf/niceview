Concepts
========

How niceview's cascades are put together. The reference for each attribute is in
[components.md](components.md); the reasoning behind single decisions is in [DESIGN.md](DESIGN.md).

Three cascades
--------------

| Cascade | Styles | Set by |
|---|---|---|
| Chrome | what niceview draws *around* a form or grid: title rows, buttons, dialogs, notifications, list rows | `set_chrome_style()`, `chrome_style=` |
| Fields | the widgets inside a form | `set_field_style()`, `ModelForm(base_props=…)`, `FieldInfo(props=…)` |
| Texts | every string niceview shows | `set_chrome_text()`, `chrome_text=` |

What is *not* in any of them: "every element of type X looks like this". That is a statement
about a type, and NiceGUI already owns it — `ui.button.default_props('dense flat')`,
`ui.input.default_props('outlined')`, `ui.colors()`, `ui.dark_mode()`. niceview styles only what
NiceGUI cannot see: the *place* and the *role* of the buttons it builds itself, and the
*category* of the fields it renders.

The chrome cascade: two axes
----------------------------

Every chrome button sits in exactly one **place** and carries exactly one **role**. The two are
independent — a Delete exists in a toolbar and as the confirm button of a dialog — so they are
two layers rather than one combined set of keys (`dialog_delete_button_props` would be n×m
names). Between them sits the shape, a mechanical distinction niceview knows because it decides
whether a button shows a label:

```
{place}_button_props   →   shape   →   {role}_button_props
      context               this button        its meaning
```

Later means more specific to this one button, which is why the role has the last word.

- **places**: `toolbar` (a wrapper's own action row), `form` (the same row for a wrapper
  embedded in a form — an editgrid field), `dialog` (a dialog footer).
- **roles**: `add`, `edit`, `delete`, `save`, `refresh`, `back`, `ok`, `cancel`. Only `delete`
  carries a default (`color=negative`), and only because that is meaning rather than taste.

A wrapper knows its place and passes it to the buttons it builds — `place=` is a plain
parameter, not something derived from the surrounding elements. There is exactly one spot where
niceview nests a wrapper (`ModelForm` rendering an editable editgrid field), and it says
`place='form'` there.

Two places are deliberately absent. A **ModelList row** has one job — navigating into the
detail view — and a button in it would need `.stop` on its click to keep the row from
navigating as well; the detail view is where an item's actions belong. A **ModelGrid row** is
AG Grid: its cells live client-side as cell renderers, not as NiceGUI elements, so Quasar props
do not reach them at all. Grid actions stay in the toolbar, acting on the selection.

Merge semantics
---------------

Readable off the type, one rule per kind:

| Type | Rule |
|---|---|
| `str` | additive layer — props merge per key, the later layer wins |
| `str \| None` | replacing layer — `None` inherits, `''` suppresses, a value replaces |
| `*_classes` | replaces wholesale |

Props are additive because a Quasar prop has a key: `color=primary` followed by `color=negative`
is one key twice, and the later source wins. Classes have no key — `w-full w-1/2` is decided by
stylesheet order, not by list order — so the most specific source replaces the others.

The one replacing layer is the per-place icon shape, and it has to be: Quasar's shapes are
separate *boolean* props, so `round` and `rounded` are two keys and adding one cannot cancel the
other. "Round in a toolbar, square in a dialog" is therefore a replacement, not an addition:

```python
set_chrome_style(icon_button_props='round', dialog_icon_button_props='')
```

The same reasoning explains the group exception: a `ui.button_group` joins straight edges and a
circle has none, so the shape layer is skipped inside a group unless `shape_in_group` says the
shape survives being joined.

The field cascade: categories
-----------------------------

Fields are keyed by widget **category**, which is niceview's vocabulary rather than NiceGUI's:
an input and a select take the same props, a switch does not (`outlined` says nothing to a
checkbox), and an application should not have to enumerate ten widget types to say so.

```
category (application)  →  base_props (one form)  →  FieldInfo.props (one field)
```

Two categories, `INPUT_BASED_WIDGETS` (QInput/QSelect based) and `CONTROL_WIDGETS` (checkbox,
switch, radio, toggle, checkbox_group, slider, rating). They are their own lists, not aliases of
the widget sets next to them in `widgets.py`: that `HINT_WIDGETS` holds the same types today
answers a different question ("does it have a hint slot") and the two may drift apart.

The text cascade
----------------

`ChromeText` holds every string, with named placeholders (`{key}`, `{error}`) so a translation
can reorder a sentence, and each slot accepts a callable as well as a string — resolved when the
text is rendered, which is what a per-client language needs. See [DESIGN.md](DESIGN.md) for why
there is no gettext in the package.

Overriding per widget
---------------------

`chrome_style=` / `chrome_text=` replace the application-wide default for one widget rather than
adding to it, so they are built by deriving:

```python
EditGridWrapper.from_list(User, users, chrome_style=ChromeStyle.derived(button_group=False))
```

Merging a partial style automatically is not possible: a fresh dataclass carries defaults, not
"unset", so `ChromeStyle(button_group=False)` could not be told apart from "every other value
deliberately at its default". Deriving is the price of that, and `derived()` is what makes it
one call.

Relationships: references vs. composition
-----------------------------------------

A model field that points at other records is one of two fundamentally different things, and
niceview renders each with a different widget.

**Composition (`editgrid`)** — the parent *owns* its children; they live inside it. A
`list[Book]` field on an `Author` is a **one-to-many** composition: the `Book` objects are part
of the author's data and are edited inline in an embedded grid (`widget_type='editgrid'`,
inferred automatically from `list[SomeModel]`). Delete the parent, the children go with it.

**Reference (`modelselect`)** — the field *points* at an item that lives in another collection,
storing only its key. This is the **many-to-one** direction (many rooms → one building). It
comes in two shapes:

- **Object-select** — the field is the related object (`author: Author`), with a hidden
  `author_id` FK alongside it (the SQLModel-relationship pattern). niceview writes the key into
  the `author_id` companion, never the relationship attribute, so SQLAlchemy does not
  cascade-insert a detached instance. Inferred automatically for a SQLModel `Mapped[Author]`.

- **Key-select** — the field *is* the scalar key (`building: str | None`), referencing a plain
  niceview `CollectionAdapter`. niceview stores the key directly in the field. The display label
  and the searchable select come from the registered adapter — `with_repositories({'building':
  buildings_adapter})`, keyed by field name — which yields `{key: str(item)}`; `item_type` is
  inferred from the adapter. A validator flags a stored key that no longer exists in the
  collection. Declared explicitly, since a bare `str` cannot name the model it references:

  ```python
  building: Annotated[str | None,
      niceview.Field(widget_type='modelselect', item_type=Building)] = None
  ```

The mode is chosen by the field's type: a model type → object-select, a scalar → key-select.

**Many-to-many** (a `list` of foreign keys) is the plural of key-select and is not built yet —
see [TODO](https://github.com/clausgf/niceview/blob/main/TODO.md). It is *not* `editgrid`:
composition embeds owned objects, a reference list points at shared ones.

Repositories are runtime wiring (live adapters, connections, file paths), so they are provided
at composition time via `with_repositories()`, never declared in `Meta` — `Meta` holds static
model metadata, not instances.

Possible extensions
-------------------

Kept here because the design is settled and the API would be additive, not because it is
planned.

**Row actions in a ModelList**, declaratively rather than as a render callback (a callback would
build its own buttons, past the cascade — and the free-form case is already covered by
`DrillDownWrapper`'s `render_list_item`):

```python
@dataclass(frozen=True)
class ItemAction:
    role: str                                     # 'delete' … → the role layer
    icon: str
    on_click: Callable[[str, Any], Any]           # (row_key, item)
    tooltip: str = ''
    label: str = ''
    visible: Callable[[Any], bool] | None = None  # per row

ModelList.from_list(User, users, actions=[ItemAction('delete', 'delete', on_click=…)])
```

They would render in their own `ui.item_section().props('side')` left of the chevron, built with
`chrome_button(place='list', role=…)` — which is what would give the `list` place something to
style. On a phone the native form of the same thing is a swipe (`ui.slide_item`, with the
desktop icons shown through Quasar's `gt-sm` / `lt-md` so CSS rather than the server decides and
a resize reflows).

It waits because the row already navigates (two click targets in one row, hence the `.stop`),
because the detail view can do it today, and above all because a swipe is not testable with
NiceGUI's `User` fixture — it can click, not drag.
