from __future__ import annotations

from abc import ABC, abstractmethod

from playwright.async_api import Page

from scraper.models import Listing


class BaseParser(ABC):
    """Every site-specific parser must implement ``parse``."""

    source: str  # "yad2", "madlan", …

    @abstractmethod
    async def parse(self, page: Page, url: str) -> Listing:
        """Parse a single listing page and return a ``Listing``."""
        ...
