"""
    A lightweight wrapper to operate on nested dictionaries seamlessly.
"""
from itertools import chain
from typing import (
    Any,
    ItemsView,
    Iterable,
    Iterator,
    KeysView,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
    ValuesView,
)


def key_error(failing_key, original_path, raised_error):
    return KeyError(
        f"Cannot access key '{failing_key}' in path '{original_path}',"
        f" because of error: {repr(raised_error)}."
    )


def index_error(failing_key, original_path, raised_error):
    return IndexError(
        f"Cannot access index '{failing_key}' in path '{original_path}',"
        f" because of error: {repr(raised_error)}."
    )


def type_error(failing_key: str, original_path: str, raised_error: Exception) -> TypeError:
    return TypeError(f"Cannot access key '{failing_key}' in path '{original_path}'.")


def missing_brackets_error(key: str) -> ValueError:
    return ValueError(
        f"Key '{key}' is badly formated: you must use brackets to access list items."
    )


def index_must_be_integer_error(index, path: str) -> ValueError:
    return ValueError(
        f"Unable to access item '{index}' in key '{path}': "
        "you can only provide integers to access list items."
    )


def split_indexes(path: str) -> List[Union[str, int]]:
    key, *str_indexes = path.split("[")
    result = [key]

    if not str_indexes:
        return result
    
    try:
        for str_index in str_indexes:
            index = str_index[:-1]
            result.append(int(index))
    except ValueError:
        if index != '' and ']' not in index:
            raise index_must_be_integer_error(index, path)
        else:
            raise missing_brackets_error(path)

    return result


def split_path(path: str, key_separator: str) -> List[Union[str, int]]:
    keys = path.split(key_separator)
    result = []
    for key in keys:
        key_and_indexes = split_indexes(key) 
        result.extend(key_and_indexes)
    return result


def traverse(data: dict, keys: List[Union[str, int]], original_path: str):
    value = data
    try:
        for key in keys:
            value = value[key]
    except TypeError:
        raise TypeError(f"Cannot access key '{key}' in path '{original_path}': the element must be a dictionary or a list.")

    return value


TCut = TypeVar("TCut", bound="Cut")


