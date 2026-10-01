# -*- coding: utf-8 -*-
"""Tes perilaku kode BARU (paket gmgn_bot).

Kontrak: seluruh ekspektasi (string balasan, angka, aturan jadwal,
daftar pesan, bobot) adalah salinan persis dari
tests/test_characterization.py (kode lama). Hanya lapisan import dan
pemanggilan API yang disesuaikan dengan struktur modular baru.

Tidak ada koneksi Discord / token asli di sini: semua I/O jaringan di-mock.
"""

import asyncio
import functools
import json
import logging
import random
from datetime import datetime
from types import SimpleNamespace

import pytest
import pytz

from gmgn_bot import commands as cmd
from gmgn_bot import scheduler as sched
from gmgn_bot import settings as settings_mod
from gmgn_bot import storage
from gmgn_bot.client import (
    COMMAND_PREFIX,
    create_bot,
    register_events,
    register_scheduler,
    send_log,
)
from gmgn_bot.messages import (
    GM_WEIGHTED_MESSAGES,
    GN_WEIGHTED_MESSAGES,
    get_menu_text,
    get_random_message,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
class FakeCtx:
    """Pengganti minimal discord Context: hanya mencatat ctx.send()."""

    def __init__(self):
        self.sent = []

    async def send(self, text):
        self.sent.append(text)
        return text


class StubBot:
    """Bot tiruan untuk menguji wiring tanpa koneksi Discord."""

    def __init__(self):
        self.registered_commands = {}
        self.registered_events = {}
        self.user = SimpleNamespace(id=1)
        self.channels = {}
        self.contexts = {}
        self.invoked = []

    def command(self, name=None):
        def deco(fn):
            self.registered_commands[name or fn.__name__] = fn
            return fn

        return deco

    def event(self, fn):
        self.registered_events[fn.__name__] = fn
        return fn

    def get_channel(self, cid):
        return self.channels.get(cid)

    async def fetch_channel(self, cid):
        raise RuntimeError("not found")

    async def get_context(self, message):
        return self.contexts.get(id(message), SimpleNamespace(valid=False))

    async def invoke(self, ctx):
        self.invoked.append(ctx)


def fresh_config(**overrides):
    cfg = {"gm_time": "07:00", "gn_time": "19:00", "target_channels": []}
    cfg.update(overrides)
    return cfg


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Snapshot teks & data (salinan persis ekspektasi kode lama)
# ---------------------------------------------------------------------------
EXPECTED_MENU = (
    "🤖 **BOT GM/GN AUTOMATION ON**\n"
    "───────────────────────────────\n"
    "📌 **MENU PERINTAH:**\n"
    "• `!set <id1> <id2>` : Tambah target channel\n"
    "• `!time gm:07.00, gn:19.00` : Atur jam GM/GN\n"
    "• `!list` : Lihat daftar target & jadwal\n"
    "• `!stop <id>` : Hapus channel dari target\n"
    "• `!test gm` atau `!test gn` : Tes kirim manual\n"
    "• `!menu` : Tampilkan menu bantuan\n"
    "───────────────────────────────"
)

EXPECTED_GM_LIST = [
    ("gm", 40),
    ("gm guys", 25),
    ("gm frens", 20),
    ("gm all", 15),
    ("good morning", 10),
    ("gm ser", 6),
    ("morning all", 6),
    ("gm fam", 5),
    ("gm world", 4),
    ("gm everyone", 2),
    ("gm! time to grind", 2),
    ("gm! have a good one", 1),
]

EXPECTED_GN_LIST = [
    ("gn", 40),
    ("gn guys", 25),
    ("gn frens", 20),
    ("gn all", 15),
    ("good night", 10),
    ("gn ser", 6),
    ("night all", 6),
    ("gn fam", 5),
    ("gn sleep well", 4),
    ("gn world", 2),
    ("gn sleep tight", 2),
    ("gn everyone", 1),
]


def test_menu_text_snapshot():
    assert get_menu_text() == EXPECTED_MENU


def test_weighted_lists_snapshot():
    assert list(GM_WEIGHTED_MESSAGES) == EXPECTED_GM_LIST
    assert list(GN_WEIGHTED_MESSAGES) == EXPECTED_GN_LIST


def test_random_pick_pinned_seeds():
    """Seed tetap -> hasil tetap (sama seperti kode lama)."""
    random.seed(0)
    assert get_random_message(GM_WEIGHTED_MESSAGES) == "gm ser"
    random.seed(0)
    assert get_random_message(GN_WEIGHTED_MESSAGES) == "gn ser"
    random.seed(1)
    assert get_random_message(GM_WEIGHTED_MESSAGES) == "gm"
    random.seed(1)
    assert get_random_message(GN_WEIGHTED_MESSAGES) == "gn"
    random.seed(42)
    assert get_random_message(GM_WEIGHTED_MESSAGES) == "gm all"
    random.seed(42)
    assert get_random_message(GN_WEIGHTED_MESSAGES) == "gn all"


def test_random_pick_deterministic_and_in_list():
    random.seed(7)
    a = [get_random_message(GM_WEIGHTED_MESSAGES) for _ in range(20)]
    random.seed(7)
    b = [get_random_message(GM_WEIGHTED_MESSAGES) for _ in range(20)]
    assert a == b
    valid = {m for m, _ in EXPECTED_GM_LIST}
    assert all(x in valid for x in a)


# ---------------------------------------------------------------------------
# Wiring perintah: nama terdaftar + handler thin memanggil logika murni
# ---------------------------------------------------------------------------
def _wired(commands_bot=None):
    bot = commands_bot or StubBot()
    config = fresh_config()
    saved = []
    cmd.register_commands(bot, config, saved.append, lambda *a: asyncio.sleep(0))
    return bot, config, saved


def test_command_names_registered():
    bot, _, _ = _wired()
    assert set(bot.registered_commands) == {"menu", "set", "time", "list", "stop", "test"}


def test_menu_command_sends_menu_text():
    bot, _, _ = _wired()
    ctx = FakeCtx()
    run(bot.registered_commands["menu"](ctx))
    assert ctx.sent == [EXPECTED_MENU]


def test_list_empty():
    bot, _, _ = _wired()
    ctx = FakeCtx()
    run(bot.registered_commands["list"](ctx))
    assert ctx.sent == ["📋 **Konfigurasi:**\n• GM: `07:00`\n• GN: `19:00`\n• Total Target: `0`\n"]


def test_list_with_targets():
    bot = StubBot()
    config = fresh_config(target_channels=[111, 222])
    cmd.register_commands(bot, config, lambda c: None, lambda *a: asyncio.sleep(0))
    ctx = FakeCtx()
    run(bot.registered_commands["list"](ctx))
    assert ctx.sent == [
        "📋 **Konfigurasi:**\n• GM: `07:00`\n• GN: `19:00`\n• Total Target: `2`\n"
        "\n**Daftar ID:**\n- `111`\n- `222`"
    ]


# ---------------------------------------------------------------------------
# Perintah !set
# ---------------------------------------------------------------------------
def test_set_empty():
    assert cmd.handle_set([], ()) == "❌ Masukkan ID channel. Contoh: `!set 123456789`"
    bot, config, saved = _wired()
    ctx = FakeCtx()
    run(bot.registered_commands["set"](ctx))
    assert ctx.sent == ["❌ Masukkan ID channel. Contoh: `!set 123456789`"]
    assert saved == []  # tanpa argumen: tidak menyimpan (sama seperti kode lama)


def test_set_add_new():
    bot, config, saved = _wired()
    ctx = FakeCtx()
    run(bot.registered_commands["set"](ctx, "123", "456"))
    assert config["target_channels"] == [123, 456]
    assert ctx.sent == ["✅ **Update Target:**\n• Ditambahkan: 123, 456\n"]
    assert saved == [config]


def test_set_duplicate_and_invalid():
    bot = StubBot()
    config = fresh_config(target_channels=[123])
    cmd.register_commands(bot, config, lambda c: None, lambda *a: asyncio.sleep(0))
    ctx = FakeCtx()
    run(bot.registered_commands["set"](ctx, "123", "abc", "789"))
    assert config["target_channels"] == [123, 789]
    assert ctx.sent == [
        "✅ **Update Target:**\n• Ditambahkan: 789\n• Sudah ada: 123\n• Tidak valid: abc\n"
    ]


def test_set_all_invalid():
    channels: list = []
    assert cmd.handle_set(channels, ("xx", "yy")) == (
        "✅ **Update Target:**\n• Tidak valid: xx, yy\n"
    )
    assert channels == []


# ---------------------------------------------------------------------------
# Perintah !time
# ---------------------------------------------------------------------------
def _wired_time(config=None):
    bot = StubBot()
    cfg = config if config is not None else fresh_config()
    saved = []
    cmd.register_commands(bot, cfg, saved.append, lambda *a: asyncio.sleep(0))
    return bot, cfg, saved


def test_time_empty():
    bot, config, saved = _wired_time()
    ctx = FakeCtx()
    run(bot.registered_commands["time"](ctx))
    assert ctx.sent == ["❌ Contoh format: `!time gm:07.00, gn:19.00`"]
    assert config["gm_time"] == "07:00"
    assert saved == []


def test_time_dot_format():
    bot, config, saved = _wired_time()
    ctx = FakeCtx()
    run(bot.registered_commands["time"](ctx, time_str="gm:07.00, gn:19.00"))
    assert config["gm_time"] == "07:00"
    assert config["gn_time"] == "19:00"
    assert ctx.sent == ["⏰ **Jadwal Diperbarui:** GM `07:00` | GN `19:00`"]
    assert saved == [config]


def test_time_colon_format():
    assert cmd.apply_time(fresh_config(), "gm:06:30, gn:21:15") == (
        "⏰ **Jadwal Diperbarui:** GM `06:30` | GN `21:15`"
    )


def test_time_partial_only_gm():
    """Hanya bagian gm: yang diproses; gn: tidak tersentuh."""
    cfg = fresh_config()
    reply = cmd.apply_time(cfg, "gm:08.00")
    assert cfg["gm_time"] == "08:00"
    assert cfg["gn_time"] == "19:00"
    assert reply == "⏰ **Jadwal Diperbarui:** GM `08:00` | GN `19:00`"


def test_time_case_insensitive_and_spaces():
    cfg = fresh_config()
    reply = cmd.apply_time(cfg, "  GM:05.00 ,  GN:20.00 ")
    assert reply == "⏰ **Jadwal Diperbarui:** GM `05:00` | GN `20:00`"


def test_time_invalid_format():
    bot, config, saved = _wired_time()
    ctx = FakeCtx()
    run(bot.registered_commands["time"](ctx, time_str="gm:25.00, gn:19.00"))
    assert ctx.sent == ["❌ Format jam salah. Gunakan format 24 Jam (`HH:MM`)."]
    assert config["gm_time"] == "07:00"
    assert saved == []


def test_time_garbage():
    bot, config, saved = _wired_time()
    ctx = FakeCtx()
    # Tidak ada bagian gm:/gn: -> config tak berubah tapi balasan tetap sukses.
    run(bot.registered_commands["time"](ctx, time_str="hello world"))
    assert config["gm_time"] == "07:00"
    assert config["gn_time"] == "19:00"
    assert ctx.sent == ["⏰ **Jadwal Diperbarui:** GM `07:00` | GN `19:00`"]


# ---------------------------------------------------------------------------
# Perintah !stop
# ---------------------------------------------------------------------------
def test_stop_empty_and_invalid():
    assert cmd.handle_stop([123], None) == (
        "❌ Masukkan ID valid. Contoh: `!stop 123456789`",
        False,
    )
    assert cmd.handle_stop([123], "abc") == (
        "❌ Masukkan ID valid. Contoh: `!stop 123456789`",
        False,
    )


def test_stop_existing():
    bot = StubBot()
    config = fresh_config(target_channels=[123, 456])
    saved = []
    cmd.register_commands(bot, config, saved.append, lambda *a: asyncio.sleep(0))
    ctx = FakeCtx()
    run(bot.registered_commands["stop"](ctx, "123"))
    assert config["target_channels"] == [456]
    assert ctx.sent == ["🗑️ Channel `123` dihapus."]
    assert saved == [config]


def test_stop_not_found():
    channels = [456]
    reply, removed = cmd.handle_stop(channels, "999")
    assert reply == "⚠️ Channel `999` tidak ditemukan."
    assert removed is False
    assert channels == [456]


# ---------------------------------------------------------------------------
# Perintah !test
# ---------------------------------------------------------------------------
def test_test_invalid_mode():
    for bad in (None, "", "xx", "gmm", "GMX"):
        assert cmd.validate_test_mode(bad) is None, bad
    bot, _, _ = _wired()
    ctx = FakeCtx()
    run(bot.registered_commands["test"](ctx, "xx"))
    assert ctx.sent == ["❌ Format salah. Gunakan: `!test gm` atau `!test gn`"]


def test_test_valid_triggers_broadcast():
    calls = []

    async def fake_broadcast(w_list, label):
        calls.append((list(w_list), label))

    bot = StubBot()
    cmd.register_commands(bot, fresh_config(), lambda c: None, fake_broadcast)
    ctx = FakeCtx()
    run(bot.registered_commands["test"](ctx, "gm"))
    assert ctx.sent == ["🧪 **[TES MANUAL]** Mengirimkan GM ke target channel..."]
    assert len(calls) == 1
    assert calls[0][0] == EXPECTED_GM_LIST
    assert calls[0][1] == "TEST-GM"

    ctx2 = FakeCtx()
    run(bot.registered_commands["test"](ctx2, "GN"))
    assert ctx2.sent == ["🧪 **[TES MANUAL]** Mengirimkan GN ke target channel..."]
    assert calls[1][0] == EXPECTED_GN_LIST
    assert calls[1][1] == "TEST-GN"


# ---------------------------------------------------------------------------
# Config file: baru / sudah ada / rusak / kosong
# ---------------------------------------------------------------------------
def test_config_missing_returns_defaults(tmp_path):
    target = tmp_path / "config.json"
    assert not target.exists()
    assert storage.load_config(str(target)) == {
        "gm_time": "07:00",
        "gn_time": "19:00",
        "target_channels": [],
    }


def test_config_existing_preserved(tmp_path):
    target = tmp_path / "config.json"
    existing = {"gm_time": "06:00", "gn_time": "22:00", "target_channels": [111, 222]}
    target.write_text(json.dumps(existing), encoding="utf-8")
    assert storage.load_config(str(target)) == existing


def test_config_corrupt_returns_defaults(tmp_path):
    target = tmp_path / "config.json"
    target.write_text("{bukan json valid", encoding="utf-8")
    assert storage.load_config(str(target)) == {
        "gm_time": "07:00",
        "gn_time": "19:00",
        "target_channels": [],
    }


def test_config_empty_file_returns_defaults(tmp_path):
    target = tmp_path / "config.json"
    target.write_text("", encoding="utf-8")
    assert storage.load_config(str(target)) == {
        "gm_time": "07:00",
        "gn_time": "19:00",
        "target_channels": [],
    }


def test_config_roundtrip(tmp_path):
    target = tmp_path / "config.json"
    cfg = fresh_config(target_channels=[1, 2, 3])
    storage.save_config(str(target), cfg)
    assert json.loads(target.read_text(encoding="utf-8")) == cfg


# ---------------------------------------------------------------------------
# Scheduler: aturan jendela kirim (sama seperti kode lama)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "now,expected",
    [
        ((7, 0), True),  # tepat waktu
        ((7, 15), True),  # batas atas inklusif
        ((7, 16), False),  # lewat 15 menit
        ((6, 59), False),  # belum waktunya
        ((8, 0), False),
        ((0, 5), False),
    ],
)
def test_scheduler_window(now, expected):
    assert sched.should_send("07:00", now[0], now[1], None, "2026-01-01") is expected


