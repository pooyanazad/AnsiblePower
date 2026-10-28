"""Authentication regression tests exercise real credentials, sessions and CSRF."""
import re
import sqlite3
from unittest.mock import patch

import pytest

import ansiblePower
import auth


PASSWORD = "a long test password"


@pytest.fixture()
def client(patched_paths, monkeypatch):
    monkeypatch.setitem(ansiblePower.app.config, "WTF_CSRF_ENABLED", True)
    return ansiblePower.app.test_client()


def csrf_token(client, path="/login"):
    response = client.get(path)
    return re.search(rb'name="csrf-token" content="([^"]+)"', response.data)[1].decode()


def sign_in(client):
    auth.create_admin(ansiblePower.app.config["AUTH_DATABASE"], "admin", PASSWORD)
    return client.post("/login", data={"username": "admin", "password": PASSWORD,
                                      "csrf_token": csrf_token(client)})


def test_local_setup_hashes_password_and_cannot_replace_admin(client):
    runner = ansiblePower.app.test_cli_runner()
    result = runner.invoke(args=["create-admin", "--username", "admin"], input=f"{PASSWORD}\n{PASSWORD}\n")
    assert result.exit_code == 0, result.output
    path = ansiblePower.app.config["AUTH_DATABASE"]
    with sqlite3.connect(path) as conn:
        stored = conn.execute("SELECT password_hash FROM administrator").fetchone()[0]
    assert stored != PASSWORD and PASSWORD not in stored
    assert auth.authenticate(path, "admin", PASSWORD)
    assert not auth.authenticate(path, "admin", "wrong")
    result = runner.invoke(args=["create-admin", "--username", "other"], input=f"{PASSWORD}\n{PASSWORD}\n")
    assert result.exit_code != 0
    assert auth.authenticate(path, "admin", PASSWORD)
    assert __import__("os").stat(path).st_mode & 0o777 == 0o600


def test_setup_rejects_short_password(client):
    with pytest.raises(ValueError):
        auth.create_admin(ansiblePower.app.config["AUTH_DATABASE"], "admin", "short")


@pytest.mark.parametrize("rule", [r for r in ansiblePower.app.url_map.iter_rules()
                                  if r.endpoint not in {"login", "main.health"}])
def test_every_route_requires_identity_even_with_valid_csrf(client, rule):
    token = csrf_token(client)
    path = rule.rule.replace("<int:record_id>", "1").replace("<path:filename>", "js/main.js")
    method = "POST" if "POST" in rule.methods else "GET"
    with patch("ansiblePower.subprocess.check_output") as run, patch("ansiblePower.load_history") as history:
        response = client.open(path, method=method, headers={"Accept": "application/json", "X-CSRFToken": token})
    assert response.status_code == 401, path
    run.assert_not_called()
    history.assert_not_called()


def test_liveness_and_browser_login(client):
    assert client.get("/health").json == {"status": "ok"}
    response = client.get("/")
    assert response.status_code == 302 and response.location == "/login"
    assert b"playbooks_dir" not in client.get("/login").data
    assert client.post("/login", data={"username": "admin", "password": PASSWORD}).status_code == 400
    response = client.post("/login", data={"username": "admin", "password": PASSWORD, "csrf_token": csrf_token(client)})
    assert response.status_code == 401  # No account exists yet.


def test_login_logout_csrf_and_revocation(client):
    old_csrf = csrf_token(client)
    assert sign_in(client).status_code == 302
    cookie = client.get_cookie("session").value
    assert client.get("/").status_code == 200
    assert client.post("/settings/save_hosts", data={"content": "x"}).status_code == 400
    assert client.post("/logout", data={"csrf_token": old_csrf}).status_code == 400
    assert client.get("/logout").status_code == 405
    token = csrf_token(client, "/")
    assert client.post("/logout", data={"csrf_token": token}).status_code == 302
    client.set_cookie("session", cookie)
    assert client.get("/history/export_history").status_code == 401


def test_session_expires_without_sliding_refresh(client):
    assert sign_in(client).status_code == 302
    path = ansiblePower.app.config["AUTH_DATABASE"]
    with auth.database(path) as conn:
        before = conn.execute("SELECT expires FROM sessions").fetchone()[0]
    assert client.get("/settings/").status_code == 200
    with auth.database(path) as conn:
        assert conn.execute("SELECT expires FROM sessions").fetchone()[0] == before
        conn.execute("UPDATE sessions SET expires = 0")
    assert client.get("/settings/get_hosts").status_code == 401


def test_cookie_tampering_is_rejected(client):
    sign_in(client)
    client.set_cookie("session", client.get_cookie("session").value + "tampered")
    assert client.get("/history/export_history").status_code == 401


def test_login_throttling(client):
    token = csrf_token(client)
    for _ in range(5):
        assert client.post("/login", data={"csrf_token": token}).status_code == 401
    assert client.post("/login", data={"csrf_token": token}).status_code == 429


def test_signing_key_is_shared_and_persistent(tmp_path):
    path = str(tmp_path / "auth.db")
    assert auth.signing_key(path) == auth.signing_key(path)
