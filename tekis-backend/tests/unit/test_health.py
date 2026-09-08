from app import create_app


def test_health_check_returns_ok():
    app = create_app("testing")
    client = app.test_client()

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"
