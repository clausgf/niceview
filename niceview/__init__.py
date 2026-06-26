import logging
from typing import Unpack
from niceview.fieldinfo import _FieldInfoInputs, FieldInfo
from niceview.dataadapter import BoundItem
from niceview.modellist import ModelList, DrillDownWrapper

__all__ = ['Field', 'FieldInfo', 'BoundItem', 'ModelList', 'DrillDownWrapper']

log = logging.getLogger('niceview')
log.addHandler(logging.NullHandler())


def Field(**kwargs: Unpack[_FieldInfoInputs]) -> FieldInfo:
    """
    Create FieldInfo instance with the provided keyword arguments.
    This is a convenience function to create fields for forms and tables.
    """
    return FieldInfo(**kwargs)

