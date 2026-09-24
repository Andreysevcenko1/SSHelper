from pathlib import Path

from scripts.cleanup_deleted_telegram_users import _get_api_hash


def test_cleanup_uses_configured_api_hash(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TG_API_HASH", "configured-hash")

    assert _get_api_hash() == "configured-hash"


def test_cleanup_reuses_saved_session_without_prompt(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TG_API_HASH", raising=False)
    Path("cleanup_deleted_users.session").touch()
    prompt = lambda _text: (_ for _ in ()).throw(AssertionError("must not prompt"))
    monkeypatch.setattr(
        "scripts.cleanup_deleted_telegram_users.getpass.getpass",
        prompt,
    )

    assert _get_api_hash() == "saved-session"

