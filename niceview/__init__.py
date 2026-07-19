import logging
from typing import Any, Unpack

from niceview.fieldinfo import _FieldInfoInputs, FieldInfo
from niceview.dataadapter import (
    BoundItem,
    CollectionAdapter,
    ConflictError,
    DirectoryAdapter,
    FileEntry,
    FilteredAdapter,
    ItemAdapter,
    JsonAdapter,
    JsonListAdapter,
    ListAdapter,
    ReactiveAdapter,
    ReloadableAdapter,
    StorageError,
    lenient_list_load,
    lenient_model_load,
)
from niceview.modelform import CheckboxGroup, ModelForm
from niceview.modelgrid import ModelGrid, ModelGridInlineEdit
from niceview.editwrapper import EditFormWrapper, EditGridWrapper
from niceview.modellist import ModelList
from niceview.drilldown import DrillDownWrapper

__all__ = [
    # Field customization
    'Field', 'FieldInfo',
    # UI components
    'ModelForm', 'CheckboxGroup',
    'ModelGrid', 'ModelGridInlineEdit',
    'EditFormWrapper', 'EditGridWrapper',
    'ModelList', 'DrillDownWrapper',
    # Data adapters
    'ItemAdapter', 'CollectionAdapter', 'ReloadableAdapter', 'ReactiveAdapter',
    'BoundItem', 'ListAdapter', 'JsonAdapter', 'JsonListAdapter',
    'DirectoryAdapter', 'FileEntry', 'FilteredAdapter', 'SqlModelAdapter',
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
