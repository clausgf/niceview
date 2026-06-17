import datetime
import logging
import os
from typing import Annotated
import sqlmodel
from nicegui import ui

import niceview

log = logging.getLogger('niceview-example')
from niceview.modeledit import EditFormWrapper, EditGridWrapper
from niceview.modelform import ModelForm
from niceview.modelgrid import ModelGridInlineEdit, ModelGrid
from niceview.dataadapter import SqlModelAdapter


def _now_factory():
    return datetime.datetime.now(datetime.timezone.utc)

class Author(sqlmodel.SQLModel, table=True):
    id: Annotated[int | None, sqlmodel.Field(default=None, primary_key=True), niceview.Field(hidden=True)]
    name: str = sqlmodel.Field(max_length=10, nullable=False, title='Author Name', description='The name of the author')
    email: str = sqlmodel.Field(max_length=100, nullable=False)
    books: list['Book'] = sqlmodel.Relationship(back_populates='author')

    created_at: Annotated[datetime.datetime, sqlmodel.Field(default_factory=_now_factory, title='Created At'), niceview.Field(hidden=True)]
    updated_at: Annotated[datetime.datetime, sqlmodel.Field(default_factory=_now_factory, title='Last Updated'), niceview.Field(hidden=True)]

    def __str__(self) -> str:
        return self.name


class Book(sqlmodel.SQLModel, table=True):
    id: Annotated[int | None, sqlmodel.Field(default=None, primary_key=True), niceview.Field(hidden=True)]
    title: str = sqlmodel.Field(max_length=100, nullable=False)
    published_date: datetime.date = sqlmodel.Field(default_factory=datetime.date.today, nullable=False)
    author_id: Annotated[int, sqlmodel.Field(foreign_key='author.id', nullable=False), niceview.Field(hidden=True)]
    author: Author = sqlmodel.Relationship(back_populates='books')

    created_at: Annotated[datetime.datetime, sqlmodel.Field(default_factory=_now_factory, title='Created At'), niceview.Field(hidden=True)]
    updated_at: Annotated[datetime.datetime, sqlmodel.Field(default_factory=_now_factory, title='Last Updated'), niceview.Field(hidden=True)]

    def __str__(self) -> str:
        return f'{self.title}' # f'{self.title} by {self.author.name}' if self.author else self.title
    
    class Meta:
        title = 'Book'
        description = 'A book written by an author'
        field_info = {
            'title': niceview.Field(label='Title', tooltip='The title of the book'),
            'published_date': niceview.Field(label='Published Date', tooltip='The date when the book was published'),
            'author': niceview.Field(label='Author', tooltip='The author of the book'),
        }


def save_author(author: Author):
    log.info(f'Saving author: {author!r}')
    with sqlmodel.Session(engine) as session:
        session.merge(author)
        session.commit()


def get_author(author_id: int) -> Author | None:
    with sqlmodel.Session(engine) as session:
        autor = session.get(Author, author_id)
        if autor:
            return autor.model_validate(autor)
        return None


@ui.page('/authors/{author_id}')
def author_id_page(author_id: int):
    """Edit an author by ID.
    Realization: The author details are loaded from the database, and changes are
    saved automatically. This is realized by hand using the ModelForm."""

    def on_author_changed(event):
        log.info(f'Author changed: {event.field_name=} {event.old_value=} {event.new_value=}')
        save_author(author)

    with ui.row():
        ui.label('Edit Author').classes('text-h3')

    # get the author by id
    author = get_author(author_id=author_id)
    with ui.card().classes('w-full'):
        if not author:
            ui.label(f'Author with ID {author_id} not found.').classes('text-red-500')
        else:
            form = ModelForm.from_item(author, classes='w-full', title='Author Form', description='Edit the author details. Changes will be saved automatically.')
            form.render()
            form.on_change(on_author_changed)


