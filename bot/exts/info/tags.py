from __future__ import annotations

import enum
import logging
import re
import time
from pathlib import Path
from typing import Callable, Iterable, List, Literal, NamedTuple, Optional, Union

import discord
import frontmatter
from discord import Embed, Member
from discord.ext.commands import Cog, Context, group

from bot import constants
from bot.bot import Bot
from bot.converters import TagNameConverter
from bot.pagination import LinePaginator
from bot.utils.messages import wait_for_deletion

log = logging.getLogger(__name__)

TEST_CHANNELS = (
    constants.Channels.bot_commands,
    constants.Channels.helpers
)

REGEX_NON_ALPHABET = re.compile(r"[^a-z]", re.MULTILINE & re.IGNORECASE)
FOOTER_TEXT = f"To show a tag, type {constants.Bot.prefix}tags <tagname>."


class COOLDOWN(enum.Enum):
    """Sentinel value to signal that a tag is on cooldown."""

    obj = object()


class TagIdentifier(NamedTuple):
    """Stores the group and name used as an identifier for a tag."""

    group: Optional[str]
    name: str

    def get_fuzzy_score(self, fuzz_tag_identifier: TagIdentifier) -> float:
        """Get fuzzy score, using `fuzz_tag_identifier` as the identifier to fuzzy match with."""
        if self.group is None:
            if fuzz_tag_identifier.group is None:
                # We're only fuzzy matching the name
                group_score = 1
            else:
                # Ignore tags without groups if the identifier contains a group
                return .0
        else:
            if fuzz_tag_identifier.group is None:
                # Ignore tags with groups if the identifier does not have a group
                return .0
            else:
                group_score = _fuzzy_search(fuzz_tag_identifier.group, self.group)

        fuzzy_score = group_score * _fuzzy_search(fuzz_tag_identifier.name, self.name) * 100
        if fuzzy_score:
            log.trace(f"Fuzzy score {fuzzy_score:=06.2f} for tag {self!r} with fuzz {fuzz_tag_identifier!r}")
        return fuzzy_score

    def __str__(self) -> str:
        return f"{self.group or ''} {self.name}"


class Tag:
    """Provide an interface to a tag from resources with `file_content`."""

    def __init__(self, file_content: str):
        post = frontmatter.loads(file_content)
        self.content = post.content
        self.metadata = post.metadata
        self._restricted_to: set[int] = set(self.metadata.get("restricted_to", ()))
        self._cooldowns: dict[discord.TextChannel, float] = {}

    @property
    def embed(self) -> Embed:
        """Create an embed for the tag."""
        embed = Embed.from_dict(self.metadata.get("embed", {}))
        embed.description = self.content
        return embed

    def accessible_by(self, member: discord.Member) -> bool:
        """Check whether `member` can access the tag."""
        return bool(
            not self._restricted_to
            or self._restricted_to & {role.id for role in member.roles}
        )

    def on_cooldown_in(self, channel: discord.TextChannel) -> bool:
        """Check whether the tag is on cooldown in `channel`."""
        return channel in self._cooldowns and self._cooldowns[channel] > time.time()

    def set_cooldown_for(self, channel: discord.TextChannel) -> None:
        """Set the tag to be on cooldown in `channel` for `constants.Cooldowns.tags` seconds."""
        self._cooldowns[channel] = time.time() + constants.Cooldowns.tags


def _fuzzy_search(search: str, target: str) -> float:
    """A simple scoring algorithm based on how many letters are found / total, with order in mind."""
    current, index = 0, 0
    _search = REGEX_NON_ALPHABET.sub("", search.lower())
    _targets = iter(REGEX_NON_ALPHABET.split(target.lower()))
    _target = next(_targets)
    try:
        while True:
            while index < len(_target) and _search[current] == _target[index]:
                current += 1
                index += 1
            index, _target = 0, next(_targets)
    except (StopIteration, IndexError):
        pass
    return current / len(_search)


