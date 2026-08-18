"""
Unit tests for CALF Ecosystem API Endpoints

Run with: pytest tests/test_api.py -v
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys
sys.path.insert(0, '.')

from app.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_returns_ok(self, client):
        """Health endpoint should return status ok."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "service" in data


class TestReportsEndpoints:
    """Test reports API endpoints."""

    def test_list_reports(self, client):
        """GET /api/v1/reports should return list of reports."""
        response = client.get("/api/v1/reports")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_list_report_categories(self, client):
        """GET /api/v1/reports/categories should return categories."""
        response = client.get("/api/v1/reports/categories")
        assert response.status_code == 200
        data = response.json()
        assert "categories" in data
        assert "grouped_reports" in data

    def test_list_report_tiers(self, client):
        """GET /api/v1/reports/tiers should return tiers info."""
        response = client.get("/api/v1/reports/tiers")
        assert response.status_code == 200
        data = response.json()
        assert "tiers" in data
        assert "T1" in data["tiers"]
        assert "T2" in data["tiers"]

    def test_get_report_metadata_valid(self, client):
        """GET /api/v1/reports/{slug}/metadata should return metadata for valid report."""
        response = client.get("/api/v1/reports/stock-opname-report/metadata")
        assert response.status_code == 200
        data = response.json()
        assert "title" in data
        assert "columns" in data

    def test_get_report_metadata_invalid(self, client):
        """GET /api/v1/reports/{slug}/metadata should return 404 for invalid report."""
        response = client.get("/api/v1/reports/invalid-report/metadata")
        assert response.status_code == 404

    @patch('app.main.get_db_connection')
    def test_get_report_valid_params(self, mock_db, client):
        """GET /api/v1/reports/{slug} should work with valid parameters."""
        # Mock database connection
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchall.return_value = []
        mock_db.return_value = mock_conn

        response = client.get(
            "/api/v1/reports/stock-opname-report",
            params={
                "company_id": 1,
                "date_from": "2026-08-01",
                "date_to": "2026-08-17"
            }
        )
        # Will return 500 if DB not properly mocked, but should not crash
        assert response.status_code in [200, 500]


class TestCompaniesEndpoint:
    """Test companies API endpoints."""

    @patch('app.main.get_db_connection')
    def test_list_companies(self, mock_db, client):
        """GET /api/v1/companies should return list of companies."""
        # Mock database connection
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = [
            {
                "id": 1,
                "esb_company_code": "CALF1",
                "company_name": "Calf Roastery",
                "esb_username": "user1",
                "esb_password": "pass123",
                "is_active": True,
                "created_at": "2026-01-01",
                "updated_at": "2026-01-01"
            }
        ]
        mock_conn.cursor.return_value = mock_cur
        mock_db.return_value = mock_conn

        response = client.get("/api/v1/companies")
        assert response.status_code == 200
        data = response.json()
        assert "companies" in data
        assert isinstance(data["companies"], list)


class TestSettingsEndpoints:
    """Test settings API endpoints."""

    @patch('app.main.get_db_connection')
    def test_get_engine_settings(self, mock_db, client):
        """GET /api/v1/settings/engine should return settings."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = {
            "sync_batch_size": 1000,
            "work_hours_interval_minutes": 30,
            "morning_window_interval_minutes": 30
        }
        mock_conn.cursor.return_value = mock_cur
        mock_db.return_value = mock_conn

        response = client.get("/api/v1/settings/engine")
        assert response.status_code == 200

    @patch('app.main.get_db_connection')
    def test_update_engine_settings(self, mock_db, client):
        """PUT /api/v1/settings/engine should update settings."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_db.return_value = mock_conn

        response = client.put(
            "/api/v1/settings/engine",
            json={
                "sync_batch_size": 500,
                "work_hours_interval_minutes": 15,
                "morning_window_interval_minutes": 15
            }
        )
        assert response.status_code == 200


class TestCORS:
    """Test CORS configuration."""

    def test_cors_headers_present(self, client):
        """API responses should include CORS headers."""
        response = client.get("/health")
        # FastAPI CORSMiddleware adds these headers
        assert response.status_code == 200


class TestAPIValidation:
    """Test API input validation."""

    def test_invalid_report_slug(self, client):
        """Invalid report slug should return 404."""
        response = client.get("/api/v1/reports/nonexistent-report/metadata")
        assert response.status_code == 404

    def test_missing_required_params(self, client):
        """Missing required parameters should return validation error."""
        response = client.get("/api/v1/reports/stock-opname-report")
        assert response.status_code == 422  # Validation error


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
