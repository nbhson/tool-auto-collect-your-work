"""Unit tests for /api/logs endpoints."""

from datetime import UTC, datetime


class TestListLogs:
    """Tests for GET /api/logs."""

    def test_list_empty(self, client):
        """Empty database returns empty list."""
        resp = client.get("/api/logs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["page_size"] == 50

    def test_list_with_data(self, client, db_session):
        """List returns created entries."""
        from database.models import WorkLog

        db_session.add(
            WorkLog(
                source="manual",
                activity_type="meeting",
                title="Test meeting",
                activity_timestamp=datetime.now(UTC).replace(tzinfo=None),
                time_spent_minutes=30,
            )
        )
        db_session.commit()

        resp = client.get("/api/logs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["title"] == "Test meeting"
        assert data["items"][0]["source"] == "manual"

    def test_filter_by_source(self, client, db_session):
        """Filter by source returns only matching entries."""
        from database.models import WorkLog

        db_session.add(
            WorkLog(
                source="github",
                activity_type="commit",
                title="GH commit",
                activity_timestamp=datetime.now(UTC).replace(tzinfo=None),
            )
        )
        db_session.add(
            WorkLog(
                source="jira",
                activity_type="comment",
                title="Jira comment",
                activity_timestamp=datetime.now(UTC).replace(tzinfo=None),
            )
        )
        db_session.commit()

        resp = client.get("/api/logs?source=github")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["source"] == "github"

    def test_pagination(self, client, db_session):
        """Pagination returns correct page metadata."""
        from database.models import WorkLog

        for i in range(5):
            db_session.add(
                WorkLog(
                    source="manual",
                    activity_type="other",
                    title=f"Log {i}",
                    activity_timestamp=datetime.now(UTC).replace(tzinfo=None),
                )
            )
        db_session.commit()

        resp = client.get("/api/logs?page=1&page_size=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5  # total entries
        assert len(data["items"]) == 2  # page size
        assert data["page"] == 1
        assert data["page_size"] == 2

    def test_invalid_sort_by_rejected(self, client):
        """Invalid sort_by is rejected with 422."""
        resp = client.get("/api/logs?sort_by=malicious_column")
        assert resp.status_code == 422

    def test_invalid_date_format(self, client):
        """Invalid date filter returns 422."""
        resp = client.get("/api/logs?from=not-a-date")
        assert resp.status_code == 422

    def test_page_out_of_range(self, client):
        """page < 1 is rejected."""
        resp = client.get("/api/logs?page=0")
        assert resp.status_code == 422

    def test_page_size_capped(self, client):
        """page_size > 200 is rejected."""
        resp = client.get("/api/logs?page_size=500")
        assert resp.status_code == 422


class TestCreateLog:
    """Tests for POST /api/logs."""

    def test_create_manual_entry(self, client):
        """Create a manual entry with valid data."""
        payload = {
            "title": "Team standup",
            "description": "Daily standup meeting",
            "activity_type": "meeting",
            "time_spent_minutes": 15,
        }
        resp = client.post("/api/logs", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Team standup"
        assert data["source"] == "manual"
        assert data["activity_type"] == "meeting"
        assert data["time_spent_minutes"] == 15

    def test_create_requires_title(self, client):
        """Title is required."""
        resp = client.post("/api/logs", json={"description": "no title"})
        assert resp.status_code == 422

    def test_create_empty_title_rejected(self, client):
        """Empty title is rejected."""
        resp = client.post("/api/logs", json={"title": ""})
        assert resp.status_code == 422

    def test_create_title_too_long(self, client):
        """Title longer than 500 chars is rejected."""
        resp = client.post("/api/logs", json={"title": "x" * 501})
        assert resp.status_code == 422

    def test_create_negative_time_rejected(self, client):
        """Negative time_spent_minutes is rejected."""
        resp = client.post(
            "/api/logs",
            json={"title": "Test", "time_spent_minutes": -5},
        )
        assert resp.status_code == 422

    def test_create_title_whitespace_stripped(self, client):
        """Title whitespace is stripped."""
        resp = client.post("/api/logs", json={"title": "  Padded title  "})
        assert resp.status_code == 201
        assert resp.json()["title"] == "Padded title"


class TestUpdateLog:
    """Tests for PATCH /api/logs/{id}."""

    def _create(self, client):
        resp = client.post(
            "/api/logs",
            json={"title": "Original", "time_spent_minutes": 10},
        )
        return resp.json()

    def test_update_existing(self, client):
        """Update changes fields and returns updated entry."""
        created = self._create(client)
        log_id = created["id"]

        resp = client.patch(
            f"/api/logs/{log_id}",
            json={"title": "Updated", "time_spent_minutes": 45},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Updated"
        assert data["time_spent_minutes"] == 45

    def test_update_not_found(self, client):
        """Updating nonexistent log returns 404."""
        resp = client.patch(
            "/api/logs/99999",
            json={"title": "Ghost"},
        )
        assert resp.status_code == 404
        assert resp.json()["error"] == "NotFoundError"

    def test_update_invalid_payload(self, client):
        """Update with invalid body returns 422."""
        resp = client.patch("/api/logs/1", json={})
        assert resp.status_code == 422


class TestDeleteLog:
    """Tests for DELETE /api/logs/{id}."""

    def test_delete_existing(self, client):
        """Delete existing log returns 204."""
        created = client.post("/api/logs", json={"title": "To delete"}).json()

        resp = client.delete(f"/api/logs/{created['id']}")
        assert resp.status_code == 204

        # Verify it's gone
        resp = client.get("/api/logs")
        assert resp.json()["total"] == 0

    def test_delete_not_found(self, client):
        """Deleting nonexistent log returns 404."""
        resp = client.delete("/api/logs/99999")
        assert resp.status_code == 404


class TestGetStats:
    """Tests for GET /api/logs/stats."""

    def test_stats_empty(self, client):
        """Stats on empty DB return zeros."""
        resp = client.get("/api/logs/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_logs"] == 0
        assert data["total_time_hours"] == 0
        assert data["github_logs"] == 0
        assert data["manual_logs"] == 0

    def test_stats_with_data(self, client, db_session):
        """Stats reflect created entries."""
        from database.models import WorkLog

        db_session.add(
            WorkLog(
                source="github",
                activity_type="commit",
                title="GH commit",
                activity_timestamp=datetime.now(UTC).replace(tzinfo=None),
                time_spent_minutes=60,
            )
        )
        db_session.add(
            WorkLog(
                source="manual",
                activity_type="meeting",
                title="Meeting",
                activity_timestamp=datetime.now(UTC).replace(tzinfo=None),
                time_spent_minutes=30,
            )
        )
        db_session.commit()

        resp = client.get("/api/logs/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_logs"] == 2
        assert data["github_logs"] == 1
        assert data["manual_logs"] == 1
        # 90 minutes = 1.5 hours
        assert data["total_time_hours"] == 1.5
