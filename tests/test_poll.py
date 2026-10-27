"""Unit tests for /api/poll endpoint."""


class TestPollEndpoint:
    """Tests for POST /api/poll."""

    def test_poll_all_sources(self, client):
        """POST /api/poll triggers all configured pollers."""
        resp = client.post("/api/poll")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "results" in data
        assert "message" in data
        # Should have results for all sources (even disabled ones)
        assert "github" in data["results"]
        assert "jira" in data["results"]
        assert "bitbucket" in data["results"]
        assert "git_hooks" in data["results"]

    def test_poll_returns_source_status(self, client):
        """Each source has a status in results."""
        resp = client.post("/api/poll")
        data = resp.json()
        for source in ["github", "jira", "bitbucket", "git_hooks"]:
            assert source in data["results"]
            assert data["results"][source] in (
                "ok",
                "disabled",
            ), f"Unexpected status for {source}: {data['results'][source]}"

    def test_poll_handles_source_error(self, client, monkeypatch):
        """Source error is captured in results."""
        from config import config as app_config
        from pollers import github as gh_module

        def failing_poll():
            raise RuntimeError("Network failure")

        monkeypatch.setattr(app_config, "GITHUB_TOKEN", "test-token")
        monkeypatch.setattr(gh_module, "poll_github", failing_poll)

        resp = client.post("/api/poll")
        assert resp.status_code == 200
        data = resp.json()
        assert "github" in data["results"]
        assert data["results"]["github"].startswith("error:")

    def test_poll_message_reports_success_count(self, client):
        """Response message includes success count."""
        resp = client.post("/api/poll")
        data = resp.json()
        # Message should mention "Sync complete: N sources OK"
        assert "Sync complete" in data["message"]
        assert "sources OK" in data["message"]
