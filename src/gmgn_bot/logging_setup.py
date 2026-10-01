"""Konfigurasi logging terpusat (pengganti ``print`` di kode lama)."""

from __future__ import annotations

import logging

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def setup_logging(level: int = logging.INFO) -> None:
    """Aktifkan logging ke stdout; dipanggil sekali saat startup."""
    logging.basicConfig(format=LOG_FORMAT, level=level)


def get_logger(name: str) -> logging.Logger:
    """Ambil logger bernama ``gmgn_bot.<name>``."""
    return logging.getLogger(f"gmgn_bot.{name}")
