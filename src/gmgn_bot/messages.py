"""Kumpulan pesan GM/GN, bobot rarity, dan teks menu.

Daftar pesan, bobot, dan seluruh teks balasan sama karakter-per-karakter
dengan kode lama; modul ini hanya memindahkannya tanpa mengubah isi.
"""

from __future__ import annotations

import random

GM_WEIGHTED_MESSAGES: list[tuple[str, int]] = [
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

GN_WEIGHTED_MESSAGES: list[tuple[str, int]] = [
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


def get_random_message(weighted_list: list[tuple[str, int]]) -> str:
    """Pilih satu pesan secara acak sesuai bobot (rarity)."""
    messages, weights = zip(*weighted_list)
    return random.choices(messages, weights=weights, k=1)[0]


def get_menu_text() -> str:
    """Teks bantuan yang dikirim oleh perintah ``!menu``."""
    return (
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
