"""Unit tests for /api/settings endpoints."""


class TestGetSettings:
    """Tests for GET /api/settings."""

    def test_get_settings_empty(self, client):
        """Empty DB returns empty settings."""
        resp = client.get("/api/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["settings"] == {}

    def test_get_settings_masks_api_key(self, client, db_session):
        """API key is masked in response."""
        from database.models import AppSetting

        db_session.add(AppSetting(key="ai_api_key", value="sk-1234567890abcdef"))
        db_session.add(AppSetting(key="ai_provider", value="openai"))
        db_session.commit()

        resp = client.get("/api/settings")
        assert resp.status_code == 200
        data = resp.json()["settings"]
        assert data["ai_api_key"] == "sk-12345****"
        assert data["ai_provider"] == "openai"
        assert "sk-1234567890" not in data["ai_api_key"]


class TestUpdateSettings:
    """Tests for PUT /api/settings."""

    def test_update_creates_setting(self, client):
        """PUT creates a new setting when it doesn't exist."""
        resp = client.put(
            "/api/settings",
            json=[{"key": "ai_provider", "value": "gemini"}],
        )
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "updated": 1}

        # Verify it was saved
        resp = client.get("/api/settings")
        assert resp.json()["settings"]["ai_provider"] == "gemini"

    def test_update_existing_setting(self, client):
        """PUT updates an existing setting."""
        client.put("/api/settings", json=[{"key": "ai_model", "value": "gpt-4o"}])
        resp = client.put("/api/settings", json=[{"key": "ai_model", "value": "gpt-4o-mini"}])
        assert resp.status_code == 200

        resp = client.get("/api/settings")
        assert resp.json()["settings"]["ai_model"] == "gpt-4o-mini"

    def test_disable_ai_clears_api_key(self, client):
        """Disabling AI removes the stored API key."""
        client.put(
            "/api/settings",
            json=[
                {"key": "ai_enabled", "value": "true"},
                {"key": "ai_api_key", "value": "secret-key"},
            ],
        )
        # Verify key exists
        resp = client.get("/api/settings")
        assert "ai_api_key" in resp.json()["settings"]

        # Disable AI
        client.put("/api/settings", json=[{"key": "ai_enabled", "value": "false"}])

        # Verify key was removed
        resp = client.get("/api/settings")
        assert "ai_api_key" not in resp.json()["settings"]

    def test_update_requires_body(self, client):
        """PUT without body is rejected."""
        resp = client.put("/api/settings")
        assert resp.status_code == 422


class TestTestConnection:
    """Tests for POST /api/settings/test."""

    def test_missing_api_key(self, client):
        """Test connection without api_key returns error."""
        resp = client.post(
            "/api/settings/test",
            json={"provider": "openai", "api_key": ""},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"
        assert "API key is required" in data["message"]
