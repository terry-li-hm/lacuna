import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient

# Mock state initialization before importing app
with patch("backend.state.init_state"), patch("backend.state.init_components"):
    from backend.main import app
    from backend.state import (
        get_document_service,
        get_gap_analysis_service,
        get_system_service,
    )


@pytest.fixture
def client():
    """Test client for Meridian API."""
    return TestClient(app)


@pytest.fixture
def mock_document_service():
    service = MagicMock()
    service.upload_document = AsyncMock()
    service.list_documents.return_value = []
    service.get_all_jurisdictions.return_value = []
    # Mock more methods as needed
    return service


@pytest.fixture
def mock_gap_analysis_service():
    service = MagicMock()
    service.perform_gap_analysis = AsyncMock()
    # Mock more methods as needed
    return service


@pytest.fixture
def mock_system_service():
    service = MagicMock()
    service.get_stats.return_value = {
        "documents_count": 0,
        "jurisdictions": 0,
        "requirements_count": 0,
        "policies_count": 0,
    }
    return service


@pytest.fixture(autouse=True)
def setup_dependency_overrides(
    mock_document_service, mock_gap_analysis_service, mock_system_service
):
    app.dependency_overrides[get_document_service] = lambda: mock_document_service
    app.dependency_overrides[get_gap_analysis_service] = (
        lambda: mock_gap_analysis_service
    )
    app.dependency_overrides[get_system_service] = lambda: mock_system_service
    yield
    app.dependency_overrides = {}
