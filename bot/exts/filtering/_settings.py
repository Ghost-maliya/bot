from __future__ import annotations

from typing import Optional

from bot.exts.filtering._filter_context import FilterContext
from bot.exts.filtering._settings_types import settings_types
from bot.exts.filtering._settings_types.settings_entry import ActionEntry, ValidationEntry
from bot.log import get_logger

log = get_logger(__name__)


class Settings:
    """"""

    _already_warned: set[str] = set()

    def __init__(self, settings_data: dict):
        self._actions: dict[str, list[ActionEntry]] = {}
        self._validations: dict[str, list[ValidationEntry]] = {}

        for setting_name, value in settings_data.items():
            if setting_name in settings_types["action"]:
                self._actions[setting_name] = settings_types["action"][setting_name].create(value)
            elif setting_name in settings_types["validation"]:
                self._validations[setting_name] = settings_types["validation"][setting_name].create(value)
            elif setting_name not in self._already_warned:
                log.warning(f"A setting named {setting_name} was loaded from the database, but no matching class.")
                self._already_warned.add(setting_name)

    @classmethod
    def create(cls, settings_date: dict) -> Optional[Settings]:
        """
        Returns a Settings object from `settings_data` if it holds any value, None otherwise.

        Use this method to create Settings objects instead of the init.
        The None value is significant for how a filter list iterates over its filters.
        """
        settings = Settings(settings_date)
        # If an entry doesn't hold any values, its `create` method will return None.
        # If all entries are None, then the settings object holds no values.
        if not any(settings._actions) and not any(settings._validations):
            return None

        return settings

    def evaluate(self, ctx: FilterContext) -> tuple[dict[str, bool], dict[str, bool]]:
        """"""
        ...


