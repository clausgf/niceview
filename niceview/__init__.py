import logging
from typing import Any, Unpack

from niceview.fieldinfo import _FieldInfoInputs, FieldInfo
from niceview.dataadapter import (
    BoundFieldAdapter,
    BoundItem,
    CollectionAdapter,
    ConflictError,
    DirectoryAdapter,
    FileEntry,
    FilteredAdapter,
    ItemAdapter,
    JsonAdapter,
    JsonDirectoryAdapter,
    JsonListAdapter,
    ListAdapter,
    ReactiveAdapter,
    ReloadableAdapter,
    StorageError,
    lenient_list_load,
    lenient_model_load,
)
from niceview.widgets import CheckboxGroup, field_value, render_field, to_widget_value
from niceview.modelform import FormAction, FormActionEventArguments, ModelForm
from niceview.modelgrid import ModelGrid, ModelGridInlineEdit
from niceview.editwrapper import EditFormWrapper, EditGridWrapper, GridActionEventArguments
from niceview.modellist import ModelList
from niceview.drilldown import DrillDownActionEventArguments, DrillDownWrapper
from niceview.style import (ChromeStyle, FieldStyle, get_chrome_style, get_field_style,
                            set_chrome_style, set_field_style)
from niceview.text import ChromeText, get_chrome_text, set_chrome_text

__all__ = [
    # Field customization
    'Field', 'FieldInfo',
    # Single widgets without a model
    'render_field', 'field_value', 'to_widget_value',
    # UI components
    'ModelForm', 'FormAction', 'CheckboxGroup',
    'ModelGrid', 'ModelGridInlineEdit',
    'EditFormWrapper', 'EditGridWrapper',
    'ModelList', 'DrillDownWrapper',
    # What an action's on_click receives, one per place it can sit in
    'FormActionEventArguments', 'GridActionEventArguments', 'DrillDownActionEventArguments',
    # Chrome styling and texts
    'ChromeStyle', 'get_chrome_style', 'set_chrome_style',
    'FieldStyle', 'get_field_style', 'set_field_style',
    'ChromeText', 'get_chrome_text', 'set_chrome_text',
    # Data adapters
    'ItemAdapter', 'CollectionAdapter', 'ReloadableAdapter', 'ReactiveAdapter',
    'BoundItem', 'BoundFieldAdapter', 'ListAdapter', 'JsonAdapter', 'JsonListAdapter',
    'JsonDirectoryAdapter', 'DirectoryAdapter', 'FileEntry', 'FilteredAdapter', 'SqlModelAdapter',
    'lenient_model_load', 'lenient_list_load',
    # Errors
    'ConflictError', 'StorageError',
]

log = logging.getLogger('niceview')
log.addHandler(logging.NullHandler())


def Field(**kwargs: Unpack[_FieldInfoInputs]) -> FieldInfo:
    """
    Create FieldInfo instance with the provided keyword arguments.
    This is a convenience function to create fields for forms and tables.
    """
    return FieldInfo(**kwargs)


def __getattr__(name: str) -> Any:
    # SqlModelAdapter needs the optional 'sqlmodel' package; resolve it lazily so
    # that importing niceview never requires it. dataadapter raises a helpful
    # ImportError if sqlmodel is missing.
    if name == 'SqlModelAdapter':
        from niceview import dataadapter
        return dataadapter.SqlModelAdapter
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
