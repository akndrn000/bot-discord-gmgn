"""Titik masuk bot: ``python -m gmgn_bot``."""

from __future__ import annotations

import functools
from typing import Any

from gmgn_bot.client import create_bot, register_events, register_scheduler, send_log
from gmgn_bot.commands import register_commands
from gmgn_bot.logging_setup import setup_logging
from gmgn_bot.scheduler import SchedulerState, broadcast
from gmgn_bot.settings import load_settings
from gmgn_bot.storage import load_config, save_config


def main() -> None:
    """Rakit state, pasang handler, dan jalankan bot bila token tersedia."""
    setup_logging()
    settings = load_settings()

    config: dict[str, Any] = load_config(settings.config_path)
    state = SchedulerState()

    bot = create_bot()

    bound_send_log = functools.partial(send_log, bot, settings.monitor_channel_id)
    bound_broadcast = functools.partial(
        broadcast, bot.get_channel, bot.fetch_channel, bound_send_log, config
    )

    def _save(cfg: dict[str, Any]) -> None:
        save_config(settings.config_path, cfg)

    register_commands(bot, config, _save, bound_broadcast)
    loop = register_scheduler(bot, config, state, bound_broadcast, settings.timezone)
    register_events(bot, settings.monitor_channel_id, loop)

    if settings.discord_user_token:
        bot.run(settings.discord_user_token)


if __name__ == "__main__":
    main()
