"""Pembuatan client Discord dan event handler tipis.

Seluruh logika (parsing, jadwal, pengiriman) tinggal di modul lain;
modul ini hanya melakukan wiring I/O.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Awaitable, Callable

# === PATCH ANTI CRASH DISCORD GATEWAY (dipertahankan dari kode lama) ===
import discord.state

original_parse_ready_supplemental = discord.state.ConnectionState.parse_ready_supplemental


def patched_parse_ready_supplemental(self: Any, data: Any) -> None:
    if data and data.get("pending_payments") is None:
        data["pending_payments"] = []
    try:
        original_parse_ready_supplemental(self, data)
    except Exception:
        pass


discord.state.ConnectionState.parse_ready_supplemental = patched_parse_ready_supplemental
# ======================================================================

from discord.ext import commands, tasks  # noqa: E402

from gmgn_bot.logging_setup import get_logger  # noqa: E402
from gmgn_bot.messages import (  # noqa: E402
    GM_WEIGHTED_MESSAGES,
    GN_WEIGHTED_MESSAGES,
    get_menu_text,
)
from gmgn_bot.scheduler import (  # noqa: E402
    GM_AUTO_LABEL,
    LOOP_INTERVAL_SECONDS,
    SchedulerState,
    due_labels,
    resolve_timezone,
)

logger = get_logger("client")

COMMAND_PREFIX = "!"


def create_bot() -> commands.Bot:
    """Buat self-bot dengan prefix ``!`` (sama seperti kode lama)."""
    return commands.Bot(command_prefix=COMMAND_PREFIX, self_bot=True)


async def send_log(bot: Any, monitor_channel_id: int, message_text: str) -> None:
    """Cetak log ke console dan teruskan ke channel pemantau."""
    logger.info(message_text)
    if monitor_channel_id != 0:
        try:
            channel = bot.get_channel(monitor_channel_id) or await bot.fetch_channel(
                monitor_channel_id
            )
            if channel:
                await channel.send(message_text)
        except Exception as e:
            logger.error(f"Gagal mengirim log ke channel pemantau: {e}")


def register_events(bot: commands.Bot, monitor_channel_id: int, scheduler_loop: tasks.Loop) -> None:
    """Pasang handler ``on_ready`` dan ``on_message`` (filter sama)."""

    @bot.event
    async def on_ready() -> None:
        logger.info(f"[✅] Login sebagai {bot.user}")
        await send_log(bot, monitor_channel_id, get_menu_text())
        if not scheduler_loop.is_running():
            scheduler_loop.start()

    @bot.event
    async def on_message(message: Any) -> None:
        if message.author.id != bot.user.id:
            return
        if monitor_channel_id != 0 and message.channel.id != monitor_channel_id:
            return

        ctx = await bot.get_context(message)
        if ctx.valid:
            await bot.invoke(ctx)


def register_scheduler(
    bot: commands.Bot,
    config: dict[str, Any],
    state: SchedulerState,
    broadcast: Callable[..., Awaitable[None]],
    timezone_name: str,
) -> tasks.Loop:
    """Pasang loop pengecekan jadwal tiap 20 detik; kembalikan loop-nya."""

    @tasks.loop(seconds=LOOP_INTERVAL_SECONDS)
    async def gm_gn_scheduler() -> None:
        tz = resolve_timezone(timezone_name)

        now = datetime.now(tz)
        today = now.strftime("%Y-%m-%d")

        for label in due_labels(config, now.hour, now.minute, today, state):
            messages = GM_WEIGHTED_MESSAGES if label == GM_AUTO_LABEL else GN_WEIGHTED_MESSAGES
            await broadcast(messages, label)

    return gm_gn_scheduler


__all__ = [
    "COMMAND_PREFIX",
    "GM_AUTO_LABEL",
    "create_bot",
    "register_events",
    "register_scheduler",
    "send_log",
]