@ui.page('/books/{book_id}')
def book_id_page(book_id: int):
    """Edit a book by ID.
    Realization: The book details are handled by an EditFormWrapper, which
    handles database access for you."""
    books = SqlModelAdapter(item_type=Book, engine=engine)
    with ui.card().classes('w-full'):
        form = ModelForm.from_adapter(Book, books, book_id, title='Book Form', description='Edit the book details.')
        form.set_model_repositories({Author.__name__: SqlModelAdapter(item_type=Author, engine=engine)})
        form_edit = EditFormWrapper(form)
        form_edit.render()


@ui.page('/authors')
def author_page():
    with ui.row():
        ui.label('Authors ModelGrid Examples').classes('text-h5')

    authors = SqlModelAdapter(item_type=Author, engine=engine)
    with ui.card().classes('w-full'):
        ui.label('Authors readonly ModelGrid').classes('text-h6')
        grid_static = ModelGrid(Author, authors, classes='w-full')
        grid_static.render()
        #selection change: e=ValueChangeEventArguments(sender=..., client=..., value={'__ui_row_key': 0, 'name': 'Jane Doe', 'email': 'jane.doe@example.com'})
        #grid_static.on_select(lambda e: print(f'selection change: {e=}'))
    with ui.card().classes('w-full'):
        ui.label('Authors Inline-Editable ModelGrid').classes('text-h6')
        grid_inline_edit = ModelGridInlineEdit(Author, authors, classes='w-full')
        grid_inline_edit.render()
        grid_inline_edit.on_change(lambda event: log.info(f'grid_edit_inline Edit changed: {event.row_key=} {event.item=}'))
    with ui.card().classes('w-full'):
        ui.label('Authors ModelGrid in EditGridWrapper with auto-generated title').classes('text-h6')
        grid_edit = EditGridWrapper(ModelGrid(Author, authors))
        grid_edit.render()
        #grid_edit_refresh.on_change(lambda event: print(f'grid_edit_refresh Edit Refresh changed: {event.row_index=} {event.item=}'))
    with ui.card().classes('w-full'):
        ui.label('Authors Inline-Editable ModelGrid in EditGridWrapper with Button text and title').classes('text-h6')
        grid_edit2 = EditGridWrapper(
            ModelGridInlineEdit(Author, authors),
            title='Authors', 
            add_button='Add', delete_button='Delete', refresh_button='Refresh')
        grid_edit2.render()


@ui.page('/books')
def book_page():
    with ui.row():
        ui.label('Books ModelGrid Examples').classes('text-h3')

    books = SqlModelAdapter(item_type=Book, engine=engine)
    with ui.card().classes('w-full'):
        book_grid = EditGridWrapper(
            ModelGrid(Book, books),
            title='Books',
        )
        book_grid.render()


@ui.page('/')
def main_page():
    with ui.row():
        ui.label('Welcome to the SQLModel Example with NiceGUI!').classes('text-h3')
    with ui.row():
        ui.button('Edit Author Form', on_click=lambda: ui.navigate.to('/authors/1')).classes('q-mr-sm')
        ui.button('Edit Book Form', on_click=lambda: ui.navigate.to('/books/1')).classes('q-mr-sm')
        ui.button('Authors ModelGrid', on_click=lambda: ui.navigate.to('/authors')).classes('q-mr-sm')
        ui.button('Books ModelGrid', on_click=lambda: ui.navigate.to('/books')).classes('q-mr-sm')


logging.basicConfig(level=logging.DEBUG)

# remove the database file if it exists
if os.path.exists("example.db"):
    os.remove("example.db")

# Create the database and tables
engine = sqlmodel.create_engine("sqlite:///example.db")
sqlmodel.SQLModel.metadata.create_all(engine)

# Populate the database with some initial data
with sqlmodel.Session(engine) as session:
    if not session.exec(sqlmodel.select(Author)).first():
        author = Author(name="Jane Doe", email="jane.doe@example.com")
        session.add(author)
        session.commit()
        session.refresh(author)
        print(f"Created author: {author.id}, {author.name}, {author.email}")

        book = Book(author=author, title="Jane's First Book") # type: ignore
        session.add(book)
        session.commit()
        session.refresh(book)
        print(f"Created book: {book.id}, {book.title}, {book.published_date}, Author ID: {book.author.id} {book.author!r}")

ui.run()
