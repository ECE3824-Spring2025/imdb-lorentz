# tests/test_app.py
import os
import tempfile
import pytest
from app import app, db, Movie

@pytest.fixture
def client(tmp_path, monkeypatch):
    # point your app at a temp users.txt so we don’t clobber your real one
    users_file = tmp_path / "users.txt"
    monkeypatch.setenv("USERS_FILE_PATH", str(users_file))
    # (you’ll need to read os.environ["USERS_FILE_PATH"] instead of hard-coding 'users.txt')
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_home_route(client):
    resp = client.get('/')
    assert resp.status_code == 200
    assert b"Login" in resp.data

def test_register_get(client):
    resp = client.get('/register')
    assert resp.status_code == 200
    assert b"Register" in resp.data

def test_register_post_writes_user(tmp_path, client):
    # POST a new user
    resp = client.post('/register', data={
        'username': 'alice',
        'password': 'wonderland'
    })
    assert resp.status_code == 200
    # it should render registered_popup.html
    assert b"alice" in resp.data

    # now check that the temp file has the encoded user
    users_file = os.environ["USERS_FILE_PATH"]
    with open(users_file) as f:
        lines = f.read().splitlines()
    assert lines == ["alice:wonderland"]

def test_login_success_and_redirect_to_welcome(client, monkeypatch):
    # first write a known user
    users_file = os.environ["USERS_FILE_PATH"]
    with open(users_file, 'w') as f:
        f.write("bob:builder\n")

    resp = client.post('/login', data={'username':'bob','password':'builder'})
    assert resp.status_code == 200
    # should see welcome page greeting
    assert b"Welcome, bob!" in resp.data

def test_login_failure_shows_error(client):
    # no users.txt or wrong creds
    resp = client.post('/login', data={'username':'nobody','password':'nopass'})
    assert resp.status_code == 200
    assert b"Invalid username or password" in resp.data

def test_dashboard_route(client):
    resp = client.get('/dashboard')
    assert resp.status_code == 200
    assert b"IMDB Top 10" in resp.data

def test_logout_redirects_to_login(client):
    resp = client.get('/logout', follow_redirects=True)
    assert resp.status_code == 200
    assert b"Team Lorentz IMDB Login" in resp.data

def test_api_get_movies_empty_db(client):
    # make sure DB is empty
    with app.app_context():
        db.drop_all()
        db.create_all()

    resp = client.get('/api/movies')
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert data == []

def test_api_get_movies_with_one_movie(client):
    with app.app_context():
        db.drop_all()
        db.create_all()
        m = Movie(id="tt9999999", name="Test Film", rating=9.1, votes="1500", genre="Drama")
        db.session.add(m)
        db.session.commit()

    resp = client.get('/api/movies')
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]["id"] == "tt9999999"
    assert data[0]["name"] == "Test Film"
