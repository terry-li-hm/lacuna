from unittest.mock import MagicMock

import pytest

from backend.main import app
from backend.state import get_confirm_service


@pytest.fixture
def mock_confirm_service():
    return MagicMock()


@pytest.fixture(autouse=True)
def override_confirm_service(mock_confirm_service):
    app.dependency_overrides[get_confirm_service] = lambda: mock_confirm_service
    yield
    app.dependency_overrides.pop(get_confirm_service, None)


def test_save_confirmed_success(client, mock_confirm_service):
    mock_confirm_service.save.return_value = {
        "doc_id": "doc-1",
        "confirmed_at": "2026-03-07T00:00:00Z",
        "total": 1,
    }

    response = client.post(
        "/confirm/doc-1",
        json={
            "requirements": [
                {
                    "index": 1,
                    "requirement_id": "req-1",
                    "requirement_type": "Control",
                    "description": "Maintain governance framework",
                    "source_snippet": "The institution should maintain governance...",
                    "chunk_index": 0,
                    "mandatory": "Yes",
                    "confidence": "High",
                }
            ],
            "confirmed_by": "Tobin",
        },
    )

    assert response.status_code == 200
    assert response.json()["doc_id"] == "doc-1"


def test_save_confirmed_not_found_returns_404(client, mock_confirm_service):
    mock_confirm_service.save.side_effect = ValueError("Document unknown not found")

    response = client.post(
        "/confirm/unknown",
        json={"requirements": [], "confirmed_by": "Tobin"},
    )

    assert response.status_code == 404


def test_get_confirmed_success(client, mock_confirm_service):
    mock_confirm_service.get.return_value = {
        "doc_id": "doc-1",
        "confirmed_at": "2026-03-07T00:00:00Z",
        "confirmed_by": "Tobin",
        "total": 1,
        "requirements": [
            {
                "index": 1,
                "requirement_id": "req-1",
                "requirement_type": "Control",
                "description": "Maintain governance framework",
                "source_snippet": "The institution should maintain governance...",
                "chunk_index": 0,
                "mandatory": "Yes",
                "confidence": "High",
            }
        ],
    }

    response = client.get("/confirm/doc-1")

    assert response.status_code == 200
    body = response.json()
    assert body["doc_id"] == "doc-1"
    assert body["total"] == 1


def test_get_confirmed_not_found_returns_404(client, mock_confirm_service):
    mock_confirm_service.get.side_effect = ValueError(
        "Confirmed requirement list for doc-1 not found"
    )

    response = client.get("/confirm/doc-1")

    assert response.status_code == 404
