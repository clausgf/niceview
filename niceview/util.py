from typing import Callable
from nicegui import ui


async def confirm_dialog(
    title: str,
    message: str,
    *,
    ok_label: str = 'OK',
    cancel_label: str = 'Cancel',
    ok_color: str = 'primary',
) -> bool:
    """Show a confirmation dialog. Returns True if confirmed, False if cancelled.

    Usage:
        if not await confirm_dialog('Delete Device', f'Delete {name!r}? Irreversible.',
                                    ok_label='Delete', ok_color='negative'):
            return
    """
    dialog = ui.dialog().props(':maximized="$q.screen.lt.md" transition-show="slide-up" transition-hide="slide-down"').style('width: 400px')
    with dialog:
        with ui.card().classes('w-full'):
            ui.label(title).classes('text-h6')
            ui.markdown(message)
            with ui.row().classes('w-full place-content-end'):
                ui.button(cancel_label, on_click=lambda: dialog.submit(False))
                ui.button(ok_label, on_click=lambda: dialog.submit(True)).props(f'color={ok_color}')
    return await dialog


async def input_dialog(
    title: str,
    *,
    label: str,
    placeholder: str = '',
    value: str = '',
    validator: Callable[[str], bool] | None = None,
    error_message: str = 'Invalid input',
) -> str | None:
    """Show an input dialog. Returns the entered string, or None if cancelled.

    Usage:
        name = await input_dialog('Create Project', label='Project Name',
                                   placeholder='my-project', validator=is_valid_filename,
                                   error_message='Only letters, digits, _ - + allowed')
        if name is None:
            return  # cancelled
        create_project(name)
    """
    dialog = ui.dialog().props(':maximized="$q.screen.lt.md" transition-show="slide-up" transition-hide="slide-down"').style('width: 400px')
    with dialog:
        with ui.card().classes('w-full'):
            ui.label(title).classes('text-h6')
            validation = {error_message: validator} if validator is not None else None
            inp = ui.input(label=label, placeholder=placeholder, value=value, validation=validation)
            with ui.row().classes('w-full place-content-end'):
                ui.button('Cancel', on_click=lambda: dialog.submit(None))
                def on_ok():
                    if validator is not None and not validator(inp.value):
                        inp.validate()
                        return
                    dialog.submit(inp.value)
                ui.button('OK', on_click=on_ok).props('color=primary')
    return await dialog


async def submit_dialog(title: str, message: str, buttons: 'tuple[str, ...] | list[str]' = ('Cancel', 'OK')) -> str | None:
    """Show a dialog with a title, message and buttons; returns the text of the
       pressed button, or None if the dialog was dismissed (e.g. Escape key).
       Buttons can be prefixed with a character for formatting and to set the color:
       - '|': space before button (also in combination with color)
       - '1': primary
       - '2': secondary
       - 'a': accent
       - 'd': dark
       - '+': positive
       - '-': negative
       - 'i': info
       - 'w': warning

       Usage:
       result = await submit_dialog('Title', 'Message', ['|dCancel', 'OK'])
       # result is the button text "Cancel" or "OK" (without prefixes), or None
       """

    dialog = ui.dialog().props(':maximized="$q.screen.lt.md" transition-show="slide-up" transition-hide="slide-down"').style('width: 400px')
    with dialog:
        with ui.card().classes('w-full'):
            ui.label(title).classes('text-h6 center')
            ui.markdown(message)
            with ui.row().classes('w-full place-content-end'):
                for button in buttons:
                    if button.startswith('|'):
                        ui.space()
                        button = button[1:]
                    s2prop = { '1': 'color=primary', '2': 'color=secondary', 
                            'a': 'color=accent', 'd': 'color=dark', 
                            '+': 'color=positive', '-': 'color=negative',
                            'i': 'color=info', 'w': 'color=warning',}
                    if button[0] in s2prop:
                        prop = s2prop[button[0]]
                        button = button[1:]
                    else:
                        prop = None
                    ui.button(button).on_click(lambda msg: dialog.submit(msg.sender.text)).props(prop)
    return await dialog
