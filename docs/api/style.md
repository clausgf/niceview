Styling and texts
=================

Three cascades: the chrome around a component, the fields inside it, and every string niceview
says out loud. [Concepts](../CONCEPT.md) explains how they fit together,
[Components](../components.md#chrome-styling) how to use them.

Chrome
------

::: niceview.style
    options:
      members:
        - ChromeStyle
        - get_chrome_style
        - set_chrome_style
        - Place
        - NotifyKind
        - NotifyPosition

Fields
------

::: niceview.style.FieldStyle

::: niceview.style.get_field_style

::: niceview.style.set_field_style

Texts
-----

::: niceview.text.ChromeText

::: niceview.text.TextValue

::: niceview.text.text_of

::: niceview.text.get_chrome_text

::: niceview.text.set_chrome_text

Building blocks
---------------

What the wrappers are made of. An application rarely calls these — they are here because a
custom wrapper that wants to look like niceview's own has to.

::: niceview.style
    options:
      heading_level: 3
      show_root_heading: false
      show_root_toc_entry: false
      members:
        - chrome_row
        - chrome_title
        - chrome_buttons
        - chrome_button
        - chrome_dialog
        - chrome_dialog_title
        - chrome_dialog_buttons
        - chrome_notify

Dialogs
-------

::: niceview.util
    options:
      heading_level: 3
      show_root_heading: false
      show_root_toc_entry: false
