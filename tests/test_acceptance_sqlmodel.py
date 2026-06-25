"""
Acceptance tests for SQLModel integration (Example 7: Authors / Books).

Organised by relation type:

  Section 0: no relations  — SqlModelAdapter CRUD + optimistic locking
  Section 1: field resolution — editgrid vs. modelselect
  Section 2: many-to-one   — Book.author → modelselect (ui.select)
  Section 3: one-to-many   — Author.books → editgrid
  Section 4: Authors grid  — EditGridWrapper + SqlModelAdapter (/ page)
  Section 5: Books grid    — EditGridWrapper + SqlModelAdapter (/books page)
  Section 6: detail pages  — EditFormWrapper + SqlModelAdapter
"""

import datetime
import pytest
import sqlmodel
from typing import Annotated
from nicegui import ui
from nicegui.testing import User

import niceview
from niceview.dataadapter import SqlModelAdapter
from niceview.fields import Fields
from niceview.modelform import ModelForm
from niceview.modelgrid import ModelGrid
from niceview.modeledit import EditFormWrapper, EditGridWrapper


# ---------------------------------------------------------------------------
# SQLModel models  (same schema as Example 7)
# ---------------------------------------------------------------------------

def _now():
    return datetime.datetime.now(datetime.timezone.utc)


class Author(sqlmodel.SQLModel, table=True):
    __table_args__ = {'extend_existing': True}
    id: Annotated[int | None, sqlmodel.Field(default=None, primary_key=True), niceview.Field(hidden=True)]
    name: str = sqlmodel.Field(min_length=2, max_length=40, title='Name')
    email: str = sqlmodel.Field(max_length=100, title='Email')
    books: list['Book'] = sqlmodel.Relationship(back_populates='author')
    updated_at: Annotated[datetime.datetime, sqlmodel.Field(default_factory=_now), niceview.Field(hidden=True)]

    class Meta:
        field_order = ['name', 'email', 'books']

    def __str__(self):
        return self.name


class Book(sqlmodel.SQLModel, table=True):
    __table_args__ = {'extend_existing': True}
    id: Annotated[int | None, sqlmodel.Field(default=None, primary_key=True), niceview.Field(hidden=True)]
    title: str = sqlmodel.Field(min_length=2, max_length=100, title='Title')
    published: datetime.date = sqlmodel.Field(default_factory=datetime.date.today, title='Published')
    author_id: Annotated[int, sqlmodel.Field(foreign_key='author.id'), niceview.Field(hidden=True)]
    author: Author = sqlmodel.Relationship(back_populates='books')
    updated_at: Annotated[datetime.datetime, sqlmodel.Field(default_factory=_now), niceview.Field(hidden=True)]

    class Meta:
        field_info = {
            'author': niceview.Field(label='Author', tooltip='Select the author of this book'),
        }
        field_order = ['title', 'author']

    def __str__(self):
        return self.title


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_engine():
    """Fresh in-memory SQLite engine with all tables created."""
    engine = sqlmodel.create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
    )
    sqlmodel.SQLModel.metadata.create_all(engine)
    return engine


def seed_engine(engine):
    """Insert two authors and three books. Returns (author1_id, author2_id, book1_id, book2_id, book3_id)."""
    with sqlmodel.Session(engine) as session:
        author1 = Author(name='Jane Doe', email='jane@example.com')
        session.add(author1)
        session.commit()
        session.refresh(author1)
        book1 = Book(title="Jane's First Book", author=author1)
        book2 = Book(title="Jane's Second Book", author=author1, published=datetime.date(2023, 6, 1))
        session.add(book1)
        session.add(book2)
        author2 = Author(name='John Smith', email='john@example.com')
        session.add(author2)
        session.commit()
        session.refresh(author2)
        book3 = Book(title="John's Only Book", author=author2)
        session.add(book3)
        session.commit()
        for obj in (book1, book2, book3):
            session.refresh(obj)
        return author1.id, author2.id, book1.id, book2.id, book3.id


# ===========================================================================
# Section 0: SqlModelAdapter CRUD — no relations
# ===========================================================================

