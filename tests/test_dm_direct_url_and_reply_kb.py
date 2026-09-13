"""Tests for private DM text fallback, direct SS.lv URL pasting, and reply keyboard navigation."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from aiogram.types import Chat, Message, User
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.bot.handlers.add_search import fsm_add_url, handle_private_text
from app.bot.keyboards.main import main_reply_kb
from app.db.base import Base
from app.db.repo import SearchRepository
from app.i18n import get_text


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


@pytest.fixture
def make_message():
    def _builder(text: str, user_id: int = 123, chat_type: str = "private"):
        user = User(id=user_id, is_bot=False, first_name="Test", language_code="ru")
        chat = Chat(id=user_id, type=chat_type)
        msg = AsyncMock(spec=Message)
        msg.text = text
        msg.from_user = user
        msg.chat = chat
        msg.message_id = 1
        msg.bot = AsyncMock()
        msg.answer = AsyncMock()
        return msg
    return _builder


@pytest.fixture
def make_fsm():
    storage = MemoryStorage()
    def _builder(user_id: int = 123):
        key = StorageKey(bot_id=1, chat_id=user_id, user_id=user_id)
        return FSMContext(storage=storage, key=key)
    return _builder


@pytest.mark.asyncio
async def test_direct_ss_url_pasted_in_dm_adds_search(session_factory, make_message, make_fsm):
    msg = make_message("https://www.ss.lv/lv/real-estate/flats/riga/all/sell/")
    state = make_fsm()

    await handle_private_text(msg, state, session_factory)

    msg.answer.assert_called_once()
    sent_text = msg.answer.call_args[0][0]
    assert "✅" in sent_text

    session = session_factory()
    repo = SearchRepository(session)
    searches = repo.get_user_searches(123)
    assert len(searches) == 1
    assert "flats/riga" in searches[0].url


@pytest.mark.asyncio
async def test_direct_listing_url_pasted_in_dm_shows_explanation(session_factory, make_message, make_fsm):
    msg = make_message("https://www.ss.lv/msg/lv/real-estate/flats/riga/kliversala/hiofx.html")
    state = make_fsm()

    await handle_private_text(msg, state, session_factory)

    msg.answer.assert_called_once()
    sent_text = msg.answer.call_args[0][0]
    assert "конкретное объявление" in sent_text or "konkrētu sludinājumu" in sent_text


@pytest.mark.asyncio
async def test_unrecognized_text_in_dm_shows_fallback_prompt(session_factory, make_message, make_fsm):
    msg = make_message("Привет!")
    state = make_fsm()

    await handle_private_text(msg, state, session_factory)

    msg.answer.assert_called_once()
    sent_text = msg.answer.call_args[0][0]
    assert "готов принимать ссылки" in sent_text or "gatavs pieņemt" in sent_text
    reply_markup = msg.answer.call_args[1].get("reply_markup")
    assert reply_markup is not None


@pytest.mark.asyncio
async def test_reply_keyboard_my_searches_button(session_factory, make_message, make_fsm):
    msg = make_message("📋 Мои поиски")
    state = make_fsm()

    await handle_private_text(msg, state, session_factory)

    msg.answer.assert_called_once()
    sent_text = msg.answer.call_args[0][0]
    assert "У вас нет поисков" in sent_text or "Mani meklējumi" in sent_text


@pytest.mark.asyncio
async def test_reply_keyboard_add_search_button(session_factory, make_message, make_fsm):
    msg = make_message("➕ Добавить поиск")
    state = make_fsm()

    await handle_private_text(msg, state, session_factory)

    msg.answer.assert_called_once()
    sent_text = msg.answer.call_args[0][0]
    assert "Добавить поиск" in sent_text


@pytest.mark.asyncio
async def test_reply_keyboard_subscription_button(session_factory, make_message, make_fsm):
    msg = make_message("⭐ Подписка")
    state = make_fsm()

    await handle_private_text(msg, state, session_factory)

    msg.answer.assert_called_once()
    sent_text = msg.answer.call_args[0][0]
    assert "Подписка" in sent_text or "Abonements" in sent_text


@pytest.mark.asyncio
async def test_main_reply_kb_structure():
    kb = main_reply_kb("ru")
    buttons = [btn.text for row in kb.keyboard for btn in row]
    assert "📋 Мои поиски" in buttons
    assert "➕ Добавить поиск" in buttons
    assert "⭐ Подписка" in buttons