class Cut:
    """
        Cut is a simple wrapper over the built-in dict class.

        It enables the standard dict API to operate on nested dictionnaries
        and cut accross list item by using dot-separated string keys.

        ex:
            query = {...} # Any dict structure
            proxy = Cut(query)
            proxy['pokemon[0].level']
            proxy['pokemon[0].level'] = 666
    """

    __slots__ = ("data", "sep")

    def __init__(self, data: Optional[dict] = None, sep: str = ".") -> None:
        self.data = data or {}
        self.sep = sep

    def __bool__(self) -> bool:
        return bool(self.data)

    def __contains__(self, path: str) -> bool:
        parent, last_key = self._traverse(self.data, path)
        try:
            parent[last_key]
            return True
        except (IndexError, KeyError):
            return False

    def __delitem__(self, path: str) -> None:
        parent, last_key = self._traverse(self.data, path)

        try:
            del parent[last_key]
        except KeyError as error:
            raise key_error(last_key, path, error)
        except IndexError as error:
            raise index_error(last_key, path, error)

    def __eq__(self, other: Any) -> bool:
        return self.data == other

    def __getitem__(self, path: str) -> Any:
        *keys, last_key = split_path(path, self.sep)
        item = traverse(data=self.data, keys=keys, original_path=path)

        try:
            return item[last_key]
        except KeyError as error:
            raise key_error(last_key, path, error)
        except IndexError as error:
            raise index_error(last_key, path, error)

    def __iter__(self) -> Iterator:
        return iter(self.data)

    def __len__(self) -> int:
        return len(self.data)

    def __ne__(self, other: Any) -> bool:
        return self.data != other

    def __setitem__(self, path: str, value: Any) -> None:
        *keys, last_key = split_path(path, self.sep)
        item = traverse(data=self.data, keys=keys, original_path=path)

        try:
            item[last_key] = value
        except IndexError as error:
            raise index_error(last_key, path, error)

    def __str__(self) -> str:
        return str(self.data)

    def all(self: TCut, path: str) -> Iterator[TCut]:
        """Wrap each item of an Iterable."""
        items = self[path]
        cls = self.__class__
        return (cls(_dict, self.sep) for _dict in items)

    def clear(self) -> None:
        return self.data.clear()

    def copy(self) -> dict:
        return self.data.copy()

    @classmethod
    def fromkeys(
        cls: Type[TCut], seq: Iterable, value: Optional[Iterable] = None
    ) -> TCut:
        return cls(dict.fromkeys(seq, value))

    def get(self, path: str, default: Optional[Any] = None) -> Any:
        try:
            return self[path]
        except (KeyError, IndexError) as error:
            if default is not None:
                return default
            raise error

    def keys(self) -> KeysView:
        return self.data.keys()

    def items(self) -> ItemsView:
        return self.data.items()

    def pop(self, path: str, default: Any = None) -> Any:
        try:
            parent, last_key = self._traverse(self.data, path)
        except KeyError as error:
            if default is not None:
                return default
            raise error
        except IndexError as error:
            if default is not None:
                return default
            raise error

        try:
            return parent.pop(last_key)
        except IndexError as error:
            if default is not None:
                return default
            raise index_error(last_key, path, error)
        except KeyError as error:
            if default is not None:
                return default
            raise key_error(last_key, path, error)

    def popitem(self) -> Any:
        return self.data.popitem()

    def setdefault(self, path: str, default: Optional[Any] = None) -> Any:
        # TODO: Fix the use of _traverse_list when its behavior will be defined
        parent = self.data
        *parent_keys, last_key = path.split(self.sep)

        if parent_keys:
            for _key in parent_keys:
                parent, _key = _traverse_list(parent, _key, path)
                try:
                    parent = parent[_key]
                except KeyError:
                    child: dict = {}
                    parent[_key] = child
                    parent = child
                except IndexError as error:
                    raise index_error(_key, path, error)

        parent, last_key = _traverse_list(parent, last_key, path)

        try:
            return parent[last_key]
        except KeyError:
            parent[last_key] = default
            return default
        except IndexError as error:
            raise index_error(last_key, path, error)

    def update(self, data=None, **kwargs):
        data = data or {}
        try:
            data.update(kwargs)
            pairs = data.items()
        except AttributeError:
            pairs = chain(data, kwargs.items())

        for key, value in pairs:
            self.__setitem__(key, value)

    def values(self) -> ValuesView:
        return self.data.values()

    def _traverse(self, parent, path: str):
        *parent_keys, last_key = path.split(self.sep)
        if len(parent_keys) > 0:
            try:
                for sub_key in parent_keys:
                    parent, sub_key = _traverse_list(parent, sub_key, path)
                    parent = parent[sub_key]
            except KeyError as error:
                raise key_error(sub_key, path, error)
            except IndexError as error:
                raise index_error(sub_key, path, error)
            except TypeError as error:
                raise key_error(sub_key, path, KeyError(f"{sub_key}"))

        parent, last_key = _traverse_list(parent, last_key, path)
        return parent, last_key

def _traverse_list(parent: dict, key: str, original_path: str):
    """
    As only `_traverse` calls `_traverse_list`, we assume `key` and `original_path` parameters are always strings.
    The parameter `parent` may not always be a dict
    Behavior:
        - If key is not a 
    """
    # TODO: Make a method that just returns the keys to acccess: "rooms[0][1]" ---> ["rooms", 0, 1]
    key, *str_indexes = key.split("[")
    if not str_indexes:
        return parent, key

    try:
        parent = parent[key]
    except KeyError as error:
        raise key_error(key, original_path, error)
    except TypeError as error:
        raise type_error(key, original_path, error)

    try:
        for str_index in str_indexes[:-1]:
            index = int(str_index[:-1])
            parent = parent[index]
    except IndexError as error:
        raise index_error(index, original_path, error)

    try:
        last_index = int(str_indexes[-1][:-1])
    except ValueError as error:
        raise index_error(str_indexes[-1][:-1], original_path, error)

    return parent, last_index