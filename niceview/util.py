from nicegui import ui


def submit_dialog(title: str, message: str, buttons: list[str] = ["Cancel", "OK"]) -> ui.dialog:
    """Create a dialog with a title, message and buttons.
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
       dialog = my_dialog('Title', 'Message', ['|dCancel', 'OK'])
       result = await dialog  # result is the button text "Cancel" or "OK"
       """

    dialog = ui.dialog().style('width: 400px')
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
    return dialog


# ***************************************************************************