def test_scheduler_no_double_send_same_day():
    assert sched.should_send("07:00", 7, 5, "2026-01-01", "2026-01-01") is False
    assert sched.should_send("07:00", 7, 5, "2025-12-31", "2026-01-01") is True


def test_due_labels_marks_state_before_send():
    state = sched.SchedulerState()
    config = fresh_config(target_channels=[111])
    due = sched.due_labels(config, 7, 5, "2026-01-01", state)
    assert due == [sched.GM_AUTO_LABEL]
    assert state.last_sent_gm_date == "2026-01-01"
    # Panggilan kedua di hari yang sama: tidak ada yang jatuh tempo.
    assert sched.due_labels(config, 7, 5, "2026-01-01", state) == []


def test_due_labels_empty_targets_marks_nothing():
    state = sched.SchedulerState()
    due = sched.due_labels(fresh_config(), 7, 0, "2026-01-01", state)
    assert due == []
    assert state.last_sent_gm_date is None


def test_scheduler_loop_interval():
    assert sched.LOOP_INTERVAL_SECONDS == 20
    bot = StubBot()
    loop = register_scheduler(
        bot,
        fresh_config(),
        sched.SchedulerState(),
        lambda *a: asyncio.sleep(0),
        "Asia/Jakarta",
    )
    assert loop.seconds == 20