class Tags(Cog):
    """Save new tags and fetch existing tags."""

    def __init__(self, bot: Bot):
        self.bot = bot
        self._tags: dict[TagIdentifier, Tag] = {}
        self.initialize_tags()

    def initialize_tags(self) -> None:
        """Load all tags from resources into `self._tags`."""
        base_path = Path("bot", "resources", "tags")

        for file in base_path.glob("**/*"):
            if file.is_file():
                parent_dir = file.relative_to(base_path).parent

                tag_name = file.stem
                tag_group = parent_dir.name if parent_dir.name else None

                self._tags[TagIdentifier(tag_group, tag_name)] = Tag(file.read_text("utf-8"))

    def _get_suggestions(
            self,
            tag_identifier: TagIdentifier,
            thresholds: Optional[list[int]] = None
    ) -> list[tuple[TagIdentifier, Tag]]:
        """Return a list of suggested tags for `tag_identifier`."""
        thresholds = thresholds or [100, 90, 80, 70, 60]

        for threshold in thresholds:
            suggestions = [
                (identifier, tag)
                for identifier, tag in self._tags.items()
                if identifier.get_fuzzy_score(tag_identifier) >= threshold
            ]
            if suggestions:
                return suggestions

        return []

    def get_fuzzy_matches(self, tag_identifier: TagIdentifier) -> list[tuple[TagIdentifier, Tag]]:
        """Get tags with identifiers similar to `tag_identifier`."""
        if tag_identifier.group is None:
            suggestions = self._get_suggestions(tag_identifier)
        else:
            # Try fuzzy matching with only a name first
            suggestions = self._get_suggestions(TagIdentifier(None, tag_identifier.group))
            suggestions += self._get_suggestions(tag_identifier)
        return suggestions

    def _get_tags_via_content(self, check: Callable[[Iterable], bool], keywords: str, user: Member) -> list:
        """
        Search for tags via contents.

        `predicate` will be the built-in any, all, or a custom callable. Must return a bool.
        """
        keywords_processed: List[str] = []
        for keyword in keywords.split(','):
            keyword_sanitized = keyword.strip().casefold()
            if not keyword_sanitized:
                # this happens when there are leading / trailing / consecutive comma.
                continue
            keywords_processed.append(keyword_sanitized)

        if not keywords_processed:
            # after sanitizing, we can end up with an empty list, for example when keywords is ','
            # in that case, we simply want to search for such keywords directly instead.
            keywords_processed = [keywords]

        matching_tags = []
        for tag in self._cache.values():
            matches = (query in tag['embed']['description'].casefold() for query in keywords_processed)
            if self.check_accessibility(user, tag) and check(matches):
                matching_tags.append(tag)

        return matching_tags

    async def _send_matching_tags(self, ctx: Context, keywords: str, matching_tags: list) -> None:
        """Send the result of matching tags to user."""
        if not matching_tags:
            pass
        elif len(matching_tags) == 1:
            await ctx.send(embed=Embed().from_dict(matching_tags[0]['embed']))
        else:
            is_plural = keywords.strip().count(' ') > 0 or keywords.strip().count(',') > 0
            embed = Embed(
                title=f"Here are the tags containing the given keyword{'s' * is_plural}:",
                description='\n'.join(tag['title'] for tag in matching_tags[:10])
            )
            await LinePaginator.paginate(
                sorted(f"**»**   {tag['title']}" for tag in matching_tags),
                ctx,
                embed,
                footer_text=FOOTER_TEXT,
                empty=False,
                max_lines=15
            )

    @group(name='tags', aliases=('tag', 't'), invoke_without_command=True)
    async def tags_group(
            self,
            ctx: Context,
            tag_name_or_group: TagNameConverter = None,
            tag_name: TagNameConverter = None,
    ) -> None:
        """Show all known tags, a single tag, or run a subcommand."""
        await self.get_command(ctx, tag_name_or_group=tag_name_or_group, tag_name=tag_name)

    @tags_group.group(name='search', invoke_without_command=True)
    async def search_tag_content(self, ctx: Context, *, keywords: str) -> None:
        """
        Search inside tags' contents for tags. Allow searching for multiple keywords separated by comma.

        Only search for tags that has ALL the keywords.
        """
        matching_tags = self._get_tags_via_content(all, keywords, ctx.author)
        await self._send_matching_tags(ctx, keywords, matching_tags)

    @search_tag_content.command(name='any')
    async def search_tag_content_any_keyword(self, ctx: Context, *, keywords: Optional[str] = 'any') -> None:
        """
        Search inside tags' contents for tags. Allow searching for multiple keywords separated by comma.

        Search for tags that has ANY of the keywords.
        """
        matching_tags = self._get_tags_via_content(any, keywords or 'any', ctx.author)
        await self._send_matching_tags(ctx, keywords, matching_tags)

    async def get_tag_embed(
            self,
            ctx: Context,
            tag_identifier: TagIdentifier,
    ) -> Optional[Union[Embed, Literal[COOLDOWN.obj]]]:
        """
        Generate an embed of the requested tag or of suggestions if the tag doesn't exist/isn't accessible by the user.

        If the requested tag is on cooldown or no suggestions were found, return None.
        """
        if (tag := self._tags.get(tag_identifier)) is not None and tag.accessible_by(ctx.author):

            if tag.on_cooldown_in(ctx.channel):
                log.debug(f"Tag {str(tag_identifier)!r} is on cooldown.")
                return COOLDOWN.obj
            tag.set_cooldown_for(ctx.channel)

            self.bot.stats.incr(
                f"tags.usages"
                f"{'.' + tag_identifier.group.replace('-', '_') if tag_identifier.group else ''}"
                f".{tag_identifier.name.replace('-', '_')}"
            )
            return tag.embed

        elif len(tag_identifier.name) >= 3:
            suggested_tags = self.get_fuzzy_matches(tag_identifier)[:10]
            if not suggested_tags:
                return None
            suggested_tags_text = "\n".join(
                str(identifier)
                for identifier, tag in suggested_tags
                if tag.accessible_by(ctx.author)
                and not tag.on_cooldown_in(ctx.channel)
            )
            return Embed(
                title="Did you mean ...",
                description=suggested_tags_text
            )

    async def list_all_tags(self, ctx: Context) -> None:
        """Send a paginator with all loaded tags accessible by `ctx.author`, groups first, and alphabetically sorted."""
        def tag_sort_key(tag_item: tuple[TagIdentifier, tag]) -> str:
            ident = tag_item[0]
            if ident.group is None:
                # Max codepoint character to force tags without a group to the end
                group = chr(0x10ffff)
            else:
                group = ident.group
            return group+ident.name

        result_lines = []
        current_group = object()
        group_accessible = True

        for identifier, tag in sorted(self._tags.items(), key=tag_sort_key):

            if identifier.group != current_group:
                if not group_accessible:
                    # Remove group separator line if no tags in the previous group were accessible by the user.
                    result_lines.pop()
                # A new group began, add a separator with the group name.
                if identifier.group is not None:
                    group_accessible = False
                    result_lines.append(f"\n\N{BULLET} **{identifier.group}**")
                else:
                    result_lines.append("\n\N{BULLET}")
                current_group = identifier.group

            if tag.accessible_by(ctx.author):
                result_lines.append(f"**\N{RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK}** {identifier.name}")
                group_accessible = True

        embed = Embed(title="Current tags")
        await LinePaginator.paginate(result_lines, ctx, embed=embed, max_lines=15, empty=False, footer_text=FOOTER_TEXT)

    @tags_group.command(name='get', aliases=('show', 'g'))
    async def get_command(
            self, ctx: Context,
            tag_name_or_group: TagNameConverter = None,
            tag_name: TagNameConverter = None,
    ) -> bool:
        """
        Get a specified tag, or a list of all tags if no tag is specified.

        Returns True if something was sent, or if the tag is on cooldown.
        Returns False if no message was sent.
        """
        if tag_name_or_group is None and tag_name is None:
            if self._tags:
                await self.list_all_tags(ctx)
                return True
            else:
                await ctx.send(embed=Embed(description="**There are no tags!**"))
                return True

        if tag_name is None:
            tag_name = tag_name_or_group
            tag_group = None
        else:
            tag_group = tag_name_or_group

        embed = await self.get_tag_embed(ctx, TagIdentifier(tag_group, tag_name))
        if embed is not None:
            if embed is not COOLDOWN.obj:
                await wait_for_deletion(
                    await ctx.send(embed=embed),
                    (ctx.author.id,)
                )
            return True
        else:
            return False


def setup(bot: Bot) -> None:
    """Load the Tags cog."""
    bot.add_cog(Tags(bot))


def extract_tag_identifier(string: str) -> TagIdentifier:
    """Create a `TagIdentifier` instance from beginning of `string`."""
    split_string = string.removeprefix(constants.Bot.prefix).split(" ", maxsplit=2)
    if len(split_string) == 1:
        return TagIdentifier(None, split_string[0])
    else:
        return TagIdentifier(split_string[0], split_string[1])
