from discord import User
from discord.abc import GuildChannel

from dataclasses import dataclass, field


@dataclass
class FilterContext:
    # Input context
    event: str
    author: User
    channel: GuildChannel
    content: str
    embeds: list = field(default_factory=list)
    # Output context
    output_content: str = field(default_factory=str)
    output_embeds: list = field(default_factory=list)