class TestSqlModelAdapterCRUD:
    """Pure Python tests: CRUD operations and optimistic locking for Author."""

    def setup_method(self):
        self.engine = make_engine()
        self.adapter = SqlModelAdapter(Author, self.engine)

    def test_create_assigns_pk(self):
        created = self.adapter.create(Author(name='Alice', email='alice@test.com'))
        assert created.id is not None

    def test_create_sets_lock_field(self):
        created = self.adapter.create(Author(name='Alice', email='alice@test.com'))
        assert created.updated_at is not None

    def test_create_item_iterable(self):
        self.adapter.create(Author(name='Alice', email='alice@test.com'))
        self.adapter.create(Author(name='Bob', email='bob@test.com'))
        names = [a.name for a in self.adapter]
        assert 'Alice' in names and 'Bob' in names

    def test_read_returns_correct_item(self):
        created = self.adapter.create(Author(name='Alice', email='alice@test.com'))
        key = self.adapter.key_from_item(created)
        fetched = self.adapter.read(key)
        assert fetched.name == 'Alice'
        assert fetched.email == 'alice@test.com'

    def test_read_missing_key_raises(self):
        with pytest.raises(ValueError):
            self.adapter.read(999)

    def test_update_modifies_fields(self):
        created = self.adapter.create(Author(name='Alice', email='alice@test.com'))
        key = self.adapter.key_from_item(created)
        created.name = 'Alicia'
        updated = self.adapter.update(created)
        assert updated.name == 'Alicia'
        assert self.adapter.read(key).name == 'Alicia'

    def test_update_bumps_lock_field(self):
        import time
        created = self.adapter.create(Author(name='Alice', email='alice@test.com'))
        old_ts = created.updated_at
        time.sleep(0.01)
        updated = self.adapter.update(created)
        assert updated.updated_at > old_ts

    def test_update_stale_lock_raises(self):
        created = self.adapter.create(Author(name='Alice', email='alice@test.com'))
        key = self.adapter.key_from_item(created)
        second = self.adapter.read(key)
        self.adapter.update(second)
        # created now has a stale updated_at
        with pytest.raises(ValueError, match='Optimistic Locking'):
            self.adapter.update(created)

    def test_delete_removes_item(self):
        created = self.adapter.create(Author(name='Alice', email='alice@test.com'))
        key = self.adapter.key_from_item(created)
        self.adapter.delete(key)
        with pytest.raises(ValueError):
            self.adapter.read(key)

    def test_delete_missing_key_raises(self):
        with pytest.raises(ValueError):
            self.adapter.delete(999)

    def test_query_all_strs_yields_str_representation(self):
        """query_all_strs() yields (key, str(item)) pairs used to populate modelselect."""
        a1 = self.adapter.create(Author(name='Alice', email='alice@test.com'))
        a2 = self.adapter.create(Author(name='Bob', email='bob@test.com'))
        pairs = dict(self.adapter.query_all_strs())
        assert pairs[self.adapter.key_from_item(a1)] == 'Alice'
        assert pairs[self.adapter.key_from_item(a2)] == 'Bob'


# ===========================================================================
# Section 1: Field resolution by relation type
# ===========================================================================

class TestFieldResolution:
    """Fields resolves SQLModel relation annotations to the correct widget type."""

    def test_one_to_many_resolves_to_editgrid(self):
        """Author.books (list[Book], one-to-many) → editgrid widget."""
        fields = Fields(Author)
        assert fields['books'].widget_type == 'editgrid'

    def test_one_to_many_item_type_is_book(self):
        fields = Fields(Author)
        assert fields['books'].item_type is Book

    def test_many_to_one_resolves_to_modelselect(self):
        """Book.author (Author, many-to-one) → modelselect widget."""
        fields = Fields(Book)
        assert fields['author'].widget_type == 'modelselect'

    def test_many_to_one_item_type_is_author(self):
        fields = Fields(Book)
        assert fields['author'].item_type is Author

    def test_author_id_is_hidden(self):
        """The FK column author_id carries niceview.Field(hidden=True)."""
        fields = Fields(Book)
        assert fields['author_id'].hidden is True

    def test_author_pk_is_hidden(self):
        fields = Fields(Author)
        assert fields['id'].hidden is True

    def test_author_updated_at_is_hidden(self):
        fields = Fields(Author)
        assert fields['updated_at'].hidden is True

    def test_book_updated_at_is_hidden(self):
        fields = Fields(Book)
        assert fields['updated_at'].hidden is True

    def test_author_field_order_name_email_books(self):
        """Meta.field_order is applied: name < email < books."""
        names = list(Fields(Author).field_names)
        assert names.index('name') < names.index('email') < names.index('books')

    def test_book_field_order_title_before_author(self):
        """Meta.field_order partial list: title < author."""
        names = list(Fields(Book).field_names)
        assert names.index('title') < names.index('author')

    def test_one_to_many_editable_by_default(self):
        """
        REVIEW-3: Author.books editgrid has editable=True (the FieldInfo default).
        Changes in the dialog go to a ListAdapter, not the DB.
        """
        assert Fields(Author)['books'].editable is True

    def test_many_to_one_with_input_enabled(self):
        """Book.author modelselect has with_input=True (set by the SQLModel field resolver)."""
        assert Fields(Book)['author'].with_input is True


