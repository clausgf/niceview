"""
# DrillDownWrapper — Directory of Files (with Rename)

DrillDownWrapper's two first-class use cases: a JSON list inside one file (see
09_drilldown.py) and, here, one file per item in a directory. `DirectoryAdapter`
models the directory — each item is just filename metadata (`FileEntry`), not the
parsed content. The actual note text lives in its own `JsonAdapter` per file,
opened lazily inside `render_detail`.

Renaming is not a wrapper feature — it's just a "Name" input wired to
`DirectoryAdapter.rename()`, reporting the new key back via the `set_key`
callback so DrillDownWrapper's navigation state (title, Back target) stays in
sync. Add is overridden via `on_add` too, since `DirectoryAdapter.create()`
picks its own default name ("untitled-01", "untitled-02", ...) instead of
taking a fully-formed item like the default Add flow expects.
"""
# Allows running without prior install. With uv: `uv run python examples/<file>.py`.
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pydantic
from nicegui import ui

from niceview.dataadapter import DirectoryAdapter, FileEntry, JsonAdapter
from niceview.form import ModelForm
from niceview.modellist import DrillDownWrapper


class Note(pydantic.BaseModel):
    text: str = pydantic.Field(default='', title='Text')


NOTES_DIR = Path('./example_notes')
NOTES_DIR.mkdir(exist_ok=True)

directory = DirectoryAdapter(NOTES_DIR, default_content=Note().model_dump_json())


def render_note_detail(adapter: DirectoryAdapter, key: str, set_key) -> None:
    def do_rename() -> None:
        try:
            set_key(adapter.rename(key, name_input.value))
        except ValueError as e:
            ui.notify(str(e), color='negative')

    name_input = ui.input('Name', value=key).classes('w-full').props('outlined dense')
    name_input.on('blur', do_rename)

    note_path = NOTES_DIR / f'{key}.json'
    form = ModelForm.from_adapter(Note, JsonAdapter(Note, note_path), autosave=True)
    form.render_field('text', widget_type='ui.textarea').classes('w-full').props('outlined')
    form.render_nonfield_errors()


@ui.page('/')
def page():
    ui.markdown(__doc__ or '')
    ui.separator()

    def handle_add() -> None:
        entry = directory.create()
        wrapper.open(entry.name)

    with ui.card().classes('w-full max-w-2xl'):
        wrapper = DrillDownWrapper.from_adapter(
            FileEntry, directory,
            list_title='Notes',
            item_title_field='name',
            item_subtitle_fields=[],
            on_add=handle_add,
            render_detail=render_note_detail,
        )
        wrapper.render()


ui.run(title='13 — Directory Drill-Down')
