from aiogram.fsm.state import State, StatesGroup


class AddSearchFSM(StatesGroup):
    """FSM for the 'add a new search' flow."""
    waiting_url = State()


class EditFilterFSM(StatesGroup):
    """FSM for the 'edit a filter value' flow (text-input step)."""
    waiting_value = State()