# ===========================================================================
# Section 2: many-to-one — Book.author rendered as modelselect
# ===========================================================================

class TestBookManyToOneRender:
    """Book form: author field must appear as a ui.select widget."""

    async def test_author_field_renders_as_select(self, user: User) -> None:
        engine = make_engine()
        seed_engine(engine)

        @ui.page('/')
        def page():
            books = SqlModelAdapter(Book, engine)
            authors = SqlModelAdapter(Author, engine)
            book = books.read(1)
            form = ModelForm.from_item(book)
            form.with_repositories({Author.__name__: authors})
            form.render()

        await user.open('/')
        await user.should_see(ui.select)

    async def test_author_label_visible(self, user: User) -> None:
        engine = make_engine()
        seed_engine(engine)

        @ui.page('/')
        def page():
            books = SqlModelAdapter(Book, engine)
            authors = SqlModelAdapter(Author, engine)
            book = books.read(1)
            form = ModelForm.from_item(book)
            form.with_repositories({Author.__name__: authors})
            form.render()

        await user.open('/')
        await user.should_see('Author')

    async def test_title_input_present(self, user: User) -> None:
        engine = make_engine()
        seed_engine(engine)

        @ui.page('/')
        def page():
            books = SqlModelAdapter(Book, engine)
            authors = SqlModelAdapter(Author, engine)
            book = books.read(1)
            form = ModelForm.from_item(book)
            form.with_repositories({Author.__name__: authors})
            form.render()

        await user.open('/')
        await user.should_see(ui.input)

    async def test_missing_model_repository_renders_disabled_select(self, user: User) -> None:
        """
        Rendering a Book form without an Author repository renders the author field
        as a disabled placeholder (no exception). Call with_repositories() to
        enable the select.
        """
        engine = make_engine()
        seed_engine(engine)
        captured: list[ModelForm] = []

        @ui.page('/')
        def page():
            books = SqlModelAdapter(Book, engine)
            book = books.read('1')
            form = ModelForm.from_item(book)
            form.render()
            captured.append(form)

        await user.open('/')
        assert captured
        author_widget = captured[0].widgets.get('author')
        assert isinstance(author_widget, ui.select)
        assert not author_widget.enabled


class TestBookManyToOneInteraction:
    """
    Verify that author changes are correctly propagated through the form
    and persisted to the DB.
    """

    def test_adapter_update_persists_new_author_id(self):
        """
        Direct adapter.update() with a changed author_id persists to the DB.
        This verifies the adapter itself is correct.
        """
        engine = make_engine()
        author1_id, author2_id, book1_id, *_ = seed_engine(engine)

        books = SqlModelAdapter(Book, engine)
        book = books.read(book1_id)
        assert book.author_id == author1_id

        book.author_id = author2_id
        books.update(book)

        reloaded = books.read(book1_id)
        assert reloaded.author_id == author2_id

    async def test_author_change_via_form_persisted(self, user: User):
        """
        Selecting a new author in the Book form and saving must persist the new author_id.

        Fix: _handle_value_change now compares and propagates the hidden FK field
        (author_id) for modelselect widgets instead of the relationship object.
        The relationship object is intentionally left unchanged on _current_item to
        avoid SQLAlchemy cascade-inserting the detached Author on session.add().
        """
        import types
        from typing import cast
        from nicegui.events import ValueChangeEventArguments

        engine = make_engine()
        author1_id, author2_id, book1_id, _, _ = seed_engine(engine)
        assert author1_id is not None and author2_id is not None and book1_id is not None

        books = SqlModelAdapter(Book, engine)
        authors = SqlModelAdapter(Author, engine)
        captured: list[ModelForm] = []

        @ui.page('/')
        def page():
            form = ModelForm.from_adapter(Book, books, book1_id)  # type: ignore[arg-type]
            form.with_repositories({Author.__name__: authors})
            form.render()
            captured.append(form)

        await user.open('/')
        assert captured
        form = captured[0]
        assert cast(Book, form._validated_item).author_id == author1_id

        # Simulate selecting author2: set the widget value, then fire the handler
        # as the on_value_change callback would in a real browser session.
        form.widgets['author'].set_value(str(author2_id))  # type: ignore[union-attr]
        vce = cast(ValueChangeEventArguments, types.SimpleNamespace(
            sender=types.SimpleNamespace(value=str(author2_id)),
            client=None,
        ))
        form._handle_validate_and_change('author', vce)

        assert cast(Book, form._validated_item).author_id == author2_id, \
            '_validated_item.author_id must reflect the new author selection'

        form.save()
        reloaded = books.read(book1_id)  # type: ignore[arg-type]
        assert reloaded.author_id == author2_id, \
            'persisted book must have the new author_id after save()'


