"""Extensible filter registry shared by the real-time processor and UI."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

import numpy as np

from lab_week01.filters import get_filter_info

FilterTransform = Callable[[np.ndarray], np.ndarray]


@dataclass(frozen=True)
class FilterDefinition:
    """One selectable image transformation."""

    key: str
    label: str
    transform: FilterTransform


class FilterRegistry:
    """Validated collection of filters with stable UI choices."""

    def __init__(self, definitions: Iterable[FilterDefinition]):
        filters: dict[str, FilterDefinition] = {}
        for definition in definitions:
            if not definition.key:
                raise ValueError("Filter key cannot be empty")
            if definition.key in filters:
                raise ValueError(f"Duplicate filter key: {definition.key}")
            if not callable(definition.transform):
                raise TypeError(f"Filter transform is not callable: {definition.key}")
            filters[definition.key] = definition

        if not filters:
            raise ValueError("At least one filter must be registered")
        self._filters = filters

    @classmethod
    def from_legacy_filter_info(
        cls, filter_info: Mapping[str, Mapping[str, object]]
    ) -> "FilterRegistry":
        """Adapt the original lab dictionary without changing existing filters."""

        definitions = [
            FilterDefinition(
                key="original",
                label="Original",
                transform=lambda image: image.copy(),
            )
        ]
        for key, info in filter_info.items():
            label = info.get("name")
            transform = info.get("function")
            if not isinstance(label, str):
                raise TypeError(f"Filter label must be a string: {key}")
            if not callable(transform):
                raise TypeError(f"Filter function must be callable: {key}")
            definitions.append(
                FilterDefinition(key=key, label=label, transform=transform)
            )
        return cls(definitions)

    @classmethod
    def default(cls) -> "FilterRegistry":
        """Build a registry from all filters exposed by ``filters.py``."""

        return cls.from_legacy_filter_info(get_filter_info())

    def get(self, key: str) -> FilterDefinition | None:
        return self._filters.get(key)

    def keys(self) -> tuple[str, ...]:
        return tuple(self._filters)

    def choices(self) -> list[tuple[str, str]]:
        """Return ``(display label, stable key)`` pairs for UI components."""

        return [
            (definition.label, definition.key)
            for definition in self._filters.values()
        ]