def test_scheduler_loop_fires_due_broadcast(monkeypatch):
    """Satu iterasi loop memetakan label GM ke daftar pesan GM."""
    monkeypatch.setattr(sched.random, "randint", lambda a, b: 0)
    now = datetime.now(pytz.timezone("Asia/Jakarta"))
    config = fresh_config(
        target_channels=[111],
        gm_time=now.strftime("%H:%M"),
        gn_time="00:00",
    )
    calls = []

    async def fake_broadcast(w_list, label):
        calls.append((list(w_list), label))

    bot = StubBot()
    loop = register_scheduler(bot, config, sched.SchedulerState(), fake_broadcast, "Asia/Jakarta")
    run(loop.coro())
    assert len(calls) == 1
    assert calls[0][0] == EXPECTED_GM_LIST
    assert calls[0][1] == "GM (Otomatis)"


def test_timezone_fallback():
    """TIMEZONE salah -> fallback Asia/Jakarta (sama seperti kode lama)."""
    with pytest.raises(Exception):
        pytz.timezone("Zona/Tidak-Ada")
    assert sched.resolve_timezone("Zona/Tidak-Ada").zone == "Asia/Jakarta"
    assert sched.resolve_timezone("Asia/Makassar").zone == "Asia/Makassar"


# ---------------------------------------------------------------------------
# Broadcast & send_log (jaringan di-mock)
# ---------------------------------------------------------------------------
def _broadcast(config, logs, channels, text="gm"):
    async def fake_send_log(msg):
        logs.append(msg)

    return functools.partial(
        sched.broadcast,
        lambda cid: channels.get(cid),
        _never_fetch,
        fake_send_log,
        config,
    )


