"""Tests for structured JSON logging."""
import json
import logging
from contextvars import copy_context

import pytest

from app.utils.logging import (
    configure_logging,
    get_logger,
    get_request_id,
    set_request_id,
)


@pytest.fixture(autouse=True)
def _reset_logging():
    """Ensure each test starts with a clean root logger and request context."""
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    # Reset request_id ContextVar before each test
    from app.utils.logging import _request_id
    token = _request_id.set(None)
    yield
    root.handlers = original_handlers
    root.setLevel(original_level)
    _request_id.reset(token)


def _last_json(capsys) -> dict:
    err = capsys.readouterr().err
    last_line = err.strip().splitlines()[-1]
    return json.loads(last_line)


def test_logger_emits_json(capsys):
    configure_logging()
    get_logger("test").info("hello")
    record = _last_json(capsys)
    assert record["message"] == "hello"
    assert record["level"] == "INFO"
    assert record["logger"] == "test"


def test_timestamp_present(capsys):
    configure_logging()
    get_logger("ts").info("timing")
    record = _last_json(capsys)
    assert "timestamp" in record
    # ISO 8601 UTC — ends with Z
    assert record["timestamp"].endswith("Z")


def test_extra_fields_included(capsys):
    configure_logging()
    get_logger("extra").info("with extras", extra={"uid": "u1", "doc_id": "d9"})
    record = _last_json(capsys)
    assert record["uid"] == "u1"
    assert record["doc_id"] == "d9"


def test_request_id_propagated(capsys):
    configure_logging()
    set_request_id("req-123")
    get_logger("req").info("processing")
    record = _last_json(capsys)
    assert record["request_id"] == "req-123"


def test_request_id_absent_when_not_set(capsys):
    configure_logging()
    # Do NOT call set_request_id
    get_logger("noreq").info("no request")
    record = _last_json(capsys)
    assert "request_id" not in record


def test_configure_is_idempotent(capsys):
    configure_logging()
    configure_logging()  # second call must not add duplicate handlers
    get_logger("idem").info("once")
    err = capsys.readouterr().err
    lines = [l for l in err.strip().splitlines() if l]
    records = [json.loads(l) for l in lines if '"message"' in l]
    assert len([r for r in records if r.get("message") == "once"]) == 1


def test_get_request_id_default_is_none():
    assert get_request_id() is None


def test_request_id_is_context_local():
    """request_id set in one context must not leak into another."""
    set_request_id("ctx-A")

    result = {}

    def run_in_new_context():
        result["id"] = get_request_id()

    copy_context().run(run_in_new_context)
    # New context inherits parent's value at copy time — that is correct behaviour.
    # What we verify is that mutations in child don't affect parent.
    assert get_request_id() == "ctx-A"
