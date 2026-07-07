"""
SQLModel adapter for NiceView.

This module requires the optional `sqlmodel` dependency:
    pip install niceview[sqlmodel]
"""
import datetime
import logging
from typing import Any, Generic, Iterator, TypeVar

import pydantic
from sqlalchemy import Engine
import sqlmodel

from niceview.dataadapter import CollectionAdapter, ConflictError, ReloadableAdapter, _ChangeNotifier

log = logging.getLogger('niceview')

T = TypeVar('T', bound=pydantic.BaseModel)


class SqlModelAdapter(_ChangeNotifier, CollectionAdapter[T], ReloadableAdapter):
    """
    An adapter for SQLModel / SQLAlchemy to work with ModelForm and ModelGrid.

    Supports optimistic locking via lock_field (default 'updated_at').
    Set lock_field=None to disable locking.

    created_field (default None): if set, the named field is automatically
    populated with datetime.now(utc) when create() is called.
    """
    def __init__(self, item_type: type[T], engine: Engine, key_field: str = 'id', lock_field: str | None = 'updated_at', created_field: str | None = None) -> None:
        if not isinstance(item_type, type) or not issubclass(item_type, sqlmodel.SQLModel):
            raise TypeError(f"item_type must be a subclass of SQLModel, got {item_type}")
        if not key_field:
            raise ValueError("key_field must be specified")
        if not hasattr(item_type, key_field):
            raise ValueError(f"Item type {item_type} does not have a field named {key_field}")
        if lock_field and not hasattr(item_type, lock_field):
            raise ValueError(f"Item type {item_type} does not have a field named {lock_field}")
        if created_field and not hasattr(item_type, created_field):
            raise ValueError(f"Item type {item_type} does not have a field named {created_field}")

        self._item_type = item_type
        self._engine = engine
        self._key_field = key_field
        self._lock_field = lock_field
        self._created_field = created_field
        self._init_notifier()

    def __iter__(self) -> Iterator[T]:
        with sqlmodel.Session(self._engine) as session:
            statement = sqlmodel.select(self._item_type)
            result = session.exec(statement)
            for item in result:
                yield self._item_type.model_validate(item)

    def _query_all_strs(self) -> Iterator[tuple[str, str]]:
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
            now = datetime.datetime.now(datetime.timezone.utc)
            if self._created_field:
                setattr(item, self._created_field, now)
            if self._lock_field:
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
                    # Distinguish a real conflict from a deleted/missing row.
                    if session.get(self._item_type, self._key_to_native(key)) is None:
                        raise ValueError(f"Item with key {key} not found in the database.")
                    log.warning(f"Optimistic lock conflict for key={key} (expected lock={getattr(item, self._lock_field)})")
                    raise ConflictError(
                        "Optimistic Locking: this item was changed by another user while you were editing it. "
                        "Please reload and re-apply your changes."
                    )
            else:
                db_item = session.get(self._item_type, self._key_to_native(key))
                if not db_item:
                    raise ValueError(f"Item with key {key} not found in the database.")

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