async def _never_fetch(cid):
    raise AssertionError("fetch tidak boleh dipanggil saat get_channel hit")


def test_broadcast_no_targets():
    logs: list = []
    run(
        _broadcast(fresh_config(target_channels=[]), logs, {})(
            GM_WEIGHTED_MESSAGES, "GM (Otomatis)"
        )
    )
    assert logs == ["⚠️ [BROADCAST GM (Otomatis)] Gagal: Tidak ada target channel terdaftar."]


def test_broadcast_success_report_format(monkeypatch):
    monkeypatch.setattr(sched.random, "randint", lambda a, b: 0)
    monkeypatch.setattr(sched, "get_random_message", lambda wl: "gm")

    class FakeChannel:
        def __init__(self, cid):
            self.id = cid
            self.name = f"chan-{cid}"
            self.sent = []

        async def send(self, text):
            self.sent.append(text)

    channels = {111: FakeChannel(111), 222: FakeChannel(222)}
    logs: list = []
    run(
        _broadcast(fresh_config(target_channels=[111, 222]), logs, channels)(
            GM_WEIGHTED_MESSAGES, "GM (Otomatis)"
        )
    )

    assert logs[0] == "🚀 Memulai pengiriman **GM (Otomatis)** ke `2` channel..."
    assert logs[1] == (
        "📊 **LAPORAN BROADCAST: GM (Otomatis)**\n"
        "• Status: Selesai (`2/2` berhasil)\n\n"
        "📝 **Detail Pesan Terkirim:**\n"
        "• <#111> (`#chan-111`): `gm`\n"
        "• <#222> (`#chan-222`): `gm`"
    )