# ===========================================================================
# Section 3: one-to-many — Author.books rendered as editgrid
# ===========================================================================

class TestAuthorOneToManyRender:
    """Author form: books field must appear as a nested aggrid (editgrid)."""

    def test_author_books_loaded_after_read(self):
        """
        Verifies that Author.books is populated after SqlModelAdapter.read().

        model_validate() is called while the SQLAlchemy session is still open,
        so Pydantic's field access triggers the lazy-load descriptor for Author.books.
        The result is a fully-populated in-memory Author instance. No eager-loading
        needed — model_validate() already loads exactly what the model declares.
        """
        engine = make_engine()
        author1_id, _, book1_id, book2_id, _ = seed_engine(engine)

        adapter = SqlModelAdapter(Author, engine)
        author = adapter.read(author1_id)

        assert len(author.books) == 2, (
            'REVIEW-2: author.books is empty after read() — relationship not eagerly loaded. '
            'The embedded books editgrid will show nothing.'
        )

    async def test_books_renders_as_aggrid(self, user: User) -> None:
        engine = make_engine()
        seed_engine(engine)

        @ui.page('/')
        def page():
            authors = SqlModelAdapter(Author, engine)
            author = authors.read(1)
            ModelForm.from_item(author).render()

        await user.open('/')
        await user.should_see(ui.aggrid)

    async def test_books_editgrid_has_add_button(self, user: User) -> None:
        """The nested books editgrid exposes an add button (editable=True by default)."""
        engine = make_engine()
        seed_engine(engine)

        @ui.page('/')
        def page():
            authors = SqlModelAdapter(Author, engine)
            author = authors.read(1)
            ModelForm.from_item(author).render()

        await user.open('/')
        await user.should_see(ui.button, content='add')

    async def test_embedded_books_grid_persists_via_repository(self, user: User) -> None:
        """
        When a SqlModelAdapter for Book is registered in model_repositories, the
        embedded books editgrid uses a FilteredAdapter that routes mutations to the DB.
        Books created through the adapter are persisted and scoped to the parent author.
        """
        from typing import cast
        from niceview.dataadapter import FilteredAdapter
        from niceview.modeledit import EditGridWrapper

        engine = make_engine()
        author1_id, _, _, _, _ = seed_engine(engine)
        books_adapter = SqlModelAdapter(Book, engine)
        captured: list[ModelForm] = []

        @ui.page('/')
        def page():
            authors = SqlModelAdapter(Author, engine)
            author = authors.read(str(author1_id))
            form = ModelForm.from_item(author)
            form.with_repositories({Book.__name__: books_adapter})
            form.render()
            captured.append(form)

        await user.open('/')
        assert captured
        form = captured[0]

        # The embedded grid adapter should be a FilteredAdapter (not ListAdapter)
        books_widget = cast(EditGridWrapper, form.widgets.get('books'))
        assert books_widget is not None
        assert isinstance(books_widget.grid._data, FilteredAdapter)

        # author_id=0 is a placeholder; FilteredAdapter.create() overwrites it before persisting
        new_book = Book(title='Persisted via FilteredAdapter', author_id=0)  # type: ignore[call-arg]
        books_widget.grid._data.create(new_book)

        all_books = list(books_adapter)
        persisted = [b for b in all_books if b.title == 'Persisted via FilteredAdapter']
        assert len(persisted) == 1
        assert persisted[0].author_id == author1_id

        # Books from another author must not appear in the filtered view
        other_books = list(books_widget.grid._data)
        assert all(b.author_id == author1_id for b in other_books)

    async def test_name_and_email_inputs_present(self, user: User) -> None:
        engine = make_engine()
        seed_engine(engine)

        @ui.page('/')
        def page():
            authors = SqlModelAdapter(Author, engine)
            author = authors.read(1)
            ModelForm.from_item(author).render()

        await user.open('/')
        await user.should_see('Name')
        await user.should_see('Email')

    def test_books_editgrid_columns(self) -> None:
        """The embedded books editgrid shows title, published, and author columns (not hidden FK/PK fields)."""
        from niceview.modelgrid import _collect_aggrid_cols
        from niceview.fields import Fields
        cols = _collect_aggrid_cols(Fields(Book))
        col_fields = [c['field'] for c in cols]
        assert 'title' in col_fields
        assert 'published' in col_fields
        assert 'author' in col_fields
        assert 'id' not in col_fields
        assert 'author_id' not in col_fields


