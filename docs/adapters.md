Data Adapters
=============

The abstraction layer between NiceView components and storage backends.

[← Back to the README](../README.md)


Data Adapters
-------------

Adapters decouple UI components from storage. Pass them explicitly for full control,
or let the `from_*` factory methods create them transparently.

| Adapter | Backs | Description |
|---|---|---|
| `ListAdapter(Type, list)` | Grid | In-memory list |
| `JsonAdapter(Type, path)` | Form | Single object in a JSON file; supports `lock_field=`, `created_field=`, `strict=` |
| `JsonListAdapter(Type, path)` | Grid | List of objects in a JSON file; supports `created_field=`, `strict=` |
| `SqlModelAdapter(Type, engine)` | Grid, Form | SQLModel / SQLAlchemy table *(requires the `sqlmodel` extra, see [Installation](../README.md#installation))* |
| `DirectoryAdapter(dir_path)` | `DrillDownWrapper` | One file per item in a directory; items are filename metadata (`FileEntry`), not parsed content — supports `rename()` |
| `FilteredAdapter(inner, predicate, defaults=)` | Grid, `DrillDownWrapper` | Filtered view of another `CollectionAdapter` (see below) |

All JSON adapters write atomically (`.tmp` → rename).
`JsonListAdapter` and `SqlModelAdapter` both implement `ReloadableAdapter`: `reload()` re-reads
from disk (JSON) or fires a grid-refresh notification (SQL, where every `read()` is already live).

**`DirectoryAdapter`** models "files in a directory" for `DrillDownWrapper`'s file-per-item use
case. `items()`/`read()` return `FileEntry(name, mtime, size)` — metadata only, never the parsed
file content; open the file's own `JsonAdapter`/`JsonListAdapter` for that (typically inside
`render_detail`). Keys never carry the file suffix — `name` is always the bare filename stem, so
a "Name" widget in `render_detail` never has to show or strip `.json` itself; if a user types the
suffix anyway, `create()`/`rename()` strip a trailing match rather than doubling it up
(`"note.json"` → `note`, file `note.json`). `create(item=None)` picks a free `'untitled-01'`,
`'untitled-02'`, ... name and writes `default_content`; `rename(key, new_key)` renames the file
on disk. Both are meant to be called directly by application code (an "Add" handler, a "Name"
widget's `blur` handler), not through `DrillDownWrapper`'s generic `item_type()`-based Add flow
— see `examples/13_directory_drilldown.py`.

**`FilteredAdapter`** wraps any `CollectionAdapter` and filters iteration by a predicate —
the standard way to show a parent-filtered view of a child collection (e.g. only the books of
one author) while mutations still go through the inner adapter for persistence. `defaults=`
injects field values on `create()`, so new items automatically belong to the current parent.
Change notifications and `reload()` are forwarded from/to the inner adapter. See
`examples/11_tree_navigation.py`.

```python
from niceview import FilteredAdapter

books_of_author = FilteredAdapter(books_adapter,
    predicate=lambda b: b.author_id == author.id,
    defaults={'author_id': author.id},   # applied to every create()
)
ModelGrid(Book, books_of_author).render()
```

**Lenient loading (default) vs strict loading:** `JsonAdapter` and `JsonListAdapter` default to
`strict=False`, which means a hand-edited or partially-migrated file does not crash the
application:

- **Malformed JSON** or a non-object/non-array root → `log.error`, return a default instance / empty list.
- **Unknown field** → `log.error`, field ignored.
- **Field with invalid value** → `log.error`, field dropped and replaced by its model default.
- **Required field absent (no default)** → `log.error`, item/load fails and raises (last resort).
- **`OSError` reading the file** (`JsonAdapter` only) → `log.error`, return `Type()` with all defaults.

Set `strict=True` to restore the original behaviour where any read error raises immediately.
The `StorageError` raised by `JsonAdapter.save()` during an optimistic-locking check is only
possible in strict mode (in lenient mode a corrupted file returns `None` lock values, so the
check is skipped).

The helper functions `lenient_model_load` and `lenient_list_load` are also importable from
`niceview` for use outside the built-in adapters.

> **Breaking change (since lenient default):** code that relied on `JsonAdapter.read()` or
> `JsonListAdapter` raising on a malformed file must pass `strict=True` explicitly.

```python
from niceview import lenient_model_load, lenient_list_load

# Load a single model from a JSON string, tolerating bad fields:
item = lenient_model_load(MyModel, json_text, context='myfile.json')

# Load a list, skipping unrecoverable items:
items = lenient_list_load(MyModel, json_text, context='myfile.json')
```

**Optimistic locking:** When `lock_field=` is set, `save()` compares the stored timestamp against
the one in memory before writing. The check only fires when *both* sides have a non-`None` value —
a `None` on either side is treated as "no lock data" and the save proceeds. Two exceptions can be
raised; both are caught by `ModelForm.save()` and `EditGridWrapper` with a user-facing `ui.notify`:

| Exception | When raised |
|---|---|
| `niceview.ConflictError` | Both timestamps are set but differ (concurrent modification) |
| `niceview.StorageError` | The stored file cannot be read during the lock check (corrupted, wrong schema, I/O error) |

Custom code calling `adapter.save()` directly should handle both:

```python
from niceview import ConflictError, StorageError

try:
    adapter.save(item)
except ConflictError:
    ui.notify('Someone else changed this item. Please reload.', color='warning')
except StorageError:
    ui.notify('The data file could not be read. Please contact your administrator.', color='negative')
```

**Adapter protocols** — implement these for custom backends:

| Protocol | Methods | Used by |
|---|---|---|
| `ItemAdapter[T]` | `read() -> T`, `save(item) -> T` | `ModelForm` |
| `CollectionAdapter[T]` | `__iter__`, `key_from_item(item) -> str`, `items() -> Iterator[(str, T)]`, `read(key) -> T`, `create(item) -> T`, `update(item) -> T`, `delete(key)` | `ModelGrid`, `EditGridWrapper` |
| `ReloadableAdapter` | `reload()` | `EditGridWrapper` (Refresh button), `FilteredAdapter` (forwarded) |
| `ReactiveAdapter` | `on_change(handler)` | `ModelGrid` (auto-update) |

`update()` returns the stored item, which may differ from the input (e.g. `SqlModelAdapter` refreshes `updated_at`). `key_from_item()` raises `KeyError` if the item is not in the adapter; `read()` raises `KeyError`/`ValueError` if the key is not found.

`items()` yields `(key, item)` pairs — like `dict.items()`, useful whenever key and item are needed together (e.g. building navigation URLs):
```python
for key, project in projects_adapter.items():
    with ui.card().on('click', lambda k=key: ui.navigate.to(f'/projects/{k}')):
        ui.label(project.name)
```

`BoundItem(adapter, key)` wraps a `CollectionAdapter` + a string key into an `ItemAdapter` —
the standard bridge for master-detail navigation (e.g. `ModelForm.from_adapter()`).
`BoundItem` can be imported directly from `niceview` (`from niceview import BoundItem`).

**Reactive updates**

All built-in adapters implement `ReactiveAdapter` via the `_ChangeNotifier` mixin.
`ModelGrid.render()` detects this and registers `update_rows()` automatically, so
structural mutations through the adapter (create / update / delete) refresh the grid
without any manual call — for in-memory lists, JSON files, and SQL databases alike.

What is **not** caught automatically: in-place attribute changes on existing items
(`item.name = 'new'`). These bypass the adapter entirely. Use `grid.update_rows()`
or the `EditGridWrapper` Refresh button for that case.

```python
# Adapter mutations → grid auto-updates (all adapter types)
adapter = ListAdapter(User, items)
adapter = ListAdapter(User, items, created_field='created_at')   # set created_at on create()
grid = ModelGridInlineEdit.from_adapter(User, adapter)
grid.render()
adapter.create(User(name='Carol'))   # grid refreshes automatically
adapter.delete(key)                  # grid refreshes automatically

# In-place attribute change → manual refresh needed
items[0].name = 'new name'
grid.update_rows()                   # must call explicitly
```

**ObservableList** additionally catches direct mutations on the list object that
bypass the adapter — useful when non-NiceView code appends to the same list:

```python
from nicegui.observables import ObservableList

obs = ObservableList([User(name='Alice')])
grid = ModelGrid.from_list(User, obs)
grid.render()
obs.append(User(name='Bob'))   # also triggers update_rows(), no adapter call needed
```

```python
from niceview import SqlModelAdapter

adapter = SqlModelAdapter(Book, engine)                                          # optimistic locking on updated_at
adapter = SqlModelAdapter(Book, engine, lock_field=None)                         # without locking
adapter = SqlModelAdapter(Book, engine, created_field='created_at')              # set created_at on create()
adapter = SqlModelAdapter(Book, engine, created_field='created_at', lock_field='updated_at')  # both

# Form for a specific record (fields only) — key must be str
form = ModelForm.from_adapter(Book, adapter, str(book_id))
form.render()

# Form with chrome (title + save/refresh buttons)
EditFormWrapper.from_adapter(Book, adapter, str(book_id), title='Edit Book').render()

# Grid over the full table
ModelGrid(Book, adapter).render()
EditGridWrapper.from_adapter(Book, adapter, title='Books').render()
```
