"""
mkdocstrings (docs/api/*.md) documents a class field by field, but only picks up a description
for a field that carries an attribute docstring -- a string literal placed directly after its
annotation. A field without one renders in the generated docs with no description at all, which
is easy to miss since niceview itself never complains. This test holds that line: every field of
every class below -- the kwargs/option classes, FieldInfo, the chrome style/text classes, and the
*EventArguments a handler receives -- must carry one.
"""
import ast
import inspect

import pytest

from niceview.drilldown import (DrillDownActionEventArguments, DrillDownListActionEventArguments,
                                _DrillDownWrapperOptionInputs)
from niceview.editwrapper import (GridActionEventArguments, _EditFormWrapperFactoryInputs,
                                  _EditFormWrapperInputs, _EditGridWrapperFactoryInputs,
                                  _EditGridWrapperInputs)
from niceview.fieldinfo import FieldInfo, _FieldInfoInputs
from niceview.modelform import (FieldChangeEventArguments, FormActionEventArguments,
                                _ModelFormOptionInputs)
from niceview.modelgrid import (TableItemEventArguments, TableItemFieldEventArguments,
                                TableItemSelectEventArguments,
                                _InlineEditableModelGridOptionInputs, _ModelGridOptionInputs)
from niceview.modellist import ListItemSelectEventArguments, _ModelListOptionInputs
from niceview.style import ChromeStyle, FieldStyle
from niceview.text import ChromeText

# The classes rendered field by field in docs/api/*.md.
OPTION_CLASSES = [
    _ModelFormOptionInputs,
    _EditFormWrapperInputs,
    _EditFormWrapperFactoryInputs,
    _ModelGridOptionInputs,
    _InlineEditableModelGridOptionInputs,
    _EditGridWrapperInputs,
    _EditGridWrapperFactoryInputs,
    _ModelListOptionInputs,
    _DrillDownWrapperOptionInputs,
    _FieldInfoInputs,
    FieldInfo,
    ChromeStyle,
    FieldStyle,
    ChromeText,
    GridActionEventArguments,
    DrillDownActionEventArguments,
    DrillDownListActionEventArguments,
    FormActionEventArguments,
    FieldChangeEventArguments,
    TableItemEventArguments,
    TableItemSelectEventArguments,
    TableItemFieldEventArguments,
    ListItemSelectEventArguments,
]


def _undocumented_fields(cls: type) -> list[str]:
    """Field names declared directly in cls's body with no attribute docstring right after them."""
    body = ast.parse(inspect.getsource(cls)).body[0].body  # type: ignore[attr-defined]
    missing = []
    for i, stmt in enumerate(body):
        if not (isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)):
            continue
        has_doc = (i + 1 < len(body) and isinstance(body[i + 1], ast.Expr)
                   and isinstance(body[i + 1].value, ast.Constant)
                   and isinstance(body[i + 1].value.value, str))
        if not has_doc:
            missing.append(stmt.target.id)
    return missing


@pytest.mark.parametrize('cls', OPTION_CLASSES, ids=lambda c: c.__qualname__)
def test_every_field_has_a_docstring(cls: type) -> None:
    missing = _undocumented_fields(cls)
    assert not missing, (
        f"{cls.__qualname__} has no attribute docstring for {missing} -- mkdocstrings renders "
        f"these fields with no description in the generated docs. Add one directly below the "
        f"field's annotation."
    )
