from abc import abstractmethod
from typing import Dict

from bot.exts.filtering._filter_context import FilterContext
from bot.exts.filtering._settings import Settings
from bot.exts.filtering._utils import FieldRequiring


class Filter(FieldRequiring):
    """
    A class representing a filter.

    Each filter looks for a specific attribute within an event (such as message sent),
    and defines what action should be performed if it is triggered.
    """

    # Each subclass must define a description of what the filter does, to be displayed in the UI.
    description = FieldRequiring.MUST_SET

    def __init__(self, filter_data: Dict):
        self.token = filter_data["content"]
        self.description = filter_data["description"]
        self.settings = Settings(filter_data["settings"])
        self.exact = filter_data["additional_field"]

    def applies(self, ctx: FilterContext) -> bool:
        """Return True if the filter's settings make it apply to the given context, False otherwise."""
        return all(setting.applies(ctx) for setting in self.settings)

    @abstractmethod
    def triggered_on(self, ctx: FilterContext) -> bool:
        """Searches for `self.token` within a given context."""
