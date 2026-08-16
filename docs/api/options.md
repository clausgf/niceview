Keyword options
===============

Every component takes its configuration as keyword arguments, and every set of them is declared
as a `TypedDict` that the factory methods unpack (`**kwargs: Unpack[_ModelFormOptionInputs]`).
That is what makes an unknown keyword a `TypeError` and a known one an editor completion — and
it is where each option's own description lives, which is why these otherwise private types are
documented here.

The names begin with an underscore because they are not meant to be imported or subclassed. Read
them as the option list of the component they belong to.

!!! tip "Two sources for the same option"

    Most of these can also be set on the model's `Meta` class, where the answer belongs to the
    model rather than to one view of it — a keyword argument then wins over `Meta`. See
    [Field types](../field-types.md).

Form
----

::: niceview.modelform._ModelFormOptionInputs
    options:
      filters: []
      show_bases: false

::: niceview.editwrapper._EditFormWrapperInputs
    options:
      filters: []
      show_bases: false

Grid
----

::: niceview.modelgrid._ModelGridOptionInputs
    options:
      filters: []
      show_bases: false

::: niceview.editwrapper._EditGridWrapperInputs
    options:
      filters: []
      show_bases: false

List and drill-down
-------------------

::: niceview.modellist._ModelListOptionInputs
    options:
      filters: []
      show_bases: false

::: niceview.drilldown._DrillDownWrapperOptionInputs
    options:
      filters: []
      show_bases: false

Field
-----

The arguments of `niceview.Field()`, which builds a
[`FieldInfo`](fields.md#niceview.fieldinfo.FieldInfo).

::: niceview.fieldinfo._FieldInfoInputs
    options:
      filters: []
      show_bases: false
