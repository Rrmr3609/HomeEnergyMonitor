import json
from backend.app import app

@pytest.fixture
def client():
    return app.test_client()

def test_current_status_endpoint(client):
    resp = client.get("/current_status")
    data = json.loads(resp.data)
    assert "status" in data
    assert "latestPower" in data
