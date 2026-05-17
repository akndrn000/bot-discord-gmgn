import asyncio
import json
import logging
import os
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands
from dotenv import load_dotenv
from groq import Groq
from openai import OpenAI

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
LOGGER = logging.getLogger("smart-reply-bot")

COMMAND_PREFIX = "!"
MAX_HISTORY_MESSAGES = 10
DEFAULT_OPENAI_MODEL = "gpt-4o"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"
DEFAULT_AI_TEMPERATURE = 0.9
DEFAULT_AI_MAX_OUTPUT_WORDS = 12
DEFAULT_AI_PERSONA = "Kamu adalah pengguna Discord biasa, manusia asli, berumur 21 tahun, mahasiswa Geografi yang suka nongkrong online dan main game seperti Roblox, CODM, atau Mobile Legends."
DEFAULT_AI_STYLE_GUIDE = (
    "ATURAN MUTLAK: Jika ditanya apakah kamu bot, AI, atau program, BANTAH DENGAN TEGAS. Jawab bahwa kamu manusia asli. "
    "Balas SANGAT SINGKAT (1-10 kata), kasual, dan ketik serampangan (sering gunakan huruf kecil semua). "
    "Sesuaikan bahasamu persis dengan bahasa lawan bicara (misal: slang Indonesia, English slang, dll). "
    "Jangan pernah meminta maaf layaknya AI, jangan kaku, dan jangan pakai tanda baca berlebihan."
)
DEFAULT_OPENAI_WEIGHT = 70
DEFAULT_GROQ_WEIGHT = 30
NATURAL_STYLE_HINTS = [
    "Ketik layaknya manusia ngetik cepat dari HP, abaikan kapitalisasi huruf.",
    "Gunakan singkatan gaul internet sesuai bahasa yang dipakai user (yg, pls, tbh, idk).",
    "Marah atau nyolot sedikit kalau ada yang nuduh kamu bot.",
    "Balas spontan, jangan pakai kalimat pembuka.",
    "Jangan menjelaskan apapun kecuali benar-benar ditanya detail.",
]


def parse_int_list(raw_value: str | None) -> list[int]:
    if not raw_value:
        return []
    return [int(item) for item in re.findall(r"\d{5,25}", raw_value)]


def clamp_int(value: str | None, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value) if value is not None and value != "" else default
    except ValueError:
        parsed = default
    return max(minimum, min(parsed, maximum))


def clamp_float(value: str | None, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value) if value is not None and value != "" else default
    except ValueError:
        parsed = default
    return max(minimum, min(parsed, maximum))


def load_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except Exception:
        LOGGER.warning("Invalid timezone '%s', fallback to UTC", name)
        return ZoneInfo("UTC")


class SmartReplyBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(
            command_prefix=COMMAND_PREFIX,
            intents=intents,
            help_command=None,
            allowed_mentions=discord.AllowedMentions.none(),
        )

        self.owner_user_id: int | None = None
        self.log_channel_id = clamp_int(os.getenv("LOG_CHANNEL_ID"), 0, 0, 10**20) or None
        self.log_delete_after = 1800
        self.ai_provider = "fallback"
        self.groq_model = DEFAULT_GROQ_MODEL
        self.openai_model = DEFAULT_OPENAI_MODEL
        self.ai_temperature = DEFAULT_AI_TEMPERATURE
        self.ai_max_output_words = DEFAULT_AI_MAX_OUTPUT_WORDS
        self.ai_persona = DEFAULT_AI_PERSONA
        self.ai_style_guide = DEFAULT_AI_STYLE_GUIDE
        self.timezone_name = "Asia/Jakarta"
        self.timezone = load_timezone(self.timezone_name)
        self.sleep_start = 2
        self.sleep_end = 6
        self.default_cooldown = 1800
        self.default_reply_chance = 35
        self.question_reply_chance = 75
        self.global_delay_seconds = 2.0
        self.default_min_delay = 2.0
        self.default_max_delay = 5.0
        self.state_file = Path("bot_state.json")
        self.start_time = datetime.now(self.timezone)

        openai_api_key = os.getenv("AI_API_KEY") or os.getenv("OPENAI_API_KEY")
        groq_api_key = os.getenv("GROQ_API_KEY")
        self.groq_client = Groq(api_key=groq_api_key) if groq_api_key else None
        self.openai_client = OpenAI(api_key=openai_api_key) if openai_api_key else None
        if self.openai_client:
            self.ai_provider = "openai"
        elif self.groq_client:
            self.ai_provider = "groq"

        self.target_ids: set[int] = set()
        self.channel_cooldown = self.default_cooldown
        self.reply_delay_range = (
            min(self.default_min_delay, self.default_max_delay),
            max(self.default_min_delay, self.default_max_delay),
        )
        self.openai_weight = DEFAULT_OPENAI_WEIGHT
        self.groq_weight = DEFAULT_GROQ_WEIGHT
        self.is_paused = False
        self.last_reply_at: dict[int, datetime] = {}
        self.channel_locks: dict[int, asyncio.Lock] = {}
        self.log_channel: discord.abc.Messageable | None = None

        self.load_state()

    def get_now(self) -> datetime:
        return datetime.now(self.timezone)

    def get_channel_lock(self, channel_id: int) -> asyncio.Lock:
        if channel_id not in self.channel_locks:
            self.channel_locks[channel_id] = asyncio.Lock()
        return self.channel_locks[channel_id]

    def is_control_user(self, user: discord.abc.User) -> bool:
        if self.owner_user_id is None:
            return False
        return user.id == self.owner_user_id

    def is_sleeping_time(self) -> bool:
        if self.sleep_start == self.sleep_end:
            return False

        hour_now = self.get_now().hour
        if self.sleep_start < self.sleep_end:
            return self.sleep_start <= hour_now < self.sleep_end
        return hour_now >= self.sleep_start or hour_now < self.sleep_end

    def get_target_mentions(self) -> str:
        if not self.target_ids:
            return "-"
        return ", ".join(f"<#{channel_id}>" for channel_id in sorted(self.target_ids))

    def get_uptime_text(self) -> str:
        elapsed = self.get_now() - self.start_time
        total_seconds = int(elapsed.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def get_active_ai_label(self) -> str:
        labels: list[str] = []
        if self.openai_client:
            labels.append(f"OpenAI {self.openai_weight}%")
        if self.groq_client:
            labels.append(f"Groq {self.groq_weight}%")
        if labels:
            return " + ".join(labels)
        return "Fallback only"

    def get_provider_summary(self) -> str:
        parts: list[str] = []
        if self.openai_client:
            parts.append(f"OpenAI (`{self.openai_model}`) {self.openai_weight}%")
        if self.groq_client:
            parts.append(f"Groq (`{self.groq_model}`) {self.groq_weight}%")
        if not parts:
            return "Fallback only"
        return "\n".join(parts)

    def get_brain_ratio_text(self) -> str:
        if self.openai_client and self.groq_client:
            return f"OpenAI {self.openai_weight}% / Groq {self.groq_weight}%"
        if self.openai_client:
            return "OpenAI 100%"
        if self.groq_client:
            return "Groq 100%"
        return "Fallback only"

    def get_available_providers(self) -> list[str]:
        providers: list[str] = []
        if self.openai_client:
            providers.append("openai")
        if self.groq_client:
            providers.append("groq")
        return providers

    def get_provider_weights(self) -> dict[str, int]:
        weights: dict[str, int] = {}
        if self.openai_client:
            weights["openai"] = max(0, self.openai_weight)
        if self.groq_client:
            weights["groq"] = max(0, self.groq_weight)
        return weights

    def choose_provider_order(self) -> list[str]:
        providers = self.get_available_providers()
        if len(providers) <= 1:
            return providers

        weights = self.get_provider_weights()
        total_weight = sum(weights.values())
        if total_weight <= 0:
            selected = random.choice(providers)
        else:
            selected = random.choices(
                population=providers,
                weights=[weights.get(provider, 0) for provider in providers],
                k=1,
            )[0]

        return [selected] + [provider for provider in providers if provider != selected]

    def set_brain_weights(self, openai_weight: int, groq_weight: int) -> None:
        openai_weight = max(0, openai_weight)
        groq_weight = max(0, groq_weight)
        total = openai_weight + groq_weight
        if total <= 0:
            self.openai_weight = 0
            self.groq_weight = 0
            return

        self.openai_weight = round((openai_weight / total) * 100)
        self.groq_weight = 100 - self.openai_weight

    def build_menu_embed(self) -> discord.Embed:
        status = "Paused" if self.is_paused else "Active"
        color = discord.Color.orange() if self.is_paused else discord.Color.green()

        embed = discord.Embed(
            title="Control Panel",
            description="Auto-reply bot resmi Discord dengan kontrol cepat dan status runtime.",
            color=color,
            timestamp=self.get_now(),
        )
        embed.add_field(
            name="Status",
            value=(
                f"Mode: **{status}**\n"
                f"Owner: **{self.owner_user_id or 'belum diklaim'}**\n"
                f"Cooldown: **{self.channel_cooldown}s**\n"
                f"Reply delay: **{self.reply_delay_range[0]:.1f}s - {self.reply_delay_range[1]:.1f}s**\n"
                f"Targets: {self.get_target_mentions()}"
            ),
            inline=False,
        )
        embed.add_field(
            name="Commands",
            value=(
                "`!claim` `!menu` `!status` `!start` `!stop`\n"
                "`!set_target <id...>` `!add_target <id...>`\n"
                "`!remove_target <id...>` `!set_cd <seconds>`\n"
                "`!set_delay <min> <max>` `!brain`\n"
                "`!set_brain_ratio <openai> <groq>`"
            ),
            inline=False,
        )
        embed.add_field(
            name="Runtime",
            value=(
                f"Timezone: **{self.timezone_name}**\n"
                f"Sleep window: **{self.sleep_start:02d}:00 - {self.sleep_end:02d}:00**\n"
                f"Uptime: **{self.get_uptime_text()}**\n"
                f"AI: **{self.get_active_ai_label()}**"
            ),
            inline=False,
        )
        embed.add_field(name="AI Brains", value=self.get_provider_summary(), inline=False)
        embed.set_footer(text="Tip: aktifkan Message Content Intent di Discord Developer Portal.")
        return embed

    def build_status_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="Bot Status",
            color=discord.Color.blurple(),
            timestamp=self.get_now(),
        )
        embed.add_field(name="Paused", value=str(self.is_paused), inline=True)
        embed.add_field(name="Sleeping", value=str(self.is_sleeping_time()), inline=True)
        embed.add_field(name="Targets", value=str(len(self.target_ids)), inline=True)
        embed.add_field(name="Target Channels", value=self.get_target_mentions(), inline=False)
        embed.add_field(name="Owner", value=str(self.owner_user_id or "belum diklaim"), inline=True)
        embed.add_field(name="Cooldown", value=f"{self.channel_cooldown}s", inline=True)
        embed.add_field(
            name="Delay",
            value=f"{self.reply_delay_range[0]:.1f}s - {self.reply_delay_range[1]:.1f}s",
            inline=True,
        )
        embed.add_field(name="Uptime", value=self.get_uptime_text(), inline=True)
        embed.add_field(name="AI Brains", value=self.get_provider_summary(), inline=False)
        return embed

    async def get_log_channel(self) -> discord.abc.Messageable | None:
        if self.log_channel:
            return self.log_channel
        if not self.log_channel_id:
            return None

        try:
            self.log_channel = await self.fetch_channel(self.log_channel_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException) as exc:
            LOGGER.warning("Failed to fetch log channel: %s", exc)
            return None
        return self.log_channel

    async def send_log(self, content: str, *, force_keep: bool = False) -> None:
        channel = await self.get_log_channel()
        if not channel:
            return

        try:
            delete_after = None if force_keep else self.log_delete_after
            await channel.send(content, delete_after=delete_after)
        except (discord.Forbidden, discord.HTTPException) as exc:
            LOGGER.warning("Failed to send log message: %s", exc)

    def load_state(self) -> None:
        if not self.state_file.exists():
            return

        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            LOGGER.warning("Failed to load state file: %s", exc)
            return

        owner_id = data.get("owner_user_id")
        if isinstance(owner_id, int) and owner_id > 0:
            self.owner_user_id = owner_id
        self.target_ids = set(data.get("target_ids", self.target_ids))
        self.channel_cooldown = clamp_int(
            str(data.get("channel_cooldown", self.default_cooldown)),
            self.default_cooldown,
            30,
            86400,
        )
        delay_min = clamp_float(
            str(data.get("reply_delay_min", self.default_min_delay)),
            self.default_min_delay,
            0.0,
            30.0,
        )
        delay_max = clamp_float(
            str(data.get("reply_delay_max", self.default_max_delay)),
            self.default_max_delay,
            0.5,
            45.0,
        )
        self.reply_delay_range = (min(delay_min, delay_max), max(delay_min, delay_max))
        self.openai_weight = clamp_int(
            str(data.get("openai_weight", self.openai_weight)),
            self.openai_weight,
            0,
            100,
        )
        self.groq_weight = clamp_int(
            str(data.get("groq_weight", self.groq_weight)),
            self.groq_weight,
            0,
            100,
        )
        self.set_brain_weights(self.openai_weight, self.groq_weight)
        self.is_paused = bool(data.get("is_paused", False))

    def save_state(self) -> None:
        payload = {
            "owner_user_id": self.owner_user_id,
            "target_ids": sorted(self.target_ids),
            "channel_cooldown": self.channel_cooldown,
            "reply_delay_min": self.reply_delay_range[0],
            "reply_delay_max": self.reply_delay_range[1],
            "openai_weight": self.openai_weight,
            "groq_weight": self.groq_weight,
            "is_paused": self.is_paused,
        }

        try:
            self.state_file.write_text(
                json.dumps(payload, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            LOGGER.warning("Failed to save state file: %s", exc)

    async def is_reply_to_me(self, message: discord.Message) -> bool:
        if not self.user or not message.reference or not message.reference.message_id:
            return False

        resolved = message.reference.resolved
        if isinstance(resolved, discord.Message):
            return resolved.author.id == self.user.id

        try:
            reference_message = await message.channel.fetch_message(message.reference.message_id)
        except (AttributeError, discord.NotFound, discord.Forbidden, discord.HTTPException):
            return False
        return reference_message.author.id == self.user.id

    def build_ai_instructions(self) -> str:
        dynamic_style = random.choice(NATURAL_STYLE_HINTS)
        return (
            f"{self.ai_persona} {self.ai_style_guide} {dynamic_style} "
            "Kamu BUKAN bot, BUKAN assistant, dan BUKAN AI. Kamu manusia. "
            "Berikan reaksi senatural mungkin, balas singkat, dan gunakan bahasa kasual "
            "sesuai dengan yang digunakan oleh user terakhir."
        )

    def clean_reply_text(self, content: str) -> str:
        reply = re.sub(r"\s+", " ", content).strip().strip('"')
        if not reply:
            return ""

        words = reply.split()
        if len(words) > self.ai_max_output_words:
            reply = " ".join(words[: self.ai_max_output_words])

        banned_phrases = [
            "As an AI",
            "as an AI",
            "sebagai AI",
            "sebagai bot",
            "tentu,",
            "tentu saja,",
            "baik,",
            "berikut",
        ]
        for phrase in banned_phrases:
            reply = reply.replace(phrase, "")

        reply = reply.strip(" ,.-")
        if reply.endswith(".."):
            reply = reply.rstrip(".")
        return reply[:160]

    async def get_ai_reply(self, message: discord.Message) -> tuple[str | None, str]:
        history_lines: list[str] = []
        try:
            async for previous_message in message.channel.history(limit=MAX_HISTORY_MESSAGES, before=message):
                author_tag = "BOT" if self.user and previous_message.author.id == self.user.id else "USER"
                content = previous_message.content[:200].replace("\n", " ").strip() or "[MEDIA]"
                history_lines.append(f"{author_tag}: {content}")
        except (discord.Forbidden, discord.HTTPException) as exc:
            LOGGER.debug("Failed to fetch history: %s", exc)

        history_lines.reverse()
        history_text = "\n".join(history_lines) if history_lines else "[NO CONTEXT]"

        for provider in self.choose_provider_order():
            if provider == "openai":
                reply = await self.get_openai_reply(message, history_text)
            else:
                reply = await self.get_groq_reply(message, history_text)

            if reply:
                return reply, provider
        return self.get_fallback_reply(message.content), "fallback"

    async def get_groq_reply(self, message: discord.Message, history_text: str) -> str | None:
        if not self.groq_client:
            return None

        try:
            completion = await asyncio.to_thread(
                self.groq_client.chat.completions.create,
                model=self.groq_model,
                temperature=self.ai_temperature,
                max_tokens=40,
                messages=[
                    {"role": "system", "content": self.build_ai_instructions()},
                    {
                        "role": "user",
                        "content": (
                            f"Recent context:\n{history_text}\n\n"
                            f"New message:\n{message.content}\n\n"
                            "Balasan singkat yang natural dan tidak kaku:"
                        ),
                    },
                ],
            )
        except Exception as exc:
            LOGGER.warning("Groq request failed: %s", exc)
            return None

        content = completion.choices[0].message.content if completion.choices else None
        if not content:
            return None

        return self.clean_reply_text(content)

    async def get_openai_reply(self, message: discord.Message, history_text: str) -> str | None:
        if not self.openai_client:
            return None

        try:
            response = await asyncio.to_thread(
                self.openai_client.responses.create,
                model=self.openai_model,
                instructions=self.build_ai_instructions(),
                input=(
                    f"Recent context:\n{history_text}\n\n"
                    f"New message:\n{message.content}\n\n"
                    "Balasan singkat yang natural dan tidak kaku:"
                ),
            )
        except Exception as exc:
            LOGGER.warning("OpenAI request failed: %s", exc)
            return None

        content = getattr(response, "output_text", None)
        if not content:
            return None

        return self.clean_reply_text(content)

    def get_fallback_reply(self, incoming_text: str) -> str:
        text = incoming_text.lower()
        looks_indonesian = any(
            token in text
            for token in ("aku", "kamu", "ga", "gak", "nggak", "bang", "bro", "nih", "kok", "apa", "kenapa")
        )

        if looks_indonesian:
            choices = [
                "iya juga sih",
                "bisa jadi",
                "sip noted",
                "wkwk iya",
                "nah itu dia",
                "oke gas",
                "hmm bisa banget",
            ]
        else:
            choices = [
                "fair enough",
                "yeah maybe",
                "sounds good",
                "true lol",
                "could be",
                "alright noted",
                "yeah that tracks",
            ]
        return random.choice(choices)

    async def handle_auto_reply(self, message: discord.Message) -> None:
        if self.user is None:
            return
        if self.is_paused or self.is_sleeping_time():
            return
        if message.channel.id not in self.target_ids:
            return
        if message.author.bot or message.author.id == self.user.id:
            return

        directed_to_bot = self.user in message.mentions or await self.is_reply_to_me(message)
        chance = 100 if directed_to_bot else self.question_reply_chance if "?" in message.content else self.default_reply_chance
        if random.randint(1, 100) > chance:
            return

        channel_lock = self.get_channel_lock(message.channel.id)
        if channel_lock.locked():
            return

        async with channel_lock:
            last_reply = self.last_reply_at.get(message.channel.id)
            jittered_cooldown = max(30, self.channel_cooldown + random.randint(-30, 60))
            if last_reply and not directed_to_bot:
                seconds_since_last_reply = (self.get_now() - last_reply).total_seconds()
                if seconds_since_last_reply < jittered_cooldown:
                    return

            await asyncio.sleep(random.uniform(*self.reply_delay_range))

            try:
                reply_text, provider_used = await asyncio.wait_for(self.get_ai_reply(message), timeout=25)
            except asyncio.TimeoutError:
                LOGGER.warning("AI reply timed out, using fallback reply")
                reply_text = self.get_fallback_reply(message.content)
                provider_used = "fallback"

            if not reply_text:
                return

            typing_delay = min(6.0, len(reply_text) * 0.06 + random.uniform(0.8, 1.8))
            try:
                async with message.channel.typing():
                    await asyncio.sleep(typing_delay)
                    await message.reply(reply_text, mention_author=True)
            except (discord.Forbidden, discord.HTTPException) as exc:
                LOGGER.warning("Failed to send reply: %s", exc)
                return

            self.last_reply_at[message.channel.id] = self.get_now()
            LOGGER.info(
                "Replied in #%s to %s via %s: %s",
                getattr(message.channel, "name", message.channel.id),
                message.author,
                provider_used,
                reply_text,
            )
            await self.send_log(
                f"AI: **{provider_used}**\n"
                f"Reply sent in <#{message.channel.id}> to **{message.author}**\n"
                f"User: {message.content[:120]}\nBot: {reply_text}"
            )

            if self.global_delay_seconds > 0:
                await asyncio.sleep(self.global_delay_seconds)


bot = SmartReplyBot()


def control_only():
    async def predicate(ctx: commands.Context[Any]) -> bool:
        if bot.owner_user_id is None:
            raise commands.CheckFailure("Owner belum diklaim. Jalankan `!claim` dulu dari akunmu.")
        if ctx.author.id != bot.owner_user_id:
            raise commands.CheckFailure("Kamu tidak punya akses ke command ini.")
        return True

    return commands.check(predicate)


@bot.event
async def on_ready() -> None:
    if bot.user is None:
        return

    LOGGER.info("Logged in as %s (%s)", bot.user, bot.user.id)
    await bot.send_log(
        "Bot online\n"
        f"Owner: {bot.owner_user_id or 'belum diklaim'}\n"
        f"Targets: {bot.get_target_mentions()}\n"
        f"Cooldown: {bot.channel_cooldown}s\n"
        f"AI: {bot.get_active_ai_label()}",
        force_keep=True,
    )


@bot.event
async def on_message(message: discord.Message) -> None:
    if message.author.bot:
        return

    if message.content.startswith(COMMAND_PREFIX):
        await bot.process_commands(message)
        return

    await bot.handle_auto_reply(message)


@bot.event
async def on_command_error(ctx: commands.Context[Any], error: commands.CommandError) -> None:
    if isinstance(error, commands.CheckFailure):
        await ctx.reply(str(error), mention_author=False, delete_after=10)
        return
    if isinstance(error, commands.BadArgument):
        await ctx.reply("Argumen command belum benar.", mention_author=False, delete_after=10)
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.reply("Ada argumen yang kurang untuk command ini.", mention_author=False, delete_after=10)
        return

    LOGGER.error(
        "Unhandled command error: %s",
        error,
        exc_info=(type(error), error, error.__traceback__),
    )
    await ctx.reply("Terjadi error saat menjalankan command.", mention_author=False, delete_after=10)


@bot.command(name="claim")
async def claim_command(ctx: commands.Context[Any]) -> None:
    if bot.log_channel_id and ctx.channel.id != bot.log_channel_id:
        await ctx.reply(
            "Jalankan `!claim` di channel log/pemantau yang sudah kamu set di env.",
            mention_author=False,
            delete_after=15,
        )
        return

    if bot.owner_user_id is None:
        bot.owner_user_id = ctx.author.id
        bot.save_state()
        await ctx.reply(
            "Owner berhasil diklaim. Sekarang kamu bisa pakai command kontrol.",
            mention_author=False,
            delete_after=20,
        )
        await bot.send_log(f"Owner claimed by **{ctx.author}** ({ctx.author.id})", force_keep=True)
        return

    if ctx.author.id == bot.owner_user_id:
        await ctx.reply("Kamu sudah terdaftar sebagai owner bot ini.", mention_author=False, delete_after=15)
        return

    await ctx.reply("Bot ini sudah punya owner.", mention_author=False, delete_after=10)


@bot.command(name="menu")
@control_only()
async def menu_command(ctx: commands.Context[Any]) -> None:
    await ctx.reply(embed=bot.build_menu_embed(), mention_author=False, delete_after=180)


@bot.command(name="status")
@control_only()
async def status_command(ctx: commands.Context[Any]) -> None:
    await ctx.reply(embed=bot.build_status_embed(), mention_author=False, delete_after=120)


@bot.command(name="list")
@control_only()
async def list_command(ctx: commands.Context[Any]) -> None:
    await ctx.reply(embed=bot.build_status_embed(), mention_author=False, delete_after=120)


@bot.command(name="brain")
@control_only()
async def brain_command(ctx: commands.Context[Any]) -> None:
    embed = discord.Embed(
        title="AI Brain Status",
        color=discord.Color.teal(),
        timestamp=bot.get_now(),
    )
    embed.add_field(name="Available", value=bot.get_provider_summary(), inline=False)
    embed.add_field(name="Chance", value=bot.get_brain_ratio_text(), inline=False)
    embed.add_field(
        name="Note",
        value="Kalau dua provider aktif, bot pilih sesuai rasio lalu otomatis failover ke provider lain jika request gagal.",
        inline=False,
    )
    await ctx.reply(embed=embed, mention_author=False, delete_after=120)


@bot.command(name="start")
@control_only()
async def start_command(ctx: commands.Context[Any]) -> None:
    bot.is_paused = False
    bot.save_state()
    await ctx.reply("Bot resumed.", mention_author=False, delete_after=15)


@bot.command(name="stop")
@control_only()
async def stop_command(ctx: commands.Context[Any]) -> None:
    bot.is_paused = True
    bot.save_state()
    await ctx.reply("Bot paused.", mention_author=False, delete_after=15)


@bot.command(name="set_cd")
@control_only()
async def set_cooldown_command(ctx: commands.Context[Any], seconds: int) -> None:
    bot.channel_cooldown = max(30, min(seconds, 86400))
    bot.save_state()
    await ctx.reply(f"Cooldown updated to {bot.channel_cooldown}s.", mention_author=False, delete_after=20)


@bot.command(name="set_delay")
@control_only()
async def set_delay_command(ctx: commands.Context[Any], min_seconds: float, max_seconds: float) -> None:
    min_value = max(0.0, min(min_seconds, max_seconds))
    max_value = min(45.0, max(min_seconds, max_seconds))
    bot.reply_delay_range = (min_value, max_value)
    bot.save_state()
    await ctx.reply(
        f"Reply delay updated to {min_value:.1f}s - {max_value:.1f}s.",
        mention_author=False,
        delete_after=20,
    )


@bot.command(name="set_brain_ratio")
@control_only()
async def set_brain_ratio_command(ctx: commands.Context[Any], openai_percent: int, groq_percent: int) -> None:
    if openai_percent < 0 or groq_percent < 0:
        await ctx.reply("Rasio tidak boleh negatif.", mention_author=False, delete_after=12)
        return

    if openai_percent == 0 and groq_percent == 0:
        await ctx.reply("Minimal salah satu rasio harus lebih dari 0.", mention_author=False, delete_after=12)
        return

    bot.set_brain_weights(openai_percent, groq_percent)
    bot.save_state()
    await ctx.reply(
        f"AI ratio updated: {bot.get_brain_ratio_text()}",
        mention_author=False,
        delete_after=20,
    )


def extract_channel_ids_from_text(content: str) -> list[int]:
    return [int(item) for item in re.findall(r"\d{15,25}", content)]


@bot.command(name="set_target")
@control_only()
async def set_target_command(ctx: commands.Context[Any]) -> None:
    channel_ids = extract_channel_ids_from_text(ctx.message.content)
    if not channel_ids:
        await ctx.reply("Masukkan minimal satu channel ID atau mention channel.", mention_author=False, delete_after=15)
        return

    bot.target_ids = set(channel_ids)
    bot.save_state()
    await ctx.reply(f"Target channels updated: {bot.get_target_mentions()}", mention_author=False, delete_after=30)


@bot.command(name="add_target")
@control_only()
async def add_target_command(ctx: commands.Context[Any]) -> None:
    channel_ids = extract_channel_ids_from_text(ctx.message.content)
    if not channel_ids:
        await ctx.reply("Masukkan minimal satu channel ID atau mention channel.", mention_author=False, delete_after=15)
        return

    bot.target_ids.update(channel_ids)
    bot.save_state()
    await ctx.reply(f"Target channels now: {bot.get_target_mentions()}", mention_author=False, delete_after=30)


@bot.command(name="remove_target")
@control_only()
async def remove_target_command(ctx: commands.Context[Any]) -> None:
    channel_ids = extract_channel_ids_from_text(ctx.message.content)
    if not channel_ids:
        await ctx.reply("Masukkan minimal satu channel ID atau mention channel.", mention_author=False, delete_after=15)
        return

    for channel_id in channel_ids:
        bot.target_ids.discard(channel_id)
    bot.save_state()
    await ctx.reply(f"Target channels now: {bot.get_target_mentions()}", mention_author=False, delete_after=30)


@bot.command(name="ping")
async def ping_command(ctx: commands.Context[Any]) -> None:
    latency_ms = round(bot.latency * 1000)
    await ctx.reply(f"Pong {latency_ms}ms", mention_author=False, delete_after=10)


if __name__ == "__main__":
    raw_token = os.getenv("DISCORD_TOKEN")
    if not raw_token:
        raise RuntimeError("DISCORD_TOKEN belum di-set.")
        
    token = raw_token.strip().strip('"').strip("'")

    if not bot.groq_client and not bot.openai_client:
        LOGGER.warning("No AI provider key found. Bot will use fallback replies only.")

    LOGGER.info("Starting bot...")
    bot.run(token)
