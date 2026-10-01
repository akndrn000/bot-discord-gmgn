"""Baca dan validasi environment variable di satu tempat.

Nama variabel dan perilaku default-nya identik dengan kode lama:
- ``DISCORD_USER_TOKEN`` (default ``""``)
- ``MONITOR_CHANNEL_ID`` (default ``"0"``, dikonversi ke ``int``)
- ``TIMEZONE`` (default ``"Asia/Jakarta"``)
"""

from __future__ import annotations

import os
from dataclasses import dataclass

ENV_TOKEN = "DISCORD_USER_TOKEN"
ENV_MONITOR_CHANNEL = "MONITOR_CHANNEL_ID"
ENV_TIMEZONE = "TIMEZONE"

DEFAULT_TIMEZONE = "Asia/Jakarta"

RAILWAY_DATA_DIR = "/data"
CONFIG_FILENAME = "config.json"


def default_config_path() -> str:
    """Lokasi config.json (volume Railway bila ada, folder lokal bila tidak)."""
    data_dir = RAILWAY_DATA_DIR if os.path.exists(RAILWAY_DATA_DIR) else "."
    return os.path.join(data_dir, CONFIG_FILENAME)


@dataclass(frozen=True)
class Settings:
    """Konfigurasi runtime bot yang dibaca dari environment variable."""

    discord_user_token: str
    monitor_channel_id: int
    timezone: str
    config_path: str


def load_settings(
    env: dict[str, str] | os._Environ[str] | None = None,
    config_path: str | None = None,
) -> Settings:
    """Bangun :class:`Settings` dari environment.

    Perilaku konversi ``MONITOR_CHANNEL_ID`` sama seperti kode lama:
    ``int(...)`` tanpa validasi tambahan, sehingga nilai non-angka
    tetap memunculkan ``ValueError`` (dicatat di laporan, tidak diubah).
    """
    source = os.environ if env is None else env
    return Settings(
        discord_user_token=source.get(ENV_TOKEN, ""),
        monitor_channel_id=int(source.get(ENV_MONITOR_CHANNEL, "0")),
        timezone=source.get(ENV_TIMEZONE, DEFAULT_TIMEZONE),
        config_path=config_path or default_config_path(),
    )
