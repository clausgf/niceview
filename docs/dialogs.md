Dialogs
=======

Async dialog helpers in `niceview.util`.

[← Back to the README](../README.md)


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
