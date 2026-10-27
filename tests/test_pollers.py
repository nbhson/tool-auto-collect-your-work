"""Unit tests for the poller HTTP retry helper."""

import httpx

from pollers.http import request_with_retry


class TestRequestWithRetry:
    """Tests for request_with_retry helper."""

    def test_success_first_attempt(self, monkeypatch):
        """Successful request returns response immediately."""
        calls = []

        def mock_request(self, **kwargs):
            calls.append(1)
            return httpx.Response(
                200,
                request=httpx.Request("GET", "https://example.com"),
                json={"ok": True},
            )

        monkeypatch.setattr(httpx.Client, "request", mock_request)

        resp = request_with_retry("GET", "https://example.com")
        assert resp.status_code == 200
        assert len(calls) == 1

    def test_no_retry_on_4xx(self, monkeypatch):
        """4xx responses do not trigger retry."""
        calls = []

        def mock_request(self, **kwargs):
            calls.append(1)
            return httpx.Response(
                404,
                request=httpx.Request("GET", "https://example.com"),
            )

        monkeypatch.setattr(httpx.Client, "request", mock_request)

        resp = request_with_retry("GET", "https://example.com")
        assert resp.status_code == 404
        assert len(calls) == 1  # Only 1 attempt, no retry


class TestPollerStateHelpers:
    """Tests for poller state file helpers."""

    def test_get_last_run_missing_file(self, tmp_path, monkeypatch):
        """_get_last_run returns None when state file missing."""
        from pollers import github as gh

        fake_state = tmp_path / "state.json"
        monkeypatch.setattr(gh, "STATE_FILE", fake_state)

        assert gh._get_last_run() is None

    def test_save_and_get_last_run(self, tmp_path, monkeypatch):
        """Save and read back last_run timestamp."""
        from datetime import datetime

        from pollers import github as gh

        state_file = tmp_path / "state.json"
        monkeypatch.setattr(gh, "STATE_FILE", state_file)

        now = datetime(2026, 10, 27, 12, 0, 0)
        gh._save_last_run(now)

        loaded = gh._get_last_run()
        assert loaded is not None
        assert loaded.year == 2026
        assert loaded.month == 10

    def test_corrupt_state_file_returns_none(self, tmp_path, monkeypatch):
        """Corrupt state file is handled gracefully."""
        from pollers import github as gh

        state_file = tmp_path / "state.json"
        state_file.write_text("not-valid-json{{{")

        monkeypatch.setattr(gh, "STATE_FILE", state_file)
        assert gh._get_last_run() is None
