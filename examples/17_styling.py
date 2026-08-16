"""
Styling and texts: the two application-wide defaults, and the presets you would build on top.

`set_chrome_style()` styles what niceview draws *around* a form or grid — the title row, its
buttons, the dialogs, the notifications. `set_field_style()` styles the fields inside, by
widget category. `set_chrome_text()` replaces every string niceview shows, which is all a
single-language application in a language other than English needs.

Everything ships empty, so a preset is example code rather than API: pick one of the three
below (or write your own) and call it once at startup.
"""
from nicegui import ui
import pydantic

from niceview import (ChromeStyle, ChromeText, EditGridWrapper, EditFormWrapper, FieldStyle,
                      set_chrome_style, set_chrome_text, set_field_style)


class Contact(pydantic.BaseModel):
    name: str = ''
    email: str = ''
    active: bool = True
    note: str = ''

    class Meta:
        layout = [['# Contact', ['name', 'email'], 'active'], ['## Notes', 'note']]


# --- presets ---------------------------------------------------------------
# Not part of niceview's API: the defaults are empty on purpose, and what "compact" or
# "touch" means is yours to decide. Copy the one you like into your own startup code.

def preset_quasar() -> None:
    """Plain Quasar: what niceview looks like out of the box. Nothing is set at all."""
    set_chrome_style(ChromeStyle())
    set_field_style(FieldStyle())


def preset_compact() -> None:
    """Dense, flat, outlined — the look niceview shipped with before styling was configurable."""
    set_chrome_style(
        toolbar_button_props='dense flat',
        form_button_props='dense flat',
        dialog_button_props='flat',
        icon_button_props='round',
    )
    set_field_style(input_props='outlined dense', control_props='dense', default_classes='w-full')


def preset_touch() -> None:
    """Bigger targets for a phone: no button group (round icons need room to breathe), filled
    fields, notifications at the top where a thumb does not cover them."""
    set_chrome_style(
        toolbar_button_props='unelevated',
        dialog_button_props='unelevated',
        icon_button_props='round',
        dialog_icon_button_props='',      # a dialog footer keeps its buttons square
        button_group=False,               # joined or round, not both
        notify_position='top',
        notify_timeout=3.0,
    )
    set_field_style(input_props='filled', default_classes='w-full')


def preset_german() -> None:
    """Same widgets, German texts. Nothing else changes — the texts are a separate cascade."""
    set_chrome_text(
        add_tooltip='Neuen Eintrag anlegen',
        edit_tooltip='Eintrag bearbeiten',
        delete_tooltip='Ausgewählten Eintrag löschen',
        delete_item_tooltip='Diesen Eintrag löschen',
        refresh_tooltip='Neu laden',
        save_tooltip='Speichern',
        back_tooltip='Zurück',
        ok_label='Ok',
        cancel_label='Abbrechen',
        create_label='Anlegen',
        delete_label='Löschen',
        delete_selected_title='Löschen bestätigen',
        delete_selected_message='Den ausgewählten Eintrag *{key}* wirklich löschen?',
        item_created='Eintrag angelegt',
        item_updated='Eintrag gespeichert',
        item_deleted='Eintrag gelöscht',
        create_error='Fehler beim Anlegen: {error}',
        select_row_first='Bitte zuerst eine Zeile auswählen!',
        required_message='Pflichtfeld',
    )


PRESETS = {'Quasar': preset_quasar, 'Compact': preset_compact, 'Touch': preset_touch}

contacts = [Contact(name='Alice', email='alice@example.com'),
            Contact(name='Bob', email='bob@example.com', active=False)]


@ui.refreshable
def demo() -> None:
    with ui.card().classes('w-full'):
        EditGridWrapper.from_list(Contact, contacts, title='Contacts').render()
    with ui.card().classes('w-full'):
        EditFormWrapper.from_item(contacts[0], title='Details').render()


@ui.page('/')
def page() -> None:
    with ui.column().classes('w-full max-w-3xl mx-auto p-4 gap-4'):
        ui.label('Styling presets').classes('text-h5')
        with ui.row().classes('items-center gap-4'):
            ui.toggle(list(PRESETS), value='Quasar',
                      on_change=lambda e: (PRESETS[e.value](), demo.refresh()))
            ui.switch('Deutsch', on_change=lambda e: (
                preset_german() if e.value else set_chrome_text(ChromeText()), demo.refresh()))
        ui.markdown('A preset is one call at startup. Everything below re-renders with it.')
        demo()


# An application-wide look that is *not* niceview's business: "every button of this app is
# dense" is a type statement, and NiceGUI owns it.
#   ui.button.default_props('dense')
#   ui.input.default_props('outlined')

ui.run(title='niceview — styling')