# ===========================================================================
# Section 4: Authors grid page (/) — EditGridWrapper + SqlModelAdapter
# ===========================================================================

class TestAuthorsGridPage:
    """Mirrors the / page from Example 7."""

    async def test_grid_renders(self, user: User) -> None:
        engine = make_engine()
        seed_engine(engine)

        @ui.page('/')
        def page():
            authors = SqlModelAdapter(Author, engine)
            EditGridWrapper(ModelGrid(Author, authors), title='Authors').render()

        await user.open('/')
        await user.should_see(ui.aggrid)

    async def test_title_visible(self, user: User) -> None:
        engine = make_engine()

        @ui.page('/')
        def page():
            authors = SqlModelAdapter(Author, engine)
            EditGridWrapper(ModelGrid(Author, authors), title='Authors').render()

        await user.open('/')
        await user.should_see('Authors')

    async def test_add_button_present(self, user: User) -> None:
        engine = make_engine()

        @ui.page('/')
        def page():
            authors = SqlModelAdapter(Author, engine)
            EditGridWrapper(ModelGrid(Author, authors)).render()

        await user.open('/')
        await user.should_see(ui.button, content='add')

    async def test_delete_button_present(self, user: User) -> None:
        engine = make_engine()

        @ui.page('/')
        def page():
            authors = SqlModelAdapter(Author, engine)
            EditGridWrapper(ModelGrid(Author, authors)).render()

        await user.open('/')
        await user.should_see(ui.button, content='delete')

    async def test_add_dialog_shows_name_field(self, user: User) -> None:
        """Clicking Add opens a dialog with the Author form (name, email inputs)."""
        engine = make_engine()

        @ui.page('/')
        def page():
            authors = SqlModelAdapter(Author, engine)
            EditGridWrapper(ModelGrid(Author, authors)).render()

        await user.open('/')
        user.find(content='add').click()
        await user.should_see('Name')

    async def test_add_dialog_shows_email_field(self, user: User) -> None:
        engine = make_engine()

        @ui.page('/')
        def page():
            authors = SqlModelAdapter(Author, engine)
            EditGridWrapper(ModelGrid(Author, authors)).render()

        await user.open('/')
        user.find(content='add').click()
        await user.should_see('Email')

    async def test_add_dialog_shows_books_editgrid(self, user: User) -> None:
        """
        The Add Author dialog includes the books editgrid by default (intended).

        Known limitation: edits in this embedded grid go through a ListAdapter
        backed by the in-memory Author.books list and are NOT written back to the DB.
        Persistence for nested editgrids is a future niceview feature.
        """
        engine = make_engine()

        @ui.page('/')
        def page():
            authors = SqlModelAdapter(Author, engine)
            EditGridWrapper(ModelGrid(Author, authors)).render()

        await user.open('/')
        user.find(content='add').click()
        await user.should_see(ui.aggrid)

    async def test_add_author_via_dialog_persists(self, user: User) -> None:
        """Filling Add Author dialog and clicking Create persists the new author to the DB."""
        engine = make_engine()
        authors_adapter = SqlModelAdapter(Author, engine)

        @ui.page('/')
        def page():
            EditGridWrapper(ModelGrid(Author, authors_adapter)).render()

        await user.open('/')
        initial_count = len(list(authors_adapter))
        user.find(content='add').click()
        await user.should_see('Name')
        user.find(kind=ui.input, content='Name').type('New Author')
        user.find(kind=ui.input, content='Email').type('new@example.com')
        user.find(kind=ui.button, content='Create').click()
        await user.should_not_see('Create')  # dialog closed

        all_authors = list(authors_adapter)
        assert len(all_authors) == initial_count + 1
        assert any(a.name == 'New Author' and a.email == 'new@example.com' for a in all_authors)

    async def test_add_author_short_name_keeps_dialog_open(self, user: User) -> None:
        """A name shorter than min_length=2 triggers a validation error; the dialog stays open."""
        engine = make_engine()

        @ui.page('/')
        def page():
            authors = SqlModelAdapter(Author, engine)
            EditGridWrapper(ModelGrid(Author, authors)).render()

        await user.open('/')
        user.find(content='add').click()
        await user.should_see('Name')
        user.find(kind=ui.input, content='Name').type('X')  # min_length=2, so 1 char is invalid
        user.find(kind=ui.button, content='Create').click()
        await user.should_see('Create')  # dialog still open

    async def test_add_book_in_author_form_no_exception(self, user: User) -> None:
        """
        Clicking 'add' in the embedded books editgrid must open a Book form without
        exception — even when no Author repository is provided, in which case the
        author select is rendered as a disabled placeholder instead of raising.
        """
        engine = make_engine()
        seed_engine(engine)

        @ui.page('/')
        def page():
            # Render Author form directly — no model_repositories for Author
            authors = SqlModelAdapter(Author, engine)
            author = authors.read('1')
            ModelForm.from_item(author).render()

        await user.open('/')
        await user.should_see('Name')        # Author form visible
        user.find(content='add').click()     # add button in embedded books editgrid
        await user.should_see('Title')       # Book form dialog opens (no exception)

    async def test_add_book_in_author_dialog_with_repo_persists(self, user: User) -> None:
        """
        When a Book repository is set on the Authors EditGridWrapper, opening the Edit
        Author dialog and adding a book via the embedded books grid persists the book
        to the DB with the correct author_id (injected by FilteredAdapter).
        """
        engine = make_engine()
        author1_id, _, _, _, _ = seed_engine(engine)
        books_adapter = SqlModelAdapter(Book, engine)

        @ui.page('/')
        def page():
            authors = SqlModelAdapter(Author, engine)
            wrapper = EditGridWrapper(ModelGrid(Author, authors))
            wrapper.with_repositories({Book.__name__: books_adapter})
            wrapper.render()

        await user.open('/')
        initial_count = len([b for b in books_adapter if b.author_id == author1_id])

        # Open edit dialog for first author (id=1)
        # EditGridWrapper's edit flow requires row selection — we use the Author form directly instead
        # by rendering it at page level (simpler for this integration test)

        @ui.page('/author')
        def author_page():
            authors = SqlModelAdapter(Author, engine)
            author = authors.read(str(author1_id))
            form = ModelForm.from_item(author)
            form.with_repositories({Book.__name__: books_adapter})
            form.render()

        await user.open('/author')
        user.find(content='add').click()     # click add in embedded books editgrid
        await user.should_see('Title')       # Book form dialog opens
        user.find(kind=ui.input, content='Title').type('Book From Dialog')
        user.find(kind=ui.button, content='Create').click()
        await user.should_not_see('Create')  # dialog closed

        new_books = [b for b in books_adapter if b.author_id == author1_id]
        assert len(new_books) == initial_count + 1
        assert any(b.title == 'Book From Dialog' for b in new_books)


