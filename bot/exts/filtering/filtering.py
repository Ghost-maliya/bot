from discord.ext.commands import Cog

from bot.bot import Bot
from bot.utils import scheduling
from bot.exts.filtering._filter_lists import filter_list_types, FilterList
from bot.log import get_logger


log = get_logger(__name__)


class Filtering(Cog):
    """"""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.filter_lists: dict[str, FilterList] = {}
        self.init_task = scheduling.create_task(self.init_cog(), event_loop=self.bot.loop)

    async def init_cog(self) -> None:
        """"""
        await self.bot.wait_until_guild_available()
        already_warned = set()

        raw_filter_lists = await self.bot.api_client.get("bot/filter/filter_lists")
        for raw_filter_list in raw_filter_lists:
            list_name = raw_filter_list["name"]
            if list_name not in self.filter_lists:
                if list_name not in filter_list_types and list_name not in already_warned:
                    log.warning(f"A filter list named {list_name} was loaded from the database, but no matching class.")
                    already_warned.add(list_name)
                    continue
                self.filter_lists[list_name] = filter_list_types[list_name]()
            self.filter_lists[list_name].add_list(raw_filter_list)


def setup(bot: Bot) -> None:
    """Load the DuckPond cog."""
    bot.add_cog(Filtering(bot))
