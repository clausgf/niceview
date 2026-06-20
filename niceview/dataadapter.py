import datetime
import json
import logging
from pathlib import Path
from typing import Any, Generic, TypeVar, Iterator, Protocol, runtime_checkable
from fastapi import HTTPException, status
from sqlalchemy import Engine
import pydantic
import sqlmodel
from nicegui.observables import ObservableList

log = logging.getLogger('niceview')


T = TypeVar('T', bound=pydantic.BaseModel)


class SingleItemAdapter(Generic[T], Protocol):
    """
    Minimal adapter protocol for single-item backends (ModelForm).
    Only read() and update() are required.
    """
    def read(self, key: str | int) -> T: ...
    def update(self, item: T, key: str) -> T: ...


@runtime_checkable
class ReloadableAdapter(Protocol):
    """Protocol for adapters that support reloading from an external source (e.g. disk)."""
    def reload(self) -> None: ...


class CollectionAdapter(SingleItemAdapter[T], Protocol):
    """
    Full adapter protocol for list-backed components (ModelGrid, EditGridWrapper).

    Extends SingleItemAdapter with iteration and full CRUD.
    SingleItemAdapter (read + update) is sufficient for ModelForm.
    """
    def __iter__(self) -> Iterator[T]: ...
    def key_from_item(self, item: T, index: int = -1) -> str: ...
    def key_from_str(self, key: str | int) -> Any: ...
    def create(self, item: T) -> T: ...
    def delete(self, key: str) -> None: ...
    def query_all_strs(self) -> Iterator[tuple[str, str]]: ...


class SqlModelAdapter(CollectionAdapter[T]):
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


    def key_from_item(self, item: pydantic.BaseModel, index: int = -1) -> str:
        if not isinstance(item, sqlmodel.SQLModel):
            raise TypeError(f"Expected item to be an instance of {self._item_type}, got {type(item)}")
        key = getattr(item, self._key_field)
        if key is None:
            raise ValueError(f"Item {item} does not have a valid primary key value.")
        return str(key)


    def key_from_str(self, key: str | int) -> Any:
        if isinstance(key, int):
            return key
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
        return item


    def read(self, key: str | int) -> T:
        key_dict = self.key_from_str(key)
        with sqlmodel.Session(self._engine) as session:
            item = session.get(self._item_type, key_dict)
            if not item:
                raise ValueError(f"Item with key {key} not found in the database.")
            item = self._item_type.model_validate(item)
        return item


    def update(self, item: T, key: str | int) -> T:
        if not isinstance(item, sqlmodel.SQLModel):
            raise TypeError(f"Expected item to be an instance of {self._item_type}, got {type(item)}")

        with sqlmodel.Session(self._engine) as session:
            if self._lock_field:
                stmt = (
                    sqlmodel.select(self._item_type)
                    .where(getattr(self._item_type, self._key_field) == self.key_from_str(key))
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
                db_item = session.get(self._item_type, self.key_from_str(key))
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
            return self._item_type.model_validate(db_item)


    def delete(self, key: str | int) -> None:
        with sqlmodel.Session(self._engine) as session:
            item = session.get(self._item_type, self.key_from_str(key))
            if not item:
                raise ValueError(f"Item with key {key} not found in the database.")

            session.delete(item)
            session.commit()


class ListAdapter(CollectionAdapter[T]):
    """
    An adapter for an in-memory list.

    Keys are the Python object identity (id()) of each item expressed as a string,
    so keys remain stable after deletions (no index shifting).
    """
    def __init__(self, item_type: type[T], items: list[T]) -> None:
        self._item_type = item_type
        self._items: ObservableList = items if isinstance(items, ObservableList) else ObservableList(items)

    def __iter__(self) -> Iterator[T]:
        return iter(self._items)

    def key_from_item(self, item: pydantic.BaseModel, index: int = -1) -> str:
        return str(id(item))

    def key_from_str(self, key: str | int) -> str:
        return str(key)

    def _find_index(self, key: str | int) -> int:
        key_str = str(key)
        for i, item in enumerate(self._items):
            if str(id(item)) == key_str:
                return i
        raise KeyError(f"Item with key {key!r} not found in list.")

    def query_all_strs(self) -> Iterator[tuple[str, str]]:
        for item in self._items:
            yield str(id(item)), str(item)

    def create(self, item: T) -> T:
        if not isinstance(item, self._item_type):
            raise TypeError(f"Expected item to be an instance of {self._item_type}, got {type(item)}")
        self._items.append(item)
        return item

    def read(self, key: str | int) -> T:
        return self._items[self._find_index(key)]

    def update(self, item: T, key: str) -> T:
        self._items[self._find_index(key)] = item
        return item

    def delete(self, key: str) -> None:
        del self._items[self._find_index(key)]


class JsonAdapter(SingleItemAdapter[T]):
    """
    A data adapter for a JSON file containing a single Pydantic model instance.
    Implements SingleItemAdapter (read + update only). Writes are atomic (.tmp → rename).
    """
    DEFAULT_KEY: str = "0"  # single-item adapters use a fixed key; the key itself is ignored by read/update

    def __init__(self, item_type: type[T], path_name: Path, create_if_not_exist: bool = True) -> None:
        if not isinstance(item_type, type) or not issubclass(item_type, pydantic.BaseModel):
            raise TypeError(f"item_type must be a subclass of pydantic.BaseModel, got {item_type}")
        self._item_type = item_type
        self._path_name = path_name
        if path_name.exists() and not path_name.is_file():
            raise ValueError(f"Path {path_name} exists but is not a file.")
        if create_if_not_exist and not path_name.exists():
            instance = self._item_type()
            self.update(instance, key=self.DEFAULT_KEY)

    def read(self, key: str | int) -> T:
        json_data = self._path_name.read_text(encoding='utf-8')
        item = self._item_type.model_validate_json(json_data)
        return item

    def update(self, item: T, key: str) -> T:
        temp_file = self._path_name.with_suffix('.tmp')
        json_data = item.model_dump_json(indent=2)
        temp_file.write_text(json_data, encoding='utf-8')
        temp_file.rename(self._path_name)
        return item  # return same object to preserve in-memory references (e.g. nested grid adapters)


class JsonListAdapter(ListAdapter[T]):
    """
    A data adapter that persists a list of Pydantic models as a JSON array.

    Items are kept in memory (like ListAdapter) and written to disk after
    every mutating operation. Writes are atomic: the full list is serialized to
    a .tmp file that is then renamed over the target path.

    Keys are Python object-identity based (str(id(item))), so they are stable
    within a session but change after reload().
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

        Existing keys become stale after this call; refresh the grid with
        update_rows() afterwards.
        """
        raw = json.loads(self._path_name.read_text(encoding='utf-8'))
        self._items.clear()
        self._items.extend(self._item_type.model_validate(d) for d in raw)

    def create(self, item: T) -> T:
        result = super().create(item)
        self._persist()
        return result

    def update(self, item: T, key: str) -> T:
        result = super().update(item, key)
        self._persist()
        return result

    def delete(self, key: str) -> None:
        super().delete(key)
        self._persist()
