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
    """Tooltip of the Add button."""
    edit_tooltip: TextValue = 'Edit item'
    """Tooltip of the Edit button."""
    delete_tooltip: TextValue = 'Delete selected item'
    """The grid's Delete acts on the selected row."""
    delete_item_tooltip: TextValue = 'Delete this item'
    """The drill-down's Delete acts on the item that is open."""
    refresh_tooltip: TextValue = 'Refresh'
    """Tooltip of the Refresh button."""
    save_tooltip: TextValue = 'Save'
    """Tooltip of the Save button."""
    back_tooltip: TextValue = 'Back'
    """Tooltip of the Back button."""
    search_placeholder: TextValue = 'Search'
    """Placeholder of the search input (EditGridWrapper's search=True)."""

    # --- dialog labels -----------------------------------------------------
    ok_label: TextValue = 'OK'
    """Confirm button label in a dialog."""
    cancel_label: TextValue = 'Cancel'
    """Cancel button label in a dialog."""
    create_label: TextValue = 'Create'
    """Confirm button label of the create dialog."""
    delete_label: TextValue = 'Delete'
    """Confirm button label of a delete confirmation."""

    # --- dialogs -----------------------------------------------------------
    delete_selected_title: TextValue = 'Confirm Deletion'
    """Title of the grid's delete-confirmation dialog."""
    delete_selected_message: TextValue = 'Are you sure you want to delete the selected item *{key}*?'
    """Message of the grid's delete-confirmation dialog; {key} is the selected row's key."""
    delete_item_title: TextValue = 'Delete'
    """Title of the drill-down's delete-confirmation dialog."""
    delete_item_message: TextValue = 'Delete this item? This cannot be undone.'
    """Message of the drill-down's delete-confirmation dialog."""
    invalid_input: TextValue = 'Invalid input'
    """Shown when a value fails validation."""
    unknown_selection: TextValue = 'Unknown selection — no longer in the list'
    """Shown when the selected row is no longer in the collection."""

    # --- notifications -----------------------------------------------------
    item_created: TextValue = 'Item created'
    """Notification after a successful create."""
    item_updated: TextValue = 'Item updated'
    """Notification after a successful update."""
    item_deleted: TextValue = 'Item deleted'
    """Notification after a successful delete."""
    create_cancelled: TextValue = 'Item creation cancelled'
    """Notification when the create dialog is cancelled."""
    update_cancelled: TextValue = 'Item update cancelled'
    """Notification when an update dialog is cancelled."""
    delete_cancelled: TextValue = 'Item deletion cancelled'
    """Notification when a delete confirmation is cancelled."""
    create_error: TextValue = 'Error creating item: {error}'
    """Notification when create fails; {error} is the exception."""
    update_error: TextValue = 'Error updating item: {error}'
    """Notification when update fails; {error} is the exception."""
    delete_error: TextValue = 'Error deleting item {key}: {error}'
    """Notification when a grid's delete fails; {key} and {error} name the row and exception."""
    delete_failed: TextValue = 'Error deleting item: {error}'
    """Deleting the open item in a drill-down, where the key is not worth naming again."""
    save_error: TextValue = 'Error saving change: {error}'
    """Notification when an autosaving form's save fails; {error} is the exception."""
    select_row_first: TextValue = 'Please select a row first!'
    """Notification when an action needs a selected row but none is selected."""
    select_row_to_delete: TextValue = 'Please select a row for deletion!'
    """Notification when Delete is clicked with no row selected."""
    item_not_found: TextValue = 'Item with key {key} not found'
    """Notification when {key} no longer exists in the collection."""
    row_not_found: TextValue = 'Row {key} not found — try again'
    """Notification when a grid row's key no longer exists."""
    conflict: TextValue = 'This item was changed by another user. The list has been refreshed — please edit again.'
    """Notification when a save loses an optimistic-lock conflict to another writer."""
    invalid_value: TextValue = 'Invalid value {value!r}: {errors}'
    """Notification for an invalid value outside a form (e.g. an inline grid edit)."""
    validation_errors: TextValue = 'Cannot save form: validation errors present'
    """Notification when Save is blocked by validation errors."""
    form_refreshed: TextValue = 'Form refreshed'
    """Notification after Refresh reloads a form."""
    form_saved: TextValue = 'Form saved'
    """Notification after a non-autosaving form saves."""

    # --- body labels -------------------------------------------------------
    no_items: TextValue = 'No items yet.'
    """Shown in an empty list view."""
    detail_not_found: TextValue = 'Item {key!r} not found.'
    """Shown in the detail view when {key} no longer exists."""

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
