NiceView
========

NiceView tries to simplify [NiceGUI](https://nicegui.io) programming by deriving forms and tables from Pydantic models. Inspiration was gatherd from
- [MagicGUI](https://magicgui.readthedocs.io/)
- [NiceCRUD](https://github.com/zauberzeug/nicegui/tree/main/examples/nicecrud)
- ... and the great [Django](https://docs.djangoproject.com/) ORM integration

NiceView is intended as an adapter layer between NiceGUI elements (widgets) and your application. Based on a pydantic model of your data, the adapters configure the elements. This is used to create forms and tables.

UI Elements and data types
--------------------------

- `value` is the value
- on_change callback

Element     | change cb | model data type | NiceGUI data type
------------+-----------+-----------------+--------------
ui.toggle   | on_change |                 | list ['value1', ...] or dictionary {'value1':'label1', ...}
ui.radio    | on_change |                 | list ['value1', ...] or dictionary {'value1':'label1', ...}
ui.radio    | on_change |                 | list ['value1', ...] or dictionary {'value1':'label1', ...}
ui.select   | on_change |                 | list ['value1', ...] or dictionary {'value1':'label1', ...}
ui.checkbox | on_change |                 | bool
ui.switch   | on_change |                 | bool
ui.slider   | on_change |                 | int?, min, max, step
ui.range    | on_change |                 | value={'min': 20, 'max': 80}, min, max, step
ui.input    | on('blur')|                 | .... validation: dictionary of validation rules: error message & lambda
ui.textarea | on('blur')|                 | .... validation: dictionary of validation rules: error message & lambda
ui.number   | on('blur')|                 | .... validation: dictionary of validation rules: error message & lambda
ui.color_input|on('blur')|                | color string like '#000000'
ui.color_picker|on('blur')|                | color string like '#000000'
ui.color_picker|on_change|                | color string like '#000000'
ui.date     | on_change |                 | string formatted according to mask parameter, default 'YYYY-MM-DD'
ui.time     | on_change |                 | string formatted according to mask parameter, default 'HH:mm'


TODO
----
- change handling: Check whether 'blur' event handles relevant edge cases. 'blur' shall trigger pydantic validation on Field and BaseModel level. Validation error shall be reflected in the form. Emit a change event. This shall be suited for saving changes. Outside on_change only for valid states.
- how do we detect leaving the form? how do we guarantee a valid model state when leaving the form?
- support validation: use pydantic validators for validation & render nice error messages - is Quasar's QForm somehow helpful?
- life cycle is not clear. when are nicegui elements instantiated, when active, when deleted?
- when is the polling implementation of binding active? problem?
- support binding in tables?
- when shall we save data? does an apply button make sense? make this button active?
- fact: QInput, QFile and QSelect inherit from QField which "provides labels, hints, errors, validation, and comes in a variety of styles and colors"
- make everything work for dataclasses in addition to pydantic models
