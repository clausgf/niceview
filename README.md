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


ModelForm
---------

`ModelForm` renders a Pydantic model as an editable form.

```python
# From a model instance (edits the instance in-place)
form = ModelForm.from_item(item, title='Edit User', classes='w-full')

# From a JSON file (creates file with defaults if missing; autosave on each validated change)
form = ModelForm.from_json(User, Path('user.json'), autosave=True)
# With explicit save button instead of autosave
form = ModelForm.from_json(User, Path('user.json'), save_button='Save', refresh_button='')
# Fail if file does not exist (no auto-creation)
form = ModelForm.from_json(User, Path('user.json'), create_if_not_exist=False)

# From a data adapter (supports refresh and save buttons)
form = ModelForm(User, title='Edit User', save_button='', refresh_button='')
form.set_item_from_model(adapter, key)
form.render()

# Options
ModelForm(User,
    include=['name', 'age'],    # or exclude=['active']
    autosave=True,              # save on every change
    save_button='Save',         # show save button ('' = icon only)
    refresh_button='',          # show refresh button
    local_tz='Europe/Berlin',   # timezone for datetime fields (None = system local)
    on_change=my_callback,      # called on every validated change
)
```

**Change events** are emitted after successful validation via `on_change`:
```python
form.on_change(lambda e: print(e.field_name, e.old_value, e.new_value))
```


ModelGrid / ModelGridInlineEdit
--------------------------------

`ModelGrid` renders a Pydantic model list as an AgGrid table.

```python
from niceview.modelgrid import ModelGrid, ModelGridInlineEdit
from niceview.dataadapter import ListModelAdapter

adapter = ListModelAdapter(User, user_list)

# Read-only grid
grid = ModelGrid(User, adapter, fields=['name', 'age'])
grid.render()

# Inline-editable grid
grid = ModelGridInlineEdit(User, adapter)
grid.render()
grid.on_change(lambda e: print(e.row_key, e.item))
```


EditGridWrapper / EditFormWrapper
----------------------------------

Wrappers that add Add/Delete/Edit functionality on top of a grid:

```python
from niceview.modeledit import EditGridWrapper, EditFormWrapper

# Grid with Add/Delete buttons and a popup form for editing
wrapper = EditGridWrapper(ModelGrid(User, adapter), title='Users')
wrapper.render()

# Form with Save/Refresh/Delete buttons backed by a data adapter
form = ModelForm(User)
form.set_item_from_model(adapter, key)
edit = EditFormWrapper(form)
edit.render()
```


Data Adapters
-------------

| Adapter | Description |
|---|---|
| `ListModelAdapter(Type, list)` | In-memory list |
| `JsonSingleModelAdapter(Type, path)` | Single item in a JSON file |
| `SqlModelAdapter(Type, engine)` | SQLModel / SQLAlchemy database table |


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

Use `niceview.Field()` as a Pydantic `Annotated` metadata to customize a field:

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
