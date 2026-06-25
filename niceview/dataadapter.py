import datetime
import json
import logging
from pathlib import Path
from typing import Any, Callable, Generic, TypeVar, Iterator, Protocol, runtime_checkable
from fastapi import HTTPException, status
from sqlalchemy import Engine
import pydantic
import sqlmodel

log = logging.getLogger('niceview')


T = TypeVar('T', bound=pydantic.BaseModel)


@runtime_checkable
class ItemAdapter(Generic[T], Protocol):
    """
    Adapter protocol for single-item backends (ModelForm).

    read() loads the item; save() persists it. No key is needed — the adapter
    encapsulates the identity of the item (e.g. a file path, or a key bound at
    construction time via BoundItem).
    """
    def read(self) -> T: ...
    def save(self, item: T) -> T: ...


@runtime_checkable
class ReloadableAdapter(Protocol):
    """Protocol for adapters that support reloading from an external source (e.g. disk)."""
    def reload(self) -> None: ...


@runtime_checkable
class ReactiveAdapter(Protocol):
    """Protocol for adapters that support push-based change notification.

    All built-in CollectionAdapters (ListAdapter, JsonListAdapter, SqlModelAdapter)
    implement this protocol. ModelGrid.render() detects it and registers update_rows()
    automatically — no explicit call needed after adapter mutations.

    For ListAdapter backed by an ObservableList, direct mutations on the list object
    (bypassing the adapter) also fire the callback.
    """
    def on_change(self, handler: Callable[[], None]) -> None: ...


class _ChangeNotifier:
    """Mixin: callback registry for structural data change notifications."""

    def _init_notifier(self) -> None:
        self._change_handlers: list[Callable[[], None]] = []

    def on_change(self, handler: Callable[[], None]) -> None:
        self._change_handlers.append(handler)

    def _notify(self) -> None:
        for h in self._change_handlers:
            h()


class CollectionAdapter(Generic[T], Protocol):
    """
    Adapter protocol for list-backed components (ModelGrid, EditGridWrapper).

    Covers full CRUD plus key management. Use BoundItem to wrap a
    CollectionAdapter + key into an ItemAdapter for ModelForm.
    """
    def __iter__(self) -> Iterator[T]: ...
    def key_from_item(self, item: T) -> str: ...
    def read(self, key: str) -> T: ...
    def create(self, item: T) -> T: ...
    def update(self, item: T) -> T: ...
    def delete(self, key: str) -> None: ...


class BoundItem(Generic[T]):
    """
    Wraps a CollectionAdapter + key into an ItemAdapter.

    Use this for master-detail navigation: bind a selected row to a ModelForm
    without exposing key management to the form layer.
    """
    def __init__(self, adapter: CollectionAdapter[T], key: str) -> None:
        self._adapter = adapter
        self._key = key

    def read(self) -> T:
        return self._adapter.read(self._key)

    def save(self, item: T) -> T:
        return self._adapter.update(item)


