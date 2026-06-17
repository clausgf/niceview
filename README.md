NiceView
========

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


API Design
----------

NiceView follows a consistent factory pattern across all backends and UI components:

| | **ModelForm** (single item) | **ModelGrid / ModelGridInlineEdit** (list) |
|---|---|---|
| **In-memory** | `ModelForm.from_item(Type, instance)` | `ModelGrid.from_list(Type, items)` |
| **JSON file** | `ModelForm.from_json(Type, path)` | `ModelGrid.from_json(Type, path)` |
| **Any adapter** | `ModelForm.from_adapter(Type, adapter, key)` | `ModelGrid.from_adapter(Type, adapter)` |

All `from_*` methods accept the same keyword options (see below).
`ModelGridInlineEdit` uses the same factory methods as `ModelGrid` via inheritance.

**Data adapters** are the abstraction layer between UI components and storage backends.
The `from_*` convenience methods create and hide the adapter; pass an adapter explicitly
for full control or when using SQL / custom backends.


ModelForm
---------

`ModelForm` renders a Pydantic model as an editable form.

```python
from niceview.modelform import ModelForm
from pathlib import Path

# In-memory: edits the instance in-place, no persistence
form = ModelForm.from_item(user)           # type inferred from instance
form = ModelForm.from_item(User, user)     # explicit type (for API symmetry)

# JSON file: reads/writes a single object; created with defaults if missing
form = ModelForm.from_json(User, Path('user.json'), autosave=True)
form = ModelForm.from_json(User, Path('user.json'), save_button='', refresh_button='')
form = ModelForm.from_json(User, Path('user.json'), create_if_not_exist=False)

# Any adapter (e.g. SQL): full control over backend
adapter = SqlModelAdapter(User, engine)
form = ModelForm.from_adapter(User, adapter, key, save_button='', refresh_button='')

form.render()
```

**Master-detail navigation** — switch the displayed item at runtime:
```python
form.load(adapter, new_key)
```

**Options** (apply to all factory methods):
```python
ModelForm.from_item(user,
    include=['name', 'age'],    # or exclude=['active']
    autosave=True,              # save after every validated change
    save_button='Save',         # show save button ('' = icon only)
    refresh_button='',          # show refresh button ('' = icon only)
    local_tz='Europe/Berlin',   # timezone for datetime display
    on_change=my_callback,      # called after every validated change
    title='Edit User',
    classes='w-full',
)
```

**Change events** carry field name and old/new value:
```python
form.on_change(lambda e: print(e.field_name, e.old_value, e.new_value))
```


ModelGrid / ModelGridInlineEdit
--------------------------------

`ModelGrid` renders a list as a read-only AgGrid table.
`ModelGridInlineEdit` adds per-cell editing with immediate validation and persistence.

```python
from niceview.modelgrid import ModelGrid, ModelGridInlineEdit

# In-memory list
grid = ModelGrid.from_list(User, user_list, fields=['name', 'age'])
grid = ModelGridInlineEdit.from_list(User, user_list)

# JSON file: created with [] if missing; Refresh button reloads from disk
grid = ModelGrid.from_json(User, Path('users.json'))
grid = ModelGridInlineEdit.from_json(User, Path('users.json'))

# Any adapter (two equivalent forms)
grid = ModelGrid(User, adapter)                   # constructor
grid = ModelGrid.from_adapter(User, adapter)      # for API symmetry with ModelForm.from_adapter()

grid.render()
grid.on_change(lambda e: print(e.row_key, e.field_name, e.new_value))
```


EditGridWrapper / EditFormWrapper
----------------------------------

Wrappers that add Add / Edit / Delete buttons on top of a grid or form:

```python
from niceview.modeledit import EditGridWrapper, EditFormWrapper

# Full CRUD: popup dialog for Add/Edit, Delete button, optional Refresh
EditGridWrapper(ModelGrid.from_list(User, user_list), title='Users').render()
EditGridWrapper(ModelGridInlineEdit.from_json(User, Path('users.json')), title='Users').render()

# Form wrapper with Save/Cancel/Refresh
edit = EditFormWrapper(ModelForm.from_adapter(User, adapter, key))
edit.render()
```


Data Adapters
-------------

Adapters decouple UI components from storage. Pass them explicitly for full control,
or let the `from_*` factory methods create them transparently.

| Adapter | Backs | Description |
|---|---|---|
| `ListModelAdapter(Type, list)` | Grid, Form | In-memory list |
| `JsonModelAdapter(Type, path)` | Form | Single object in a JSON file |
| `JsonListModelAdapter(Type, path)` | Grid | List of objects in a JSON file |
| `SqlModelAdapter(Type, engine)` | Grid, Form | SQLModel / SQLAlchemy table |

All JSON adapters write atomically (`.tmp` → rename).
`JsonListModelAdapter` exposes `reload()` to re-read from disk after external changes.

```python
from niceview.dataadapter import SqlModelAdapter

adapter = SqlModelAdapter(Book, engine)                    # with optimistic locking (updated_at)
adapter = SqlModelAdapter(Book, engine, lock_field=None)   # without locking

# Form for a specific record
form = ModelForm.from_adapter(Book, adapter, book_id, save_button='', refresh_button='')
form.render()

# Grid over the full table
ModelGrid(Book, adapter).render()
EditGridWrapper(ModelGrid(Book, adapter), title='Books').render()
```


Supported Field Types
---------------------

| Python type | Widget |
|---|---|
| `str` | `ui.input` |
| `int`, `float` | `ui.number` |
| `bool` | `ui.switch` or `ui.checkbox` |
| `datetime.date` | HTML date input |
| `datetime.time` | HTML time input |
| `datetime.datetime` | HTML datetime-local input |
| `datetime.timedelta` | `ui.input` (ISO 8601 duration) |
| `Literal['a', 'b', ...]` | `ui.select` |
| `list[str]` | `ui.input_chips` |
| `list[BaseModel]` | Inline `EditGridWrapper` |
| SQLModel relationship | `ui.select` (via model repository) |


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
        field_info = {
            'secret': niceview.Field(hidden=True),
        }
```

Key `FieldInfo` options: `label`, `placeholder`, `tooltip`, `hidden`, `editable`, `widget_type`, `min`, `max`, `classes`, `select_options`.


Validation
----------

Field-level and model-level (`@model_validator`) errors are displayed in the form. Field errors appear inline below the widget; model-level errors appear at the bottom of the form.


Development
-----------

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

Run tests:
```bash
pytest
```


Open Questions / TODO
---------------------

- How do we detect leaving the form? How do we guarantee a valid model state on navigation?
- NiceGUI element lifecycle: when are elements instantiated, active, deleted?
- Support binding in tables (two-way sync between grid rows and model)?
- Support dataclasses in addition to Pydantic models?
- SQLModel support: completeness, tests, inline docs
