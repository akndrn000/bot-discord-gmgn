"""Baca/tulis ``config.json`` dengan skema yang sama persis seperti kode lama.

Skema: ``{"gm_time": "HH:MM", "gn_time": "HH:MM", "target_channels": [int]}``.
Tidak ada validasi/migrasi: file yang sudah ada dibaca apa adanya, file
rusak/kosong/tidak ada menghasilkan nilai default.
"""

from __future__ import annotations

import json
import os
from typing import Any

DEFAULT_GM_TIME = "07:00"
DEFAULT_GN_TIME = "19:00"

_DEFAULT_CONFIG = {
    "gm_time": DEFAULT_GM_TIME,
    "gn_time": DEFAULT_GN_TIME,
    "target_channels": [],
}


def default_config() -> dict[str, Any]:
    """Kembalikan salinan baru dari konfigurasi default."""
    return {
        "gm_time": DEFAULT_GM_TIME,
        "gn_time": DEFAULT_GN_TIME,
        "target_channels": [],
    }


def load_config(path: str) -> dict[str, Any]:
    """Muat config dari *path*; kembalikan default bila hilang/rusak.

    Sama seperti kode lama: isi file yang valid dibaca apa adanya
    (tanpa penggabungan dengan default), dan kegagalan apa pun
    saat membaca/mengurai menghasilkan default.
    """
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default_config()


def save_config(path: str, config_data: dict[str, Any]) -> None:
    """Simpan config ke *path*; kegagalan diabaikan seperti kode lama."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4)
    except Exception:
        pass
