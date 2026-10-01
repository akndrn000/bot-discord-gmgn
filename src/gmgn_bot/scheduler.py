"""Logika penjadwalan dan pengiriman berkala pesan GM/GN.

Aturan kirim sama persis dengan kode lama: pesan dikirim bila waktu
sekarang berada dalam jendela 0--15 menit setelah jadwal dan belum
pernah dikirim pada tanggal tersebut.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import pytz

from gmgn_bot.logging_setup import get_logger
from gmgn_bot.messages import get_random_message

logger = get_logger("scheduler")

LOOP_INTERVAL_SECONDS = 20
SEND_WINDOW_MINUTES = 15
BROADCAST_DELAY_MIN_SECONDS = 2
BROADCAST_DELAY_MAX_SECONDS = 5

FALLBACK_TIMEZONE = "Asia/Jakarta"

GM_AUTO_LABEL = "GM (Otomatis)"
GN_AUTO_LABEL = "GN (Otomatis)"

SendLog = Callable[[str], Awaitable[None]]


@dataclass
class SchedulerState:
    """Tanggal terakhir pesan otomatis terkirim (pencegah kirim ganda)."""

    last_sent_gm_date: str | None = None
    last_sent_gn_date: str | None = None


def resolve_timezone(name: str) -> Any:
    """Kembalikan zona waktu *name*; fallback ke Jakarta bila tidak valid."""
    try:
        return pytz.timezone(name)
    except Exception:
        return pytz.timezone(FALLBACK_TIMEZONE)


def should_send(
    target_time: str | None,
    now_hour: int,
    now_minute: int,
    last_sent_date: str | None,
    today: str,
) -> bool:
    """Tentukan apakah jadwal *target_time* ("HH:MM") jatuh tempo sekarang."""
    if target_time and last_sent_date != today:
        target_h, target_m = map(int, target_time.split(":"))
        elapsed = (now_hour * 60 + now_minute) - (target_h * 60 + target_m)
        if 0 <= elapsed <= SEND_WINDOW_MINUTES:
            return True
    return False


def due_labels(
    config: dict[str, Any],
    now_hour: int,
    now_minute: int,
    today: str,
    state: SchedulerState,
) -> list[str]:
    """Kembalikan label yang jatuh tempo (GM lalu GN) dan tandai terkirim.

    Penandaan dilakukan sebelum pengiriman, sama seperti kode lama.
    Bila tidak ada target channel, tidak ada yang ditandai/dikirim.
    """
    channels = config.get("target_channels", [])
    if not channels:
        return []

    due: list[str] = []
    if should_send(config.get("gm_time"), now_hour, now_minute, state.last_sent_gm_date, today):
        state.last_sent_gm_date = today
        due.append(GM_AUTO_LABEL)
    if should_send(config.get("gn_time"), now_hour, now_minute, state.last_sent_gn_date, today):
        state.last_sent_gn_date = today
        due.append(GN_AUTO_LABEL)
    return due


async def broadcast(
    get_channel: Callable[[int], Any],
    fetch_channel: Callable[[int], Awaitable[Any]],
    send_log: SendLog,
    config: dict[str, Any],
    weighted_messages: list[tuple[str, int]],
    label: str,
) -> None:
    """Kirim pesan acak berbobot ke semua target channel lalu laporkan."""
    targets = config.get("target_channels", [])
    if not targets:
        await send_log(f"⚠️ [BROADCAST {label}] Gagal: Tidak ada target channel terdaftar.")
        return

    await send_log(f"🚀 Memulai pengiriman **{label}** ke `{len(targets)}` channel...")
    success_count = 0
    failed_channels: list[str] = []
    sent_details: list[str] = []

    for cid in targets:
        try:
            ch = get_channel(cid) or await fetch_channel(cid)
            if ch:
                await asyncio.sleep(
                    random.randint(BROADCAST_DELAY_MIN_SECONDS, BROADCAST_DELAY_MAX_SECONDS)
                )
                msg = get_random_message(weighted_messages)
                await ch.send(msg)
                success_count += 1

                channel_name = getattr(ch, "name", str(cid))
                sent_details.append(f"• <#{cid}> (`#{channel_name}`): `{msg}`")
            else:
                failed_channels.append(str(cid))
        except Exception as e:
            failed_channels.append(str(cid))
            logger.error(f"Gagal kirim ke channel {cid}: {e}")

    report_msg = (
        f"📊 **LAPORAN BROADCAST: {label}**\n"
        f"• Status: Selesai (`{success_count}/{len(targets)}` berhasil)\n\n"
        f"📝 **Detail Pesan Terkirim:**\n"
        + ("\n".join(sent_details) if sent_details else "Tidak ada pesan terkirim.")
    )

    if failed_channels:
        report_msg += f"\n\n⚠️ Gagal/Invalid: `{', '.join(failed_channels)}`"

    await send_log(report_msg)
