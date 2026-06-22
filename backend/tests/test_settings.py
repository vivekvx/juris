from app.config.settings import Settings


def test_defaults_are_safe() -> None:
    s = Settings()
    assert s.app_name == "juris-backend"
    assert s.environment == "development"
    assert s.google_api_key == ""  # no secret leaks via default


def test_env_override(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    assert Settings().google_api_key == "test-key"


def test_all_secrets_default_to_empty() -> None:
    """Every secret field must default to empty string, never to a real value."""
    s = Settings()
    assert s.google_api_key == ""
    assert s.firebase_project_id == ""
    assert s.firebase_credentials == ""
    assert s.firebase_storage_bucket == ""
    assert s.langfuse_secret_key == ""
    assert s.langfuse_public_key == ""


def test_extra_env_vars_are_ignored(monkeypatch) -> None:
    """Unknown env vars must not raise (extra='ignore')."""
    monkeypatch.setenv("TOTALLY_UNKNOWN_VAR", "some-value")
    s = Settings()  # must not raise
    assert s.app_name == "juris-backend"


def test_cors_origins_is_list() -> None:
    """cors_origins must be a list, not a string."""
    s = Settings()
    assert isinstance(s.cors_origins, list)
    assert "http://localhost:3000" in s.cors_origins