def test_broadcast_marks_failed_channels(monkeypatch):
    monkeypatch.setattr(sched.random, "randint", lambda a, b: 0)
    monkeypatch.setattr(sched, "get_random_message", lambda wl: "gn")

    class FakeChannel:
        name = "ok"

        async def send(self, text):
            pass

    async def fail_fetch(cid):
        raise RuntimeError("not found")

    async def fake_send_log(msg):
        logs.append(msg)

    logs: list = []
    run(
        sched.broadcast(
            lambda cid: FakeChannel() if cid == 111 else None,
            fail_fetch,
            fake_send_log,
            fresh_config(target_channels=[111, 999]),
            GN_WEIGHTED_MESSAGES,
            "GN (Otomatis)",
        )
    )

    assert "`1/2` berhasil" in logs[1]
    assert "⚠️ Gagal/Invalid: `999`" in logs[1]


def test_send_log_forwards_identical_text():
    bot = StubBot()

    class Chan:
        def __init__(self):
            self.sent = []

        async def send(self, text):
            self.sent.append(text)

    chan = Chan()
    bot.channels = {555: chan}
    run(send_log(bot, 555, "halo log"))
    assert chan.sent == ["halo log"]


def test_send_log_no_monitor_sends_nothing(caplog):
    bot = StubBot()
    with caplog.at_level(logging.INFO, logger="gmgn_bot.client"):
        run(send_log(bot, 0, "halo log"))
    assert bot.channels == {}
    assert "halo log" in caplog.text


