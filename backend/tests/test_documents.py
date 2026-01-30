import pytest


def test_list_documents(client, mock_document_service):
    """Test /documents endpoint."""
    mock_document_service.list_documents.return_value = [
        {"doc_id": "doc1", "filename": "test.pdf", "jurisdiction": "HK"}
    ]
    mock_document_service.get_all_jurisdictions.return_value = ["HK"]

    response = client.get("/documents")
    assert response.status_code == 200
    data = response.json()
    assert "documents" in data
    assert len(data["documents"]) == 1
    assert data["documents"][0]["doc_id"] == "doc1"
    assert "jurisdictions" in data


def test_upload_validation(client):
    """Test /upload validation errors."""
    # Missing file
    response = client.post("/upload?jurisdiction=HK")
    assert response.status_code == 422

    # Missing jurisdiction
    response = client.post("/upload", files={"file": ("test.txt", b"content")})
    assert response.status_code == 422


def test_get_document_not_found(client, mock_document_service):
    """Test /documents/{id} 404."""
    mock_document_service.get_document.return_value = None
    response = client.get("/documents/nonexistent")
    assert response.status_code == 404
