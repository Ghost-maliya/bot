import re

from bot.exts.filtering._filters.filter import Filter
from bot.exts.filtering._filter_context import FilterContext


class TokenFilter(Filter):
    """A filter which looks for a specific token given by regex."""

    description = ""

    def triggered_on(self, ctx: FilterContext) -> bool:
        """Searches for a regex pattern within a given context."""
        pattern = self.token
        if self.exact:
            if not pattern.startswith(r"\b"):
                pattern = "\b" + pattern
            if not pattern.endswith(r"\b"):
                pattern += "\b"

        return bool(re.search(pattern, ctx.content, flags=re.IGNORECASE))


