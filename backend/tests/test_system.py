def test_healthz(client):
    """Test /healthz endpoint."""
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_stats(client, mock_system_service):
    """Test /stats endpoint."""
    mock_system_service.get_stats.return_value = {
        "documents_count": 10,
        "jurisdictions": 2,
        "requirements_count": 50,
        "policies_count": 5,
    }
    response = client.get("/stats")
    assert response.status_code == 200
    assert response.json()["documents_count"] == 10
    assert response.json()["jurisdictions"] == 2
