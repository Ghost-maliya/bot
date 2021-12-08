from typing import Any

from discord.abc import Member

from bot.exts.filtering._filter_context import FilterContext
from bot.exts.filtering._settings_types.settings_entry import ValidationEntry


class RoleBypass(ValidationEntry):
    """A setting entry which tells whether the roles the member has allow them to bypass the filter."""

    name = "bypass_roles"
    description = "Which roles allow the member to ignore the filter."

    def __init__(self, entry_data: Any):
        self.roles = set(entry_data)

    def triggers_on(self, ctx: FilterContext) -> bool:
        """Return whether the filter should be triggered on this user given their roles."""
        if not isinstance(ctx.author, Member):
            return True
        return all(member_role.id not in self.roles for member_role in ctx.author.roles)
