"""
One documentation page per example, generated at build time (mkdocs-gen-files).

Each numbered example already explains itself: its module docstring is Markdown, and the app
prints it on its own first page with `ui.markdown(__doc__)`. That text is the page here too, so
there is exactly one place to write it — the example — and no copy that can drift.

The screenshot beside it is *not* generated here: it is committed under docs/img/examples/ and
refreshed with `uv run python docs/screenshots/capture_examples.py` when an example's UI
changes. Building the documentation must not need a browser.

The docstrings are read with `ast`, never imported: importing an example would start a NiceGUI
server in the middle of the build.
"""
import ast
import re
from pathlib import Path

import mkdocs_gen_files

REPO_BLOB = 'https://github.com/clausgf/niceview/blob/main/examples/'
EXAMPLES = Path('examples')
SHOTS = Path('docs/img/examples')

ROUTE_LINK = re.compile(r'(?<!!)\[([^\]]+)\]\(/[^)]*\)')
"""A link to a path at the root: in the running example that is one of its own routes and a
live link, on this site it is a page that does not exist."""


def _routes_to_code(body: str) -> str:
    """Keep such a link's label, drop its destination — a route is code here, not a link."""
    return ROUTE_LINK.sub(lambda m: m[1] if '`' in m[1] else f'`{m[1]}`', body)


def _title_and_body(docstring: str, fallback: str) -> tuple[str, str]:
    """
    Split '# ModelForm — Actions\n\nprose…' into its heading and the rest. An example without a
    leading heading keeps its whole docstring as the body and is titled after its file.
    """
    lines = docstring.strip().splitlines()
    if lines and lines[0].startswith('# '):
        return lines[0][2:].strip(), '\n'.join(lines[1:]).strip()
    return fallback, docstring.strip()


def _number_and_name(stem: str) -> tuple[str, str]:
    """'18_form_actions' -> ('18', 'form actions')"""
    number, _, rest = stem.partition('_')
    return number, rest.replace('_', ' ')


summary = ['* [Examples](index.md)\n']
cards = []

for path in sorted(EXAMPLES.glob('[0-9]*.py')):
    source = path.read_text()
    number, name = _number_and_name(path.stem)
    title, body = _title_and_body(ast.get_docstring(ast.parse(source)) or '', name.title())
    body = _routes_to_code(body)
    page = f'examples/{path.stem}.md'

    out = [f'{title}\n{"=" * len(title)}\n']
    out.append(f'[:material-file-code: `examples/{path.name}`]({REPO_BLOB}{path.name}) · run it with '
               f'`uv run python examples/{path.name}`\n')

    shot = SHOTS / f'{path.stem}.png'
    if shot.exists():
        # The picture shows the running app without its own docstring — the text below is that
        # docstring, and printing it twice would be the same paragraph in two typefaces.
        out.append(f'![{title}](../img/examples/{path.stem}.png)\n')

    if body:
        out.append(body + '\n')

    out.append('??? example "Source"\n')
    out.append('    ```python\n' + '\n'.join('    ' + line for line in source.splitlines()) + '\n    ```\n')

    with mkdocs_gen_files.open(page, 'w') as f:
        f.write('\n'.join(out))
    mkdocs_gen_files.set_edit_path(page, f'../examples/{path.name}')

    summary.append(f'* [{number} — {title}]({path.stem}.md)\n')
    cards.append((number, title, path.stem, body.strip().splitlines()[0] if body.strip() else ''))

index = ['Examples\n========\n',
         'Every example is one runnable file: `uv run python examples/01_form_basic.py` starts a\n'
         'NiceGUI app that explains itself on its own first page. The pages here show the same\n'
         'text, a screenshot of what it looks like, and the source.\n',
         '| # | Example | Shows |', '|---|---|---|']
for number, title, stem, lead in cards:
    index.append(f'| {number} | [{title}]({stem}.md) | {lead} |')

with mkdocs_gen_files.open('examples/index.md', 'w') as f:
    f.write('\n'.join(index) + '\n')

# The nav for the section, read by mkdocs-literate-nav. It is a table of contents, not a page:
# the front matter keeps it out of the search index, where it would be a hit that leads to a
# list of links the navigation already shows.
with mkdocs_gen_files.open('examples/SUMMARY.md', 'w') as f:
    f.write('---\nsearch:\n  exclude: true\n---\n\n')
    f.writelines(summary)
