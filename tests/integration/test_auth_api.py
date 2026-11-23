"""Integration-тести: реєстрація, вхід, захист ендпоінтів (UC-01, UC-02)."""

NEW_USER = {
    "name": "Леся",
    "email": "Lesia@Example.com",
    "phone": "+380671234567",
    "password": "secret123",
}


def test_register_creates_client(api):
    response = api.post("/auth/register", json=NEW_USER)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "lesia@example.com"  # email зберігається в нижньому регістрі
    assert body["role"] == "client"
    assert "password" not in body and "password_hash" not in body


def test_register_duplicate_email_returns_409(api):
    api.post("/auth/register", json=NEW_USER)
    response = api.post("/auth/register", json={**NEW_USER, "email": "LESIA@example.com"})
    assert response.status_code == 409


def test_register_invalid_email_returns_400(api):
    response = api.post("/auth/register", json={**NEW_USER, "email": "not-an-email"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Невалідний email"  # доменна помилка → 400


def test_register_short_password_returns_400(api):
    response = api.post("/auth/register", json={**NEW_USER, "password": "123"})
    assert response.status_code == 400


def test_register_missing_field_returns_400(api):
    response = api.post("/auth/register", json={"name": "Леся"})

    assert response.status_code == 400
    fields = {error["field"] for error in response.json()["errors"]}
    assert fields == {"email", "phone", "password"}


def test_login_returns_token(api):
    api.post("/auth/register", json=NEW_USER)
    response = api.post("/auth/login", json={"email": "lesia@example.com", "password": "secret123"})

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


def test_login_wrong_password_returns_401(api):
    api.post("/auth/register", json=NEW_USER)
    response = api.post("/auth/login", json={"email": "lesia@example.com", "password": "wrong-pass"})
    assert response.status_code == 401


def test_login_unknown_email_returns_401(api):
    response = api.post("/auth/login", json={"email": "nobody@example.com", "password": "secret123"})
    assert response.status_code == 401


def test_me_with_token_returns_current_user(api):
    api.post("/auth/register", json=NEW_USER)
    token = api.post(
        "/auth/login", json={"email": "lesia@example.com", "password": "secret123"}
    ).json()["access_token"]

    response = api.get("/clients/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["email"] == "lesia@example.com"


def test_protected_endpoint_without_token_returns_401(api):
    assert api.get("/clients/me").status_code == 401
    assert api.get("/specialists").status_code == 401
    assert api.get("/appointments").status_code == 401


def test_protected_endpoint_with_invalid_token_returns_401(api):
    response = api.get("/clients/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401
