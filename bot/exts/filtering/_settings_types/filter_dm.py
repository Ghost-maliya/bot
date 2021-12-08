from typing import Any

from bot.exts.filtering._filter_context import FilterContext
from bot.exts.filtering._settings_types.settings_entry import ValidationEntry


class RoleBypass(ValidationEntry):
    """A setting entry which tells whether to apply the filter to DMs."""

    name = "filter_dm"
    description = "Whether to apply the filter to DMs."

    def __init__(self, entry_data: Any):
        self.apply_in_dm = entry_data

    def triggers_on(self, ctx: FilterContext) -> bool:
        """Return whether the filter should be triggered even if it was triggered in DMs."""
        return ctx.guild is not None or self.apply_in_dm
