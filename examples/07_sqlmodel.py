"""
# SqlModelAdapter

Advanced example: `SqlModelAdapter` connects `ModelForm` and `ModelGrid`
to a SQLite database via SQLModel / SQLAlchemy.

Features shown:
- Optimistic locking via `updated_at` field (built into `SqlModelAdapter`)
- `EditGridWrapper` over a full SQL table
- `EditFormWrapper` with Save / Refresh for editing a single record
- SQLModel relationship rendered as `ui.select` (via `repositories=`)

**Try the optimistic locking:** open [/books/1](/books/1) in two browser tabs,
edit and save in the first, then save in the second — the second save is
rejected with a conflict notification (`ConflictError`), because its
`updated_at` no longer matches the database.

The database is re-created on every run.

Pages: [`/` → Authors grid](/), [`/authors/{id}` → Edit Author](/authors/1),
[`/books` → Books grid](/books), [`/books/{id}` → Edit Book](/books/1)
"""

import os
import datetime
import logging
from typing import Annotated
import sqlmodel
from nicegui import ui

import niceview
from niceview import SqlModelAdapter, EditFormWrapper, EditGridWrapper

log = logging.getLogger('niceview-example')
logging.getLogger('niceview').setLevel(logging.DEBUG)


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


class Author(sqlmodel.SQLModel, table=True):
    id: Annotated[int | None, sqlmodel.Field(default=None, primary_key=True), niceview.Field(hidden=True)]
    name: str = sqlmodel.Field(min_length=2, max_length=40, title='Name')
    email: str = sqlmodel.Field(max_length=100, title='Email')
    books: list['Book'] = sqlmodel.Relationship(back_populates='author')
    updated_at: Annotated[datetime.datetime, sqlmodel.Field(default_factory=_now), niceview.Field(hidden=True)]

    class Meta:
        # provide field order because SQLModel doesn't preserve declaration order
        field_order = ['name', 'email', 'books']

    def __str__(self):
        return self.name


class Book(sqlmodel.SQLModel, table=True):
    id: Annotated[int | None, sqlmodel.Field(default=None, primary_key=True), niceview.Field(hidden=True)]
    title: str = sqlmodel.Field(min_length=2, max_length=100, title='Title')
    published: datetime.date = sqlmodel.Field(default_factory=datetime.date.today, title='Published')
    author_id: Annotated[int, sqlmodel.Field(foreign_key='author.id'), niceview.Field(hidden=True)]
    author: Author = sqlmodel.Relationship(back_populates='books')
    updated_at: Annotated[datetime.datetime, sqlmodel.Field(default_factory=_now), niceview.Field(hidden=True)]

    class Meta:
        field_infos = {
            'author': niceview.Field(label='Author', tooltip='Select the author of this book'),
        }
        field_order = ['title', 'author']  # partial field order, with remaining field at the end

    def __str__(self):
        return self.title


@ui.page('/')
def authors_page():
    ui.markdown(__doc__ or '')
    ui.separator()
    ui.label('Authors').classes('text-h5')
    authors = SqlModelAdapter(Author, engine)
    EditGridWrapper.from_adapter(Author, authors, title='Authors').render()
    ui.button('→ Books', on_click=lambda: ui.navigate.to('/books')).props('flat')


@ui.page('/authors/{author_id}')
def author_edit_page(author_id: int):
    authors = SqlModelAdapter(Author, engine)
    with ui.card().classes('w-full max-w-lg'):
        EditFormWrapper.from_adapter(Author, authors, str(author_id), title='Edit Author').render()
    ui.button('← Back', on_click=lambda: ui.navigate.to('/')).props('flat')


@ui.page('/books')
def books_page():
    books = SqlModelAdapter(Book, engine)
    authors = SqlModelAdapter(Author, engine)
    ui.label('Books').classes('text-h5')
    wrapper = EditGridWrapper.from_adapter(Book, books, title='Books').render()
    wrapper.with_repositories({Author: authors})
    ui.button('← Authors', on_click=lambda: ui.navigate.to('/')).props('flat')


@ui.page('/books/{book_id}')
def book_edit_page(book_id: int):
    books = SqlModelAdapter(Book, engine)
    authors = SqlModelAdapter(Author, engine)
    with ui.card().classes('w-full max-w-lg'):
        EditFormWrapper.from_adapter(Book, books, str(book_id), title='Edit Book',
                                     repositories={Author: authors}).render()
    ui.button('← Back', on_click=lambda: ui.navigate.to('/books')).props('flat')


logging.basicConfig(level=logging.INFO)

DB_PATH = 'example_sqlmodel.db'
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

engine = sqlmodel.create_engine(f'sqlite:///{DB_PATH}')
sqlmodel.SQLModel.metadata.create_all(engine)

with sqlmodel.Session(engine) as session:
    author1 = Author(name='Jane Doe', email='jane@example.com')
    session.add(author1)
    session.commit()
    session.refresh(author1)
    session.add(Book(title="Jane's First Book", author=author1))  # type: ignore
    session.add(Book(title="Jane's Second Book", author=author1, published=datetime.date(2023, 6, 1)))  # type: ignore
    author2 = Author(name='John Smith', email='john@example.com')
    session.add(author2)
    session.commit()
    session.refresh(author2)
    session.add(Book(title="John's Only Book", author=author2))  # type: ignore
    session.commit()

ui.run(title='07 — SQLModel')
