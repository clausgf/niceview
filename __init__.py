import logging
from typing import Unpack
from niceview.fieldinfo import _FieldInfoInputs, FieldInfo

log = logging.getLogger('niceview')
log.addHandler(logging.NullHandler())


def Field(**kwargs: Unpack[_FieldInfoInputs]) -> FieldInfo:
    """
    Create FieldInfo instance with the provided keyword arguments.
    This is a convenience function to create fields for forms and tables.
    """
    return FieldInfo(**kwargs)

