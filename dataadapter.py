import ast
import datetime
from typing import Any, Generic, TypeVar, Iterator, Protocol
from pydantic import BaseModel
from sqlalchemy import Engine
import sqlmodel


T = TypeVar('T', bound=BaseModel)
class ModelDataAdapter(Generic[T], Protocol):
    """
    A protocol for a data adapter that can be used with the ModelGrid.
    It defines the methods that must be implemented by any data adapter.

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


    def key_from_item(self, item: BaseModel, index: int = -1) -> str:
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
            print(f"before add: {item=}")
            session.add(item)
            print(f"before commit: {item=}")
            session.commit()
            print(f"before refresh: {item=}")
            session.refresh(item)  # Refresh to get the updated item with the new ID
            print(f"before model_validate: {item=}")
            item = self._item_type.model_validate(item) # force reloading all fields & detach object
        print(f"before return: {item=}")
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
    An adapter for a list to work with the ModelGrid.
    """
    def __init__(self, item_type: type[T], items: list[T]) -> None:
        self._item_type = item_type
        self._items = items

    def __iter__(self) -> Iterator[T]:
        return iter(self._items)
    
    def query_all_strs(self) -> Iterator[tuple[str, str]]:
        for index, item in enumerate(self._items):
            yield str(index), str(item)

    def key_from_item(self, item: BaseModel, index: int = -1) -> str:
        key = str(index)
        return key

    def key_from_str(self, key: str | int) -> int:
        return int(key)

    def create(self, item: T) -> T:
        if not isinstance(item, self._item_type):
            raise TypeError(f"Expected item to be an instance of {self._item_type}, got {type(item)}")
        self._items.append(item)
        return item

    def read(self, key: str | int) -> T:
        index = self.key_from_str(key)
        if index < 0 or index >= len(self._items):
            raise IndexError(f"Index {index} is out of bounds for the list.")

        return self._items[index]

    def update(self, item: T, key: str) -> T:
        index = self.key_from_str(key)
        if index < 0 or index >= len(self._items):
            raise IndexError(f"Index {index} is out of bounds for the list.")

        self._items[index] = item
        return item

    def delete(self, key: str) -> None:
        index = self.key_from_str(key)
        if index < 0 or index >= len(self._items):
            raise IndexError(f"Index {index} is out of bounds for the list.")

        del self._items[index]

