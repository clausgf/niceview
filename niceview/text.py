"""
Every string niceview shows: button tooltips, dialog labels, notifications, the two field
markers. Replaceable as a whole for a single-language application in any language, and per
client for a multilingual one.

    set_chrome_text(delete_tooltip='Ausgewählten Eintrag löschen')   # one language, right now
    set_chrome_text(delete_tooltip=lambda: _('delete_tooltip'))      # per client, later

Why niceview brings no gettext of its own:

  - A library must not pick the i18n stack of the application that uses it. Django can
    prescribe gettext because Django *is* the framework; niceview is not.
  - More to the point, a NiceGUI locale is per client, not per process, while gettext's
    locale is process-global. A server that serves two sessions in two languages at the same
    time cannot be served by a module-level translation — which is why every slot here also
    accepts a callable, resolved when the text is rendered rather than when it is configured.

Texts of the *model* are deliberately not here: a field's label comes from FieldInfo (or from
pydantic's `title`), so it already belongs to the application, which can localize it where it
defines it. niceview owns only its own strings.

Placeholders are named, never positional ('{key}', '{error}') — a translator has to be able to
reorder a sentence.
"""
import dataclasses
from dataclasses import dataclass
from typing import Any, Callable, Self


TextValue = str | Callable[[], str]
"""A text: either the string itself, or a callable returning it. The callable is invoked every
time the text is rendered, so it can resolve the current client's language."""


def text_of(value: TextValue, /, **params: Any) -> str:
    """
    Resolve a text: call it if it is a callable, then fill in its named placeholders.

    Without params the template is returned unchanged, so a text containing braces of its own
    survives (formatting it would raise).
    """
    text = value() if callable(value) else value
    return text.format(**params) if params else text


@dataclass(frozen=True)
class ChromeText:
    """
    The texts of the chrome. Immutable — derive one with replace() or ChromeText.derived().
    """

    # --- button tooltips ---------------------------------------------------
    add_tooltip: TextValue = 'Add a new item'
    edit_tooltip: TextValue = 'Edit item'
    delete_tooltip: TextValue = 'Delete selected item'
    """The grid's Delete acts on the selected row."""
    delete_item_tooltip: TextValue = 'Delete this item'
    """The drill-down's Delete acts on the item that is open."""
    refresh_tooltip: TextValue = 'Refresh'
    save_tooltip: TextValue = 'Save'
    back_tooltip: TextValue = 'Back'

    # --- dialog labels -----------------------------------------------------
    ok_label: TextValue = 'OK'
    cancel_label: TextValue = 'Cancel'
    create_label: TextValue = 'Create'
    delete_label: TextValue = 'Delete'

    # --- dialogs -----------------------------------------------------------
    delete_selected_title: TextValue = 'Confirm Deletion'
    delete_selected_message: TextValue = 'Are you sure you want to delete the selected item *{key}*?'
    delete_item_title: TextValue = 'Delete'
    delete_item_message: TextValue = 'Delete this item? This cannot be undone.'
    invalid_input: TextValue = 'Invalid input'

    # --- notifications -----------------------------------------------------
    item_created: TextValue = 'Item created'
    item_updated: TextValue = 'Item updated'
    item_deleted: TextValue = 'Item deleted'
    create_cancelled: TextValue = 'Item creation cancelled'
    update_cancelled: TextValue = 'Item update cancelled'
    delete_cancelled: TextValue = 'Item deletion cancelled'
    create_error: TextValue = 'Error creating item: {error}'
    update_error: TextValue = 'Error updating item: {error}'
    delete_error: TextValue = 'Error deleting item {key}: {error}'
    delete_failed: TextValue = 'Error deleting item: {error}'
    """Deleting the open item in a drill-down, where the key is not worth naming again."""
    save_error: TextValue = 'Error saving change: {error}'
    select_row_first: TextValue = 'Please select a row first!'
    select_row_to_delete: TextValue = 'Please select a row for deletion!'
    item_not_found: TextValue = 'Item with key {key} not found'
    row_not_found: TextValue = 'Row {key} not found — try again'
    conflict: TextValue = 'This item was changed by another user. The list has been refreshed — please edit again.'
    invalid_value: TextValue = 'Invalid value {value!r}: {errors}'
    validation_errors: TextValue = 'Cannot save form: validation errors present'
    form_refreshed: TextValue = 'Form refreshed'
    form_saved: TextValue = 'Form saved'

    # --- body labels -------------------------------------------------------
    no_items: TextValue = 'No items yet.'
    detail_not_found: TextValue = 'Item {key!r} not found.'

    # --- fields ------------------------------------------------------------
    required_marker: TextValue = ' *'
    """Appended to the label of a required field. A form may still set None to render none."""
    required_message: TextValue = 'Required'
    """Validation message of an empty required field."""

    def replace(self, **overrides: Any) -> Self:
        """Return a copy with the given texts changed."""
        return dataclasses.replace(self, **overrides)

    @classmethod
    def derived(cls, **overrides: Any) -> 'ChromeText':
        """The application-wide texts with the given ones changed — for a single widget's
        `chrome_text=`, which replaces the default rather than adding to it."""
        return get_chrome_text().replace(**overrides)


_chrome_text = ChromeText()


def get_chrome_text() -> ChromeText:
    """The current application-wide chrome texts."""
    return _chrome_text


def set_chrome_text(text: ChromeText | None = None, **overrides: Any) -> ChromeText:
    """
    Set the application-wide chrome texts and return them. Call with a complete ChromeText, or
    with keyword arguments to change single texts of the current one:

        set_chrome_text(add_tooltip='Neuen Eintrag anlegen', ok_label='Ok')

    Widgets read the texts when they render, so this takes effect for everything rendered
    afterwards — call it once at startup.
    """
    global _chrome_text
    _chrome_text = (text or _chrome_text).replace(**overrides)
    return _chrome_text
