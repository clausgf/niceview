import inspect
from typing import Any, Awaitable, Callable
from nicegui import helpers, ui
from nicegui.elements.mixins.validation_element import ValidationDict, ValidationFunction

from niceview.style import (ChromeStyle, chrome_button, chrome_dialog, chrome_dialog_buttons,
                            chrome_dialog_title, get_chrome_style)
from niceview.text import ChromeText, get_chrome_text, text_of


def meta_option(item_type: type, kwargs: dict, key: str, default: Any, *, meta_key: str | None = None) -> Any:
    """Resolve a wrapper option from (descending priority) kwargs, the model's Meta, or default.

    Pops `key` from `kwargs`: an explicitly passed value (even None) wins over Meta, mirroring
    how ModelForm reads its own Meta options. `meta_key` reads a differently named Meta attribute
    (e.g. a collection wrapper's `title` kwarg defaulting from `Meta.title_plural`).
    """
    meta = getattr(item_type, 'Meta', None)
    value = getattr(meta, meta_key or key, default) if meta is not None else default
    return kwargs.pop(key, value)


async def maybe_await(result: Any) -> Any:
    """
    Await `result` if it is awaitable, pass it through otherwise.

    Calling an `async def` handler returns a coroutine; dropping it does nothing at all except
    emit a RuntimeWarning, which is the worst way for a click handler to fail. Every place that
    invokes a caller-supplied callback directly (rather than through NiceGUI's `handle_event`,
    which does the same thing for callbacks that take an event argument) goes through here, so
    `def` and `async def` are equally valid there.
    """
    return await result if inspect.isawaitable(result) else result


async def confirm_dialog(
    title: str,
    message: str,
    *,
    ok_label: str | None = None,
    cancel_label: str | None = None,
    ok_role: str = 'ok',
    chrome_style: ChromeStyle | None = None,
    chrome_text: ChromeText | None = None,
) -> bool:
    """Show a confirmation dialog. Returns True if confirmed, False if cancelled.

    `ok_role` picks the role layer of the chrome cascade for the confirm button rather than a
    color: 'delete' makes it negative, and an application that restyles its delete buttons
    restyles this one with them.

    Usage:
        if not await confirm_dialog('Delete Device', f'Delete {name!r}? Irreversible.',
                                    ok_label='Delete', ok_role='delete'):
            return
    """
    style = chrome_style or get_chrome_style()
    text = chrome_text or get_chrome_text()
    with chrome_dialog(style) as dialog:
        chrome_dialog_title(title, style)
        ui.markdown(message)
        with chrome_dialog_buttons(style):
            chrome_button('cancel', cancel_label or text_of(text.cancel_label), None, '', style,
                          lambda: dialog.submit(False), place='dialog')
            chrome_button(ok_role, ok_label or text_of(text.ok_label), None, '', style,
                          lambda: dialog.submit(True), place='dialog')
    return await dialog


async def input_dialog(
    title: str,
    *,
    label: str,
    placeholder: str = '',
    value: str = '',
    validator: Callable[[str], bool | Awaitable[bool]] | None = None,
    error_message: str | None = None,
    chrome_style: ChromeStyle | None = None,
    chrome_text: ChromeText | None = None,
) -> str | None:
    """Show an input dialog. Returns the entered string, or None if cancelled.

    The validator may be sync or async — async is what you want when the answer lives elsewhere
    ("is this name still free?"), and it gates the OK button just as a sync one does.

    Usage:
        name = await input_dialog('Create Project', label='Project Name',
                                   placeholder='my-project', validator=is_valid_filename,
                                   error_message='Only letters, digits, _ - + allowed')
        if name is None:
            return  # cancelled
        create_project(name)
    """
    style = chrome_style or get_chrome_style()
    text = chrome_text or get_chrome_text()
    message = error_message or text_of(text.invalid_input)
    with chrome_dialog(style) as dialog:
        chrome_dialog_title(title, style)
        # A sync validator goes into Quasar's validation dict unchanged. An async one cannot:
        # NiceGUI's ValidationDict is sync-only, so it is wrapped in a ValidationFunction,
        # which does accept awaitables.
        validation: ValidationFunction | ValidationDict | None
        if validator is None:
            validation = None
        elif helpers.is_coroutine_function(validator):
            async def validation(value: str) -> str | None:  # type: ignore[no-redef]
                return None if await validator(value) else message  # type: ignore[misc, union-attr]
        else:
            validation = {message: validator}  # type: ignore[dict-item]
        inp = ui.input(label=label, placeholder=placeholder, value=value, validation=validation)
        with chrome_dialog_buttons(style):
            chrome_button('cancel', text_of(text.cancel_label), None, '', style,
                          lambda: dialog.submit(None), place='dialog')

            async def on_ok() -> None:
                if validator is not None and not await maybe_await(validator(inp.value)):
                    # return_result=False: an async validation function has no synchronous
                    # answer to give, and we only call this for the error message anyway.
                    inp.validate(return_result=False)
                    return
                dialog.submit(inp.value)
            chrome_button('ok', text_of(text.ok_label), None, '', style, on_ok, place='dialog')
    return await dialog


async def submit_dialog(title: str, message: str, buttons: 'tuple[str, ...] | list[str]' = ('Cancel', 'OK'),
                        *, chrome_style: ChromeStyle | None = None) -> str | None:
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

    style = chrome_style or get_chrome_style()
    with chrome_dialog(style) as dialog:
        chrome_dialog_title(title, style)
        ui.markdown(message)
        with chrome_dialog_buttons(style):
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
                # The chrome cascade styles the button; the prefix, being the most specific
                # source, has the last word on its color.
                element = chrome_button('ok', button, None, '', style,
                                        lambda msg: dialog.submit(msg.sender.text), place='dialog')
                if prop:
                    element.props(prop)
    return await dialog
