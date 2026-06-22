from app.config.settings import Settings


def test_defaults_are_safe():
    s = Settings(_env_file=None)
    assert s.app_name == "juris-backend"
    assert s.environment == "development"
    assert s.google_api_key == ""  # no secret leaks via default


def test_env_override(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    assert Settings(_env_file=None).google_api_key == "test-key"
