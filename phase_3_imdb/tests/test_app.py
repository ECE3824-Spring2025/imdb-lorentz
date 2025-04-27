# tests/test_app.py
import app

def test_home_route():
    # Create a test client using the Flask application configured for testing
    with app.app_context():
        client = app.app.test_client()
        response = client.get("/")
        assert response.status_code == 200