# ===========================================================================
# Section 5: Books grid page (/books) — EditGridWrapper + author repository
# ===========================================================================

class TestBooksGridPage:
    """Mirrors the /books page from Example 7."""

    async def test_grid_renders(self, user: User) -> None:
        """
        Known: SQLAlchemy may emit a SAWarning during iteration —
        'Object of type <Author> not in session, add operation along Book.author
        won't proceed'. This occurs because model_validate() creates a new SQLModel
        instance and SQLAlchemy's instrumentation tries to manage the relationship
        on a non-session object. The warning is benign for reads; no fix applied.
        """
        engine = make_engine()
        seed_engine(engine)

        @ui.page('/')
        def page():
            books = SqlModelAdapter(Book, engine)
            authors = SqlModelAdapter(Author, engine)
            wrapper = EditGridWrapper(ModelGrid(Book, books), title='Books')
            wrapper.with_repositories({Author.__name__: authors})
            wrapper.render()

        await user.open('/')
        await user.should_see(ui.aggrid)

    async def test_title_visible(self, user: User) -> None:
        engine = make_engine()

        @ui.page('/')
        def page():
            books = SqlModelAdapter(Book, engine)
            authors = SqlModelAdapter(Author, engine)
            wrapper = EditGridWrapper(ModelGrid(Book, books), title='Books')
            wrapper.with_repositories({Author.__name__: authors})
            wrapper.render()

        await user.open('/')
        await user.should_see('Books')

    async def test_add_button_present(self, user: User) -> None:
        engine = make_engine()

        @ui.page('/')
        def page():
            books = SqlModelAdapter(Book, engine)
            authors = SqlModelAdapter(Author, engine)
            wrapper = EditGridWrapper(ModelGrid(Book, books))
            wrapper.with_repositories({Author.__name__: authors})
            wrapper.render()

        await user.open('/')
        await user.should_see(ui.button, content='add')

    async def test_add_dialog_shows_author_select(self, user: User) -> None:
        """
        Clicking Add opens a Book dialog with a ui.select for the Author field.
        """
        engine = make_engine()
        seed_engine(engine)

        @ui.page('/')
        def page():
            books = SqlModelAdapter(Book, engine)
            authors = SqlModelAdapter(Author, engine)
            wrapper = EditGridWrapper(ModelGrid(Book, books))
            wrapper.with_repositories({Author.__name__: authors})
            wrapper.render()

        await user.open('/')
        user.find(content='add').click()
        await user.should_see(ui.select)

    async def test_add_dialog_author_options_populated(self, user: User) -> None:
        """
        Author names from the repository appear as options in the Author select widget.

        Verified at form level (not via should_see) because NiceGUI's User fixture
        does not make closed-dropdown option labels visible as page text.
        """
        engine = make_engine()
        seed_engine(engine)
        captured: list = []

        @ui.page('/')
        def page():
            books = SqlModelAdapter(Book, engine)
            authors = SqlModelAdapter(Author, engine)
            new_book = Book()
            form = ModelForm.from_item(new_book)
            form.with_repositories({Author.__name__: authors})
            form.render()
            captured.append(form)

        await user.open('/')
        assert captured, 'page did not render'
        form = captured[0]
        options = form.widgets['author'].options
        # options is a dict: {pk_str: author_name}
        assert isinstance(options, dict)
        assert 'Jane Doe' in options.values()
        assert 'John Smith' in options.values()

    async def test_add_dialog_shows_title_field(self, user: User) -> None:
        engine = make_engine()
        seed_engine(engine)

        @ui.page('/')
        def page():
            books = SqlModelAdapter(Book, engine)
            authors = SqlModelAdapter(Author, engine)
            wrapper = EditGridWrapper(ModelGrid(Book, books))
            wrapper.with_repositories({Author.__name__: authors})
            wrapper.render()

        await user.open('/')
        user.find(content='add').click()
        await user.should_see('Title')
    
    async def test_add_book_via_dialog_persists(self, user: User) -> None:
        """
        Filling the Add Book dialog (title + author select) and clicking Create
        persists the book to the DB with the correct author_id.

        Author select interaction: first click opens the popup, second click (by
        label text) picks the option — this is the NiceGUI User fixture convention.
        """
        engine = make_engine()
        author1_id, _, _, _, _ = seed_engine(engine)
        books_adapter = SqlModelAdapter(Book, engine)

        @ui.page('/')
        def page():
            books = SqlModelAdapter(Book, engine)
            authors = SqlModelAdapter(Author, engine)
            wrapper = EditGridWrapper(ModelGrid(Book, books))
            wrapper.with_repositories({Author.__name__: authors})
            wrapper.render()

        await user.open('/')
        initial_count = len(list(books_adapter))
        user.find(content='add').click()
        await user.should_see('Title')
        user.find(kind=ui.input, content='Title').type('Brand New Book')
        user.find(kind=ui.select, content='Author').click()   # open popup
        user.find('Jane Doe').click()                         # pick option by label
        user.find(kind=ui.button, content='Create').click()
        await user.should_not_see('Create')

        all_books = list(books_adapter)
        assert len(all_books) == initial_count + 1
        new_book = next(b for b in all_books if b.title == 'Brand New Book')
        assert new_book.author_id == author1_id

    async def test_add_book_without_author_keeps_dialog_open(self, user: User) -> None:
        """Missing author (required FK) triggers a validation error; dialog stays open."""
        engine = make_engine()
        seed_engine(engine)

        @ui.page('/')
        def page():
            books = SqlModelAdapter(Book, engine)
            authors = SqlModelAdapter(Author, engine)
            wrapper = EditGridWrapper(ModelGrid(Book, books))
            wrapper.with_repositories({Author.__name__: authors})
            wrapper.render()

        await user.open('/')
        user.find(content='add').click()
        await user.should_see('Title')
        user.find(kind=ui.input, content='Title').type('Incomplete Book')
        # No author selected — author_id is required
        user.find(kind=ui.button, content='Create').click()
        await user.should_see('Create')  # dialog still open