class SqlModelAdapter(_ChangeNotifier, CollectionAdapter[T], ReloadableAdapter):
    """
    An adapter for SQLModel / SQLAlchemy to work with ModelForm and ModelGrid.

    Supports optimistic locking via lock_field (default 'updated_at').
    Set lock_field=None to disable locking.
    """
    def __init__(self, item_type: type[T], engine: Engine, key_field: str = 'id', lock_field: str | None = 'updated_at') -> None:
        if not isinstance(item_type, type) or not issubclass(item_type, sqlmodel.SQLModel):
            raise TypeError(f"item_type must be a subclass of SQLModel, got {item_type}")
        if not key_field:
            raise ValueError("key_field must be specified")
        if not hasattr(item_type, key_field):
            raise ValueError(f"Item type {item_type} does not have a field named {key_field}")
        if lock_field and not hasattr(item_type, lock_field):
            raise ValueError(f"Item type {item_type} does not have a field named {lock_field}")

        self._item_type = item_type
        self._engine = engine
        self._key_field = key_field
        self._lock_field = lock_field
        self._init_notifier()


    def __iter__(self) -> Iterator[T]:
        with sqlmodel.Session(self._engine) as session:
            statement = sqlmodel.select(self._item_type)
            result = session.exec(statement)
            for item in result:
                yield self._item_type.model_validate(item)


    def query_all_strs(self) -> Iterator[tuple[str, str]]:
        with sqlmodel.Session(self._engine) as session:
            statement = sqlmodel.select(self._item_type)
            result = session.exec(statement)
            for item in result:
                yield self.key_from_item(item), str(item)


    def key_from_item(self, item: pydantic.BaseModel) -> str:
        if not isinstance(item, sqlmodel.SQLModel):
            raise TypeError(f"Expected item to be an instance of {self._item_type}, got {type(item)}")
        key = getattr(item, self._key_field)
        if key is None:
            raise ValueError(f"Item {item} does not have a valid primary key value.")
        return str(key)

    def _key_to_native(self, key: str) -> Any:
        try:
            return int(key)
        except ValueError:
            return key

    def create(self, item: T) -> T:
        if not isinstance(item, sqlmodel.SQLModel):
            raise TypeError(f"Expected item to be an instance of {self._item_type}, got {type(item)}")

        with sqlmodel.Session(self._engine) as session:
            if self._lock_field:
                now = datetime.datetime.now(datetime.timezone.utc)
                setattr(item, self._lock_field, now)
            session.add(item)
            session.commit()
            session.refresh(item)
            item = self._item_type.model_validate(item)
        self._notify()
        return item


    def read(self, key: str) -> T:
        with sqlmodel.Session(self._engine) as session:
            item = session.get(self._item_type, self._key_to_native(key))
            if not item:
                raise ValueError(f"Item with key {key} not found in the database.")
            item = self._item_type.model_validate(item)
        return item


    def update(self, item: T) -> T:
        if not isinstance(item, sqlmodel.SQLModel):
            raise TypeError(f"Expected item to be an instance of {self._item_type}, got {type(item)}")

        key = self.key_from_item(item)
        with sqlmodel.Session(self._engine) as session:
            if self._lock_field:
                stmt = (
                    sqlmodel.select(self._item_type)
                    .where(getattr(self._item_type, self._key_field) == self._key_to_native(key))
                    .where(getattr(self._item_type, self._lock_field) == getattr(item, self._lock_field))
                    .with_for_update()
                )
                db_item = session.exec(stmt).first()
                if not db_item:
                    raise ValueError(
                        f"Optimistic Locking: Item with key={key} not found or already updated. "
                        f"(expected lock={getattr(item, self._lock_field)})"
                    )
            else:
                db_item = session.get(self._item_type, self._key_to_native(key))
                if not db_item:
                    raise ValueError(f"Item with key {key} not found in the database.")

            # Update the item with the new values
            exclude = {self._key_field}
            if self._lock_field:
                exclude.add(self._lock_field)
            data = item.model_dump(exclude=exclude)
            for field, value in data.items():
                setattr(db_item, field, value)

            if self._lock_field:
                setattr(db_item, self._lock_field, datetime.datetime.now(datetime.timezone.utc))

            session.add(db_item)
            session.commit()
            session.refresh(db_item)
            result = self._item_type.model_validate(db_item)
        self._notify()
        return result


    def delete(self, key: str) -> None:
        with sqlmodel.Session(self._engine) as session:
            item = session.get(self._item_type, self._key_to_native(key))
            if not item:
                raise ValueError(f"Item with key {key} not found in the database.")

            session.delete(item)
            session.commit()
        self._notify()

    def reload(self) -> None:
        """Signal that the backing database may have changed.

        Every read() already queries the database, so no in-memory state needs
        refreshing. Fires on_change() handlers so any registered ModelGrid
        re-renders from the current database state.
        """
        self._notify()


