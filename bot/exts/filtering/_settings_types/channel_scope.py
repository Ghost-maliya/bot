from typing import Any

from bot.exts.filtering._filter_context import FilterContext
from bot.exts.filtering._settings_types.settings_entry import ValidationEntry


class ChannelScope(ValidationEntry):
    """A setting entry which tells whether the filter was invoked in a whitelisted channel or category."""

    name = "channel_scope"
    description = "The channels and categories the filter should apply in."

    def __init__(self, entry_data: Any):
        if entry_data["allowed_channels"]:
            self.disabled_channels = set(entry_data["allowed_channels"])
        else:
            self.disabled_channels = set()

        if entry_data["allowed_categories"]:
            self.disabled_categories = set(entry_data["allowed_categories"])
        else:
            self.disabled_categories = set()

        if entry_data["disallowed_channels"]:
            self.enabled_channels = set(entry_data["disallowed_channels"])
        else:
            self.enabled_channels = set()

    def triggers_on(self, ctx: FilterContext) -> bool:
        """
        Return whether the filter should be triggered in the given channel.

        The filter is invoked by default.
        If the channel is explicitly enabled, it bypasses the set disabled channels and categories.
        """
        return (
                ctx.channel.id in self.enabled_channels
                or (
                        ctx.channel.id not in self.disabled_channels
                        and (not ctx.channel.category or ctx.channel.category not in self.disabled_categories)
                )
        )
