from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.main import _BOT_COMMANDS, _prepare_bot


@pytest.mark.asyncio
async def test_prepare_bot_authenticates_removes_webhook_and_sets_commands():
    bot = SimpleNamespace(
        get_me=AsyncMock(return_value=SimpleNamespace(username="sshelper", id=123)),
        delete_webhook=AsyncMock(),
        set_my_commands=AsyncMock(),
    )

    await _prepare_bot(bot, [42])

    bot.get_me.assert_awaited_once()
    bot.delete_webhook.assert_awaited_once_with(drop_pending_updates=False)
    assert bot.set_my_commands.await_count == 2
    assert bot.set_my_commands.await_args_list[0].args == (_BOT_COMMANDS,)


@pytest.mark.asyncio
async def test_prepare_bot_command_failure_does_not_block_startup():
    bot = SimpleNamespace(
        get_me=AsyncMock(return_value=SimpleNamespace(username="sshelper", id=123)),
        delete_webhook=AsyncMock(),
        set_my_commands=AsyncMock(side_effect=RuntimeError("temporary API failure")),
    )

    await _prepare_bot(bot, [42])

    bot.delete_webhook.assert_awaited_once_with(drop_pending_updates=False)
