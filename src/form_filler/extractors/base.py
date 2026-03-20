"""Abstract base extractor.

Applying SOLID:
  S — each concrete subclass has exactly one source responsibility.
  O — add new sources by subclassing; never touch this file.
  L — all extractors are substitutable via BaseExtractor.
  I — thin interface: one abstract method only.
  D — Pipeline depends on List[BaseExtractor], not concrete classes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

# Type alias: every answer entry looks like this.
ExtractionResult = dict[str, dict[str, Any]]


class BaseExtractor(ABC):
    """Abstract base for all information extractors."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Human-readable identifier used in logging and answer metadata."""

    @abstractmethod
    def extract(
        self,
        schema: dict[str, Any],
        already_filled: ExtractionResult | None = None,
    ) -> ExtractionResult:
        """Extract information from this extractor's source.

        Args:
            schema:        Normalised schema dict (from SchemaExtractor).
            already_filled: Accumulated results from previous extractors.
                           Concrete implementations use this for
                           completion-only targeting (skip already-known fields).

        Returns:
            Dict mapping normalised field key → answer entry dict.
        """