class ListAdapter(_ChangeNotifier, CollectionAdapter[T]):
    """
    An adapter for an in-memory list.

    Keys are monotonic counter strings ("0", "1", ...) assigned at creation time,
    stable across deletions. key_from_item() searches by object identity (O(n)).

    Implements ReactiveAdapter: on_change() handlers fire after every structural
    mutation via the adapter (create/update/delete). When the backing list is an
    ObservableList, direct mutations on the list object (bypassing the adapter)
    also fire the handlers and the key map is reconciled automatically.
    """
    def __init__(self, item_type: type[T], items: list[T]) -> None:
        self._item_type = item_type
        self._items = items
        self._counter = len(items)
        self._id_to_key: dict[int, str] = {id(item): str(i) for i, item in enumerate(items)}
        self._init_notifier()
        self._in_mutation = False
        from nicegui.observables import ObservableList
        if isinstance(items, ObservableList):
            items.on_change(self._on_observable_change)

    def _on_observable_change(self, _: Any = None) -> None:
        if not self._in_mutation:
            self._reconcile_keys()
            self._notify()

    def _reconcile_keys(self) -> None:
        current_ids = {id(item) for item in self._items}
        for oid in list(self._id_to_key):
            if oid not in current_ids:
                del self._id_to_key[oid]
        for item in self._items:
            if id(item) not in self._id_to_key:
                self._id_to_key[id(item)] = str(self._counter)
                self._counter += 1

    def __iter__(self) -> Iterator[T]:
        return iter(self._items)

    def key_from_item(self, item: pydantic.BaseModel) -> str:
        key = self._id_to_key.get(id(item))
        if key is None:
            raise KeyError(f"Item not found in adapter.")
        return key

    def query_all_strs(self) -> Iterator[tuple[str, str]]:
        for item in self._items:
            yield self.key_from_item(item), str(item)

    def _find_index(self, key: str) -> int:
        for i, item in enumerate(self._items):
            if self._id_to_key.get(id(item)) == key:
                return i
        raise KeyError(f"Item with key {key!r} not found in list.")

    def create(self, item: T) -> T:
        if not isinstance(item, self._item_type):
            raise TypeError(f"Expected item to be an instance of {self._item_type}, got {type(item)}")
        key = str(self._counter)
        self._counter += 1
        self._in_mutation = True
        try:
            self._items.append(item)
            self._id_to_key[id(item)] = key
        finally:
            self._in_mutation = False
        self._notify()
        return item

    def read(self, key: str) -> T:
        return self._items[self._find_index(key)]

    def update(self, item: T) -> T:
        key = self.key_from_item(item)
        idx = self._find_index(key)
        self._in_mutation = True
        try:
            old_item = self._items[idx]
            self._items[idx] = item
            if old_item is not item:
                del self._id_to_key[id(old_item)]
                self._id_to_key[id(item)] = key
        finally:
            self._in_mutation = False
        self._notify()
        return item

    def delete(self, key: str) -> None:
        idx = self._find_index(key)
        self._in_mutation = True
        try:
            old_item = self._items[idx]
            del self._items[idx]
            del self._id_to_key[id(old_item)]
        finally:
            self._in_mutation = False
        self._notify()


class FilteredAdapter(_ChangeNotifier, Generic[T]):
    """
    Wraps a CollectionAdapter, filtering __iter__ results by a predicate and
    injecting default field values on create().

    Typical use: show a parent-filtered view of a child collection (e.g., books
    for a specific author) while routing mutations through the underlying adapter
    for DB persistence.  Change notifications from the inner adapter are forwarded
    automatically.
    """

    def __init__(
        self,
        inner: CollectionAdapter[T],
        predicate: Callable[[T], bool],
        defaults: dict[str, Any] | None = None,
    ) -> None:
        self._inner = inner
        self._predicate = predicate
        self._defaults = defaults or {}
        self._init_notifier()
        if isinstance(inner, _ChangeNotifier):
            inner.on_change(self._notify)

    def __iter__(self) -> Iterator[T]:
        return (item for item in self._inner if self._predicate(item))

    def key_from_item(self, item: T) -> str:
        return self._inner.key_from_item(item)

    def read(self, key: str) -> T:
        return self._inner.read(key)

    def create(self, item: T) -> T:
        for field, value in self._defaults.items():
            setattr(item, field, value)
        return self._inner.create(item)

    def update(self, item: T) -> T:
        return self._inner.update(item)

    def delete(self, key: str) -> None:
        self._inner.delete(key)


