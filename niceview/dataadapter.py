import datetime
import json
import logging
from pathlib import Path
from typing import Any, Generic, TypeVar, Iterator, Protocol
from fastapi import HTTPException, status
from sqlalchemy import Engine
import pydantic
import sqlmodel

log = logging.getLogger('niceview')


T = TypeVar('T', bound=pydantic.BaseModel)
class ModelDataAdapter(Generic[T], Protocol):
    """
    This protocol defines the methods that must be implemented by any data adapter.

    DataAdapters are responsible for managing the data access layer and providing 
    a consistent collection API for the ModelGrid.

    DataAdapters could also manage single instances instead of collections
    (e.g. for editing a single item in a ModelForm). Then only the read and update
    methods need to be implemented, keys can be ignored.

    A data adapter could be a pure adapter for a list, or something
    more complex like an adapter for SQLModel similar to a JPA Repository.
    """

    def __iter__(self) -> Iterator[T]:
        raise NotImplementedError

    def key_from_item(self, item: T, index: int = -1) -> str:
        raise NotImplementedError

    def key_from_str(self, key: str | int) -> Any:
        raise NotImplementedError

    def create(self, item: T) -> T:
        """
        Add a new item to the data store.
        """
        raise NotImplementedError

    def read(self, key: str | int) -> T:
        raise NotImplementedError

    def update(self, item: T, key: str) -> T:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def query_all_strs(self) -> Iterator[tuple[str, str]]:
        """
        Execute a query to retrieve the key and a string representation (__str__) 
        of all items.
        """
        raise NotImplementedError("query method is not implemented in this adapter")


class SqlModelAdapter(ModelDataAdapter[T]):
    """
    An adapter for SQLModel to work with the ModelGrid.
    """
    def __init__(self, item_type: type[T], engine: Engine, key_field: str = 'id', lock_field: str = 'updated_at') -> None:
        if not issubclass(item_type, sqlmodel.SQLModel):
            raise TypeError(f"Expected item_type to be a subclass of SQLModel, got {item_type}")
        if not key_field:
            raise ValueError("key_field must be specified")
        if key_field and not hasattr(item_type, key_field):
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
                # Do we have to detach the items? Just to be sure...
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

        # pk_columns = item.__table__.primary_key.columns # type: ignore
        # pks = {col.name: getattr(item, col.name) for col in pk_columns}
        # key = str(pks)
        key = getattr(item, self._key_field)
        if key is None:
            raise ValueError(f"Item {item} does not have a valid primary key value.")
        return str(key)


    # def key_from_str(self, key: str) -> dict[str, Any]:
    #     try:
    #         return ast.literal_eval(key)  # Use ast.literal_eval for safety
    #     except (SyntaxError, ValueError):
    #         raise ValueError(f"Invalid key format: {key}")
    def key_from_str(self, key: str | int) -> Any:
        """
        Convert a string key to the appropriate type for the primary key.
        This method assumes that the key is a string representation of an integer or a string.
        """
        if isinstance(key, int):
            return key
        try:
            # Try to convert the key to an integer
            return int(key)
        except ValueError:
            # If it fails, return the key as a string
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
            session.refresh(item)  # Refresh to get the updated item with the new ID
            item = self._item_type.model_validate(item) # force reloading all fields & detach object
        return item


    def read(self, key: str | int) -> T:
        key_dict = self.key_from_str(key)
        with sqlmodel.Session(self._engine) as session:
            item = session.get(self._item_type, key_dict)
            if not item:
                raise ValueError(f"Item with key {key} not found in the database.")

            # force reloading all fields and detach the object
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
            data = item.model_dump(exclude={self._key_field, self._lock_field}, exclude_unset=True)
            for field, value in data.items():
                setattr(db_item, field, value)

            # Update the lock field
            if self._lock_field:
                now = datetime.datetime.now(datetime.timezone.utc)
                setattr(db_item, self._lock_field, now)

            # Add the updated item to the session
            session.add(db_item)
            session.commit()
            session.refresh(db_item)
            db_item = self._item_type.model_validate(db_item)  # force reloading all fields & detach object
            return db_item

        #     session.merge(item)
        #     session.commit()
        #     # force reloading all fields and detach the object
        #     item = self._item_type.model_validate(item)
        # return item


    def delete(self, key: str | int) -> None:
        with sqlmodel.Session(self._engine) as session:
            item = session.get(self._item_type, self.key_from_str(key))
            if not item:
                raise ValueError(f"Item with key {key} not found in the database.")

            session.delete(item)
            session.commit()


class ListModelAdapter(ModelDataAdapter[T]):
    """
    An adapter for an in-memory list.

    Keys are the Python object identity (id()) of each item expressed as a string,
    so keys remain stable after deletions (no index shifting).
    """
    def __init__(self, item_type: type[T], items: list[T]) -> None:
        self._item_type = item_type
        self._items = items

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


class JsonSingleModelAdapter(ModelDataAdapter[T]):
    """
    A data adapter for a JSON file containing a single Pydantic model instance.
    Writes are atomic (write to .tmp, then rename).
    """
    def __init__(self, item_type: type[T], path_name: Path, create_if_not_exist: bool = True) -> None:
        if not isinstance(item_type, type) or not issubclass(item_type, pydantic.BaseModel):
            raise TypeError(f"item_type must be a subclass of pydantic.BaseModel, got {item_type}")
        self._item_type = item_type
        self._path_name = path_name
        if path_name.exists() and not path_name.is_file():
            raise ValueError(f"Path {path_name} exists but is not a file.")
        if create_if_not_exist and not path_name.exists():
            instance = self._item_type()
            self.update(instance, key="0")

    def read(self, key: str | int) -> T:
        json_data = self._path_name.read_text(encoding='utf-8')
        item = self._item_type.model_validate_json(json_data)
        return item

    def update(self, item: T, key: str) -> T:
        temp_file = self._path_name.with_suffix('.tmp')
        json_data = item.model_dump_json(indent=2)
        temp_file.write_text(json_data, encoding='utf-8')
        temp_file.rename(self._path_name)
        return self.read(key)

    def __iter__(self) -> Iterator[T]:
        raise NotImplementedError

    def key_from_item(self, item: T, index: int = -1) -> str:
        raise NotImplementedError

    def key_from_str(self, key: str | int) -> Any:
        raise NotImplementedError

    def create(self, item: T) -> T:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def query_all_strs(self) -> Iterator[tuple[str, str]]:
        raise NotImplementedError


class JsonListModelAdapter(ListModelAdapter[T]):
    """
    A data adapter that persists a list of Pydantic models as a JSON array.

    Items are kept in memory (like ListModelAdapter) and written to disk after
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