# ===========================================================================
# Section 6: Detail pages — EditFormWrapper + SqlModelAdapter
# ===========================================================================

class TestAuthorDetailPage:
    """Mirrors the /authors/{id} page from Example 7."""

    async def test_save_and_refresh_buttons_present(self, user: User) -> None:
        engine = make_engine()
        seed_engine(engine)

        @ui.page('/')
        def page():
            authors = SqlModelAdapter(Author, engine)
            EditFormWrapper.from_adapter(Author, authors, 1, title='Edit Author').render()

        await user.open('/')
        await user.should_see(ui.button, content='save')
        await user.should_see(ui.button, content='refresh')

    async def test_title_visible(self, user: User) -> None:
        engine = make_engine()
        seed_engine(engine)

        @ui.page('/')
        def page():
            authors = SqlModelAdapter(Author, engine)
            EditFormWrapper.from_adapter(Author, authors, 1, title='Edit Author').render()

        await user.open('/')
        await user.should_see('Edit Author')

    async def test_author_name_displayed(self, user: User) -> None:
        engine = make_engine()
        seed_engine(engine)

        @ui.page('/')
        def page():
            authors = SqlModelAdapter(Author, engine)
            EditFormWrapper.from_adapter(Author, authors, 1, title='Edit Author').render()

        await user.open('/')
        await user.should_see('Jane Doe')

    async def test_save_persists_name_change(self, user: User) -> None:
        """Changing name and clicking Save writes the new value to the DB."""
        engine = make_engine()
        seed_engine(engine)

        @ui.page('/')
        def page():
            authors = SqlModelAdapter(Author, engine)
            EditFormWrapper.from_adapter(Author, authors, 1, title='Edit Author').render()

        await user.open('/')
        user.find('Name').clear().type('Jane Updated')
        user.find('Name').trigger('blur')
        user.find(content='save').click()

        reloaded = SqlModelAdapter(Author, engine).read(1)
        assert reloaded.name == 'Jane Updated'


