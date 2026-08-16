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
        ok_role='delete',
    ):
        return
    device_adapter.delete(key)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `title` | `str` | — | Dialog title |
| `message` | `str` | — | Body text (Markdown) |
| `ok_label` | `str \| None` | `None` | Confirm button label; `None` takes `ChromeText.ok_label` |
| `cancel_label` | `str \| None` | `None` | Cancel button label; `None` takes `ChromeText.cancel_label` |
| `ok_role` | `str` | `'ok'` | Role of the confirm button in the chrome cascade. `'delete'` makes it negative — and follows the application's delete styling |
| `chrome_style` | `ChromeStyle \| None` | `None` | Look of this dialog; `None` takes the application-wide style |
| `chrome_text` | `ChromeText \| None` | `None` | Texts of this dialog |

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
| `validator` | `Callable[[str], bool \| Awaitable[bool]] \| None` | `None` | Validation function, sync or async; `True` = valid |
| `error_message` | `str` | `'Invalid input'` | Error shown when validator fails |

The validator may be `async def` — use it when the answer is not local, e.g. a uniqueness check
against a database. It gates the OK button exactly as a sync one does:

```python
async def is_free(name: str) -> bool:
    return await repo.count(name=name) == 0

name = await input_dialog('Create Project', label='Project Name',
                          validator=is_free, error_message='Name already taken')
```

**`submit_dialog`** — generic dialog with custom button list, returns the text of the
pressed button (without prefixes), or `None` if the dialog was dismissed:

```python
result = await submit_dialog('Confirm', 'Proceed?', ['Cancel', '|1OK'])  # 'Cancel' or 'OK'
```

Button labels can be prefixed for spacing (`|`) and color (`1`=primary, `2`=secondary, `a`=accent, `d`=dark, `+`=positive, `-`=negative, `i`=info, `w`=warning). Prefixes can be combined: `'|-OK'` = spacer + negative color.