# ---------------------------------------------------------------------------
# on_message: hanya author sendiri + hanya channel pemantau
# ---------------------------------------------------------------------------
def test_on_message_ignores_others_and_other_channels():
    bot = StubBot()
    loop = SimpleNamespace(is_running=lambda: True, start=lambda: None)
    register_events(bot, 555, loop)

    class FakeMessage:
        def __init__(self, uid, cid):
            self.author = SimpleNamespace(id=uid)
            self.channel = SimpleNamespace(id=cid)

    handler = bot.registered_events["on_message"]
    run(handler(FakeMessage(2, 555)))  # penulis lain
    run(handler(FakeMessage(1, 999)))  # channel lain
    assert bot.invoked == []


def test_on_message_invokes_own_monitor_command():
    bot = StubBot()
    loop = SimpleNamespace(is_running=lambda: True, start=lambda: None)
    register_events(bot, 555, loop)

    class FakeMessage:
        author = SimpleNamespace(id=1)
        channel = SimpleNamespace(id=555)

    msg = FakeMessage()
    ctx = SimpleNamespace(valid=True)
    bot.contexts[id(msg)] = ctx
    run(bot.registered_events["on_message"](msg))
    assert bot.invoked == [ctx]


def test_events_registered():
    bot = StubBot()
    loop = SimpleNamespace(is_running=lambda: True, start=lambda: None)
    register_events(bot, 555, loop)
    assert set(bot.registered_events) == {"on_ready", "on_message"}


# ---------------------------------------------------------------------------
# Settings & client factory
# ---------------------------------------------------------------------------
def test_env_var_names_and_defaults():
    s = settings_mod.load_settings({})
    assert s.discord_user_token == ""
    assert s.monitor_channel_id == 0
    assert s.timezone == "Asia/Jakarta"

    s2 = settings_mod.load_settings(
        {
            "DISCORD_USER_TOKEN": "abc",
            "MONITOR_CHANNEL_ID": "555",
            "TIMEZONE": "Asia/Makassar",
        }
    )
    assert (s2.discord_user_token, s2.monitor_channel_id, s2.timezone) == (
        "abc",
        555,
        "Asia/Makassar",
    )
    assert settings_mod.ENV_TOKEN == "DISCORD_USER_TOKEN"
    assert settings_mod.ENV_MONITOR_CHANNEL == "MONITOR_CHANNEL_ID"
    assert settings_mod.ENV_TIMEZONE == "TIMEZONE"


def test_client_factory_prefix_and_selfbot():
    bot = create_bot()
    assert bot.command_prefix == "!"
    assert COMMAND_PREFIX == "!"
    # self_bot=True diteruskan ke konstruktor (mode self-bot: pesan orang
    # lain dilewati, pesan sendiri diproses) — sama seperti kode lama.
    assert bot._skip_check(1, 1) is False
    assert bot._skip_check(2, 1) is True
