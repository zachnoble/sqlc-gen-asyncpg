"""Check runtime values against generated annotations."""

from __future__ import annotations

import enum
import sys
import types
import typing
from typing import Any

import asyncpg
import msgspec


def _hints(cls: type) -> dict[str, Any]:
    mod = sys.modules[cls.__module__]
    return typing.get_type_hints(cls, globalns=vars(mod))


def check(value: Any, hint: Any, path: str = "value") -> None:
    """Assert value conforms to hint."""
    if hint is Any:
        return
    if hint is None or hint is type(None):
        assert value is None, f"{path}: expected None, got {value!r}"
        return
    if isinstance(hint, typing.NewType):
        check(value, hint.__supertype__, path)
        return
    origin = typing.get_origin(hint)
    if origin in (typing.Union, types.UnionType):
        errors = []
        for alt in typing.get_args(hint):
            try:
                check(value, alt, path)
                return
            except AssertionError as e:
                errors.append(str(e))
        raise AssertionError(f"{path}: {value!r} matches none of {hint}: {errors}")
    if origin is list:
        assert type(value) is list, f"{path}: expected list, got {type(value).__name__}: {value!r}"
        (inner,) = typing.get_args(hint)
        for i, v in enumerate(value):
            # arrays may contain NULLs
            if v is not None:
                check(v, inner, f"{path}[{i}]")
        return
    if origin is dict:
        assert type(value) is dict, f"{path}: expected dict, got {value!r}"
        kt, vt = typing.get_args(hint)
        for k, v in value.items():
            check(k, kt, f"{path} key")
            check(v, vt, f"{path}[{k!r}]")
        return
    if origin is tuple:
        assert isinstance(value, tuple), f"{path}: expected tuple, got {value!r}"
        args = typing.get_args(hint)
        assert len(args) == len(value), f"{path}: wrong tuple arity {value!r}"
        for i, (v, a) in enumerate(zip(value, args)):
            check(v, a, f"{path}[{i}]")
        return
    if origin is asyncpg.Range:
        assert type(value) is asyncpg.Range, f"{path}: expected Range, got {value!r}"
        (inner,) = typing.get_args(hint)
        for bound in (value.lower, value.upper):
            if bound is not None:
                check(bound, inner, f"{path}.bound")
        return
    assert origin is None, f"{path}: unsupported annotation {hint}"
    assert isinstance(hint, type), f"{path}: unsupported annotation {hint!r}"
    if issubclass(hint, msgspec.Struct):
        assert type(value) is hint, f"{path}: expected {hint.__name__}, got {type(value).__name__}"
        for name, h in _hints(hint).items():
            check(getattr(value, name), h, f"{path}.{name}")
        return
    if issubclass(hint, enum.Enum):
        assert type(value) is hint, f"{path}: expected enum {hint.__name__}, got {type(value).__name__} {value!r}"
        return
    if hint is float:
        assert type(value) is float, f"{path}: expected float, got {type(value).__name__}"
        return
    if hint is int:
        assert type(value) is int, f"{path}: expected int, got {type(value).__name__}"
        return
    if hint is bool:
        assert type(value) is bool, f"{path}: expected bool, got {type(value).__name__}"
        return
    if hint is str:
        assert type(value) is str, f"{path}: expected str, got {type(value).__name__} {value!r}"
        return
    assert isinstance(value, hint), f"{path}: expected {hint.__name__}, got {type(value).__name__} {value!r}"


def conforms(value: Any, hint: Any) -> None:
    check(value, hint)


def check_return(method: Any, value: Any) -> None:
    """Assert value conforms to method's return annotation."""
    func = getattr(method, "__func__", method)
    mod = sys.modules[func.__module__]
    hints = typing.get_type_hints(func, globalns={"DBTX": Any, **vars(mod)})
    check(value, hints["return"], func.__qualname__)
