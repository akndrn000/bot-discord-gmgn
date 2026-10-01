"""Parser dan handler perintah ``!menu``/``!set``/``!time``/``!list``/``!stop``/``!test``.

Fungsi ``handle_*`` adalah logika murni: menerima state eksplisit dan
mengembalikan teks balasan yang sama karakter-per-karakter dengan kode
lama. Fungsi ``register_commands`` memasangnya ke client Discord.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Awaitable, Callable

from gmgn_bot.messages import (
    GM_WEIGHTED_MESSAGES,
    GN_WEIGHTED_MESSAGES,
    get_menu_text,
)

TEST_MODES = ("gm", "gn")


def handle_set(target_channels: list[int], channel_ids: tuple[str, ...]) -> str:
    """Tambahkan ID channel target; kembalikan teks balasan ``!set``."""
    if not channel_ids:
        return "❌ Masukkan ID channel. Contoh: `!set 123456789`"
    added, exist, invalid = [], [], []
    for cid in channel_ids:
        if not cid.isdigit():
            invalid.append(cid)
            continue
        cid_int = int(cid)
        if cid_int not in target_channels:
            target_channels.append(cid_int)
            added.append(str(cid_int))
        else:
            exist.append(str(cid_int))
    res = "✅ **Update Target:**\n"
    if added:
        res += f"• Ditambahkan: {', '.join(added)}\n"
    if exist:
        res += f"• Sudah ada: {', '.join(exist)}\n"
    if invalid:
        res += f"• Tidak valid: {', '.join(invalid)}\n"
    return res


def apply_time(config: dict[str, Any], time_str: str) -> str:
    """Terapkan jadwal dari sintaks ``!time``; kembalikan teks balasan.

    Melempar ``ValueError`` bila format jam salah (ditangkap pemanggil
    menjadi balasan error). Bagian tanpa awalan ``gm:``/``gn:`` diabaikan
    tanpa error, sama seperti kode lama.
    """
    clean_str = time_str.replace(".", ":").lower()
    parts = [p.strip() for p in clean_str.split(",")]
    for part in parts:
        if part.startswith("gm:"):
            t = part.replace("gm:", "").strip()
            datetime.strptime(t, "%H:%M")
            config["gm_time"] = t
        elif part.startswith("gn:"):
            t = part.replace("gn:", "").strip()
            datetime.strptime(t, "%H:%M")
            config["gn_time"] = t
    return f"⏰ **Jadwal Diperbarui:** GM `{config['gm_time']}` | GN `{config['gn_time']}`"


def handle_list(config: dict[str, Any]) -> str:
    """Kembalikan teks balasan ``!list``."""
    channels = config.get("target_channels", [])
    msg = (
        f"📋 **Konfigurasi:**\n• GM: `{config.get('gm_time')}`\n"
        f"• GN: `{config.get('gn_time')}`\n• Total Target: `{len(channels)}`\n"
    )
    if channels:
        msg += "\n**Daftar ID:**\n" + "\n".join(f"- `{c}`" for c in channels)
    return msg


def handle_stop(target_channels: list[int], channel_id: str | None) -> tuple[str, bool]:
    """Hapus channel dari target; kembalikan (teks balasan, berhasil?)."""
    if not channel_id or not channel_id.isdigit():
        return "❌ Masukkan ID valid. Contoh: `!stop 123456789`", False
    cid_int = int(channel_id)
    if cid_int in target_channels:
        target_channels.remove(cid_int)
        return f"🗑️ Channel `{channel_id}` dihapus.", True
    return f"⚠️ Channel `{channel_id}` tidak ditemukan.", False


def validate_test_mode(mode: str | None) -> str | None:
    """Kembalikan label ``GM``/``GN`` atau ``None`` bila mode tidak valid."""
    if not mode or mode.lower() not in TEST_MODES:
        return None
    return mode.upper()


def register_commands(
    bot: Any,
    config: dict[str, Any],
    save_config: Callable[[dict[str, Any]], None],
    broadcast: Callable[..., Awaitable[None]],
) -> None:
    """Pasang keenam perintah ke *bot*; perilaku sama dengan kode lama."""

    @bot.command(name="menu")
    async def show_menu(ctx: Any) -> None:
        await ctx.send(get_menu_text())

    @bot.command(name="set")
    async def set_channel(ctx: Any, *channel_ids: str) -> None:
        reply = handle_set(config["target_channels"], channel_ids)
        if channel_ids:
            save_config(config)
        await ctx.send(reply)

    @bot.command(name="time")
    async def set_time(ctx: Any, *, time_str: str | None = None) -> None:
        if not time_str:
            await ctx.send("❌ Contoh format: `!time gm:07.00, gn:19.00`")
            return
        try:
            reply = apply_time(config, time_str)
            save_config(config)
            await ctx.send(reply)
        except Exception:
            await ctx.send("❌ Format jam salah. Gunakan format 24 Jam (`HH:MM`).")

    @bot.command(name="list")
    async def list_channels(ctx: Any) -> None:
        await ctx.send(handle_list(config))

    @bot.command(name="stop")
    async def stop_channel(ctx: Any, channel_id: str | None = None) -> None:
        reply, removed = handle_stop(config["target_channels"], channel_id)
        if removed:
            save_config(config)
        await ctx.send(reply)

    @bot.command(name="test")
    async def test_broadcast(ctx: Any, mode: str | None = None) -> None:
        label = validate_test_mode(mode)
        if label is None:
            await ctx.send("❌ Format salah. Gunakan: `!test gm` atau `!test gn`")
            return
        messages = GM_WEIGHTED_MESSAGES if label == "GM" else GN_WEIGHTED_MESSAGES
        await ctx.send(f"🧪 **[TES MANUAL]** Mengirimkan {label} ke target channel...")
        await broadcast(messages, f"TEST-{label}")