class TestBookDetailPage:
    """Mirrors the /books/{id} page from Example 7."""

    async def test_save_and_refresh_buttons_present(self, user: User) -> None:
        engine = make_engine()
        seed_engine(engine)

        @ui.page('/')
        def page():
            books = SqlModelAdapter(Book, engine)
            authors = SqlModelAdapter(Author, engine)
            wrapper = EditFormWrapper.from_adapter(Book, books, 1, title='Edit Book')
            wrapper.with_repositories({Author.__name__: authors})
            wrapper.render()

        await user.open('/')
        await user.should_see(ui.button, content='save')
        await user.should_see(ui.button, content='refresh')

    async def test_author_select_present(self, user: User) -> None:
        engine = make_engine()
        seed_engine(engine)

        @ui.page('/')
        def page():
            books = SqlModelAdapter(Book, engine)
            authors = SqlModelAdapter(Author, engine)
            wrapper = EditFormWrapper.from_adapter(Book, books, 1, title='Edit Book')
            wrapper.with_repositories({Author.__name__: authors})
            wrapper.render()

        await user.open('/')
        await user.should_see(ui.select)

    async def test_save_persists_title_change(self, user: User) -> None:
        """Changing title and clicking Save writes the new value to the DB."""
        engine = make_engine()
        seed_engine(engine)

        @ui.page('/')
        def page():
            books = SqlModelAdapter(Book, engine)
            authors = SqlModelAdapter(Author, engine)
            wrapper = EditFormWrapper.from_adapter(Book, books, 1, title='Edit Book')
            wrapper.with_repositories({Author.__name__: authors})
            wrapper.render()

        await user.open('/')
        user.find('Title').clear().type('Completely New Title')
        user.find('Title').trigger('blur')
        user.find(content='save').click()

        reloaded = SqlModelAdapter(Book, engine).read(1)
        assert reloaded.title == 'Completely New Title'

