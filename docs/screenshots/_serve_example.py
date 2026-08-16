"""
Run one numbered example headlessly on a given port. Used by capture_examples.py as a
subprocess; not useful on its own.

The examples end in a bare `ui.run(title=...)`, which is exactly right when a human starts
one and wrong for a screenshot: it would pick the default port, open a browser and start the
reload watcher (whose child process a `terminate()` on the parent would leave behind). Those
three arguments are overridden here rather than in the examples, which stay the plain scripts
a reader is meant to copy.

Usage:
    python _serve_example.py ../../examples/01_form_basic.py 8138
"""
import runpy
import sys

from nicegui import ui

_run = ui.run


def _run_headless(**kwargs: object) -> None:
    _run(**{**kwargs, 'reload': False, 'show': False, 'port': int(sys.argv[2])})


ui.run = _run_headless  # type: ignore[assignment]
runpy.run_path(sys.argv[1], run_name='__main__')
