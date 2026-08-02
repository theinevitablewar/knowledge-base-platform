from app.core.tracing import sanitize


def test_trace_sanitizes_credentials_recursively():
    value = sanitize({"query": "safe", "authorization": "Bearer secret", "nested": {"api_key": "key"}})
    assert value == {"query": "safe", "authorization": "[REDACTED]", "nested": {"api_key": "[REDACTED]"}}
