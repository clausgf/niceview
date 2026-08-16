Fields and widgets
==================

What a field *is* (`FieldInfo`, built by `niceview.Field()`), how a model's fields are resolved
into a set of them (`Fields`), how a layout arranges them — and the model-free half, which
renders a single widget from a single `FieldInfo`. See [Field types](../field-types.md) for the
type→widget mapping.

Field metadata
--------------

::: niceview.Field

::: niceview.fieldinfo.FieldInfo

::: niceview.fields.Fields

Layout
------

The tree a layout notation parses into. `'@name'` becomes a `LayoutAction`, a field name a
`LayoutField`, a nested list a `LayoutGroup` — see
[Components](../components.md#layout) for the notation itself.

::: niceview.fields.LayoutGroup

::: niceview.fields.LayoutField

::: niceview.fields.LayoutAction

::: niceview.fields.parse_layout

::: niceview.fields.layout_field_names

::: niceview.fields.layout_action_names

Widgets without a model
-----------------------

::: niceview.widgets.render_field

::: niceview.widgets.field_value

::: niceview.widgets.to_widget_value

::: niceview.widgets.CheckboxGroup

::: niceview.widgets.reserves_bottom_space