class JsonAdapter(Generic[T]):
    """
    An ItemAdapter backed by a JSON file containing a single Pydantic model instance.
    Writes are atomic (.tmp → rename).
    """

    def __init__(self, item_type: type[T], path_name: Path, create_if_not_exist: bool = True) -> None:
        if not isinstance(item_type, type) or not issubclass(item_type, pydantic.BaseModel):
            raise TypeError(f"item_type must be a subclass of pydantic.BaseModel, got {item_type}")
        self._item_type = item_type
        self._path_name = path_name
        if path_name.exists() and not path_name.is_file():
            raise ValueError(f"Path {path_name} exists but is not a file.")
        if create_if_not_exist and not path_name.exists():
            self.save(self._item_type())

    def read(self) -> T:
        json_data = self._path_name.read_text(encoding='utf-8')
        return self._item_type.model_validate_json(json_data)

    def save(self, item: T) -> T:
        temp_file = self._path_name.with_suffix('.tmp')
        temp_file.write_text(item.model_dump_json(indent=2), encoding='utf-8')
        temp_file.rename(self._path_name)
        return item  # return same object to preserve in-memory references (e.g. nested grid adapters)


class JsonListAdapter(ListAdapter[T], ReloadableAdapter):
    """
    A data adapter that persists a list of Pydantic models as a JSON array.

    Items are kept in memory (like ListAdapter) and written to disk after
    every mutating operation. Writes are atomic: the full list is serialized to
    a .tmp file that is then renamed over the target path.

    Keys are monotonic counter strings (same as ListAdapter), stable across
    deletions within a session but reassigned after reload().
    """

    def __init__(self, item_type: type[T], path_name: Path, create_if_not_exist: bool = True) -> None:
        if not isinstance(item_type, type) or not issubclass(item_type, pydantic.BaseModel):
            raise TypeError(f"item_type must be a subclass of pydantic.BaseModel, got {item_type}")
        if path_name.exists() and not path_name.is_file():
            raise ValueError(f"Path {path_name} exists but is not a file.")

        self._path_name = path_name

        if path_name.exists():
            raw = json.loads(path_name.read_text(encoding='utf-8'))
            items: list[T] = [item_type.model_validate(d) for d in raw]
        elif create_if_not_exist:
            items = []
        else:
            raise FileNotFoundError(f"JSON file not found: {path_name}")

        super().__init__(item_type, items)

        if not path_name.exists():
            self._persist()

    def _persist(self) -> None:
        """Write the full item list to disk atomically."""
        temp_file = self._path_name.with_suffix('.tmp')
        data = [item.model_dump(mode='json') for item in self._items]
        temp_file.write_text(json.dumps(data, indent=2), encoding='utf-8')
        temp_file.rename(self._path_name)

    def reload(self) -> None:
        """Re-read items from the JSON file, replacing the in-memory list.

        Keys are reassigned to new counter values after reload, so any BoundItem
        holding a previous key is invalidated. Registered on_change() handlers
        (including ModelGrid) are notified automatically.
        """
        raw = json.loads(self._path_name.read_text(encoding='utf-8'))
        new_items = [self._item_type.model_validate(d) for d in raw]
        self._in_mutation = True
        try:
            self._items.clear()
            self._id_to_key.clear()
            self._items.extend(new_items)
            for item in new_items:
                self._id_to_key[id(item)] = str(self._counter)
                self._counter += 1
        finally:
            self._in_mutation = False
        self._notify()

    def create(self, item: T) -> T:
        result = super().create(item)
        self._persist()
        return result

    def update(self, item: T) -> T:
        result = super().update(item)
        self._persist()
        return result

    def delete(self, key: str) -> None:
        super().delete(key)
        self._persist()
