from abc import abstractmethod
from enum import Enum
from typing import Dict, List, Type

import regex
from bot.exts.filtering._settings import Settings
from bot.exts.filtering._filters.filter import Filter
from bot.exts.filtering._filter_context import FilterContext
from bot.exts.filtering._utils import FieldRequiring

VARIATION_SELECTORS = r"\uFE00-\uFE0F\U000E0100-\U000E01EF"
INVISIBLE_RE = regex.compile(rf"[{VARIATION_SELECTORS}\p{{UNASSIGNED}}\p{{FORMAT}}\p{{CONTROL}}--\s]", regex.V1)
ZALGO_RE = regex.compile(rf"[\p{{NONSPACING MARK}}\p{{ENCLOSING MARK}}--[{VARIATION_SELECTORS}]]", regex.V1)


class ListType(Enum):
    DENY = 0
    ALLOW = 1


class FilterList(FieldRequiring):
    """Dispatches events to lists of _filters, and aggregates the responses into a single list of actions to take."""

    # Each subclass must define a name matching the filter_list name we're expecting to receive from the database.
    # Names must be unique across all filter lists.
    name = FieldRequiring.MUST_SET_UNIQUE

    # Each subclass must define a description of what the list does, to be displayed in the UI.
    description = FieldRequiring.MUST_SET

    def __init__(self, filter_type: Type[Filter]):
        self._filter_lists: dict[ListType, list[Filter]] = {}
        self._defaults: dict[ListType, Settings] = {}

        self.filter_type = filter_type

    def add_list(self, list_data: Dict) -> None:
        """Add a whitelist or a blacklist to this filter list."""
        filters = [self.filter_type(filter_data) for filter_data in list_data["filters"]]
        settings = Settings(list_data["settings"])

        list_type = ListType(list_data["list_type"])
        self._filter_lists[list_type] = filters
        self._defaults[list_type] = settings

    @abstractmethod
    def action(self, ctx: FilterContext) -> Settings:
        """Dispatch the given event to the list's filters, and return an aggregated result of the action to take."""

    @staticmethod
    def filter_list_result(ctx: FilterContext, filters: List[Filter], settings: Settings) -> Settings:
        """Sift through the filters list, and return only the ones which apply to the given context."""
        # We're expecting most _filters to have no overrides.
        applies_by_default = all(setting.applies(ctx) for setting in settings)

        relevant_filters = []
        for filter_ in filters:
            if (not filter_.settings and applies_by_default) or filter_.applies(ctx):
                relevant_filters.append(filter_)

        result = Settings()
        for filter_ in relevant_filters:
            if filter_.triggered_on(ctx):
                result |= filter_.settings

        return result

    @staticmethod
    def clean_input(string: str) -> str:
        """Remove zalgo and invisible characters from `string`."""
        # For future consideration: remove characters in the Mc, Sk, and Lm categories too.
        # Can be normalised with form C to merge char + combining char into a single char to avoid
        # removing legit diacritics, but this would open up a way to bypass _filters.
        no_zalgo = ZALGO_RE.sub("", string)
        return INVISIBLE_RE.sub("", no_zalgo)
