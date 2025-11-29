# tests/test_profiles.py

from starlette.testclient import TestClient
from sqlalchemy.orm import Session


def _create_profile(
    client: TestClient,
    display_name: str = "Alice",
    avatar_url: str | None = None,
):
    """テスト用のプロフィール作成ヘルパー"""
    payload = {"display_name": display_name}
    if avatar_url is not None:
        payload["avatar_url"] = avatar_url

    res = client.post("/api/profiles", json=payload)
    assert res.status_code in (200, 201)
    return res.json()


def test_create_and_get_profile(client: TestClient, db: Session):
    """プロフィールを作成して、GET で取得できること"""
    created = _create_profile(client, "TestUser")
    profile_id = created["id"]

    res = client.get(f"/api/profiles/{profile_id}")
    assert res.status_code == 200

    body = res.json()
    assert body["id"] == profile_id
    assert body["display_name"] == "TestUser"
    # is_deleted がレスポンスに含まれる前提（なければこの行は消してOK）
    assert body.get("is_deleted") in (False, None)


def test_get_nonexistent_profile_returns_404(client: TestClient, db: Session):
    """存在しないプロフィールを取得しようとすると 404"""
    res = client.get("/api/profiles/nonexistent-id-123")
    assert res.status_code == 404


def test_list_profiles_returns_created_profiles(client: TestClient, db: Session):
    """一覧に作成済みプロフィールが含まれること"""
    p1 = _create_profile(client, "User1")
    p2 = _create_profile(client, "User2")

    res = client.get("/api/profiles")
    assert res.status_code == 200

    items = res.json()
    ids = {p["id"] for p in items}

    assert p1["id"] in ids
    assert p2["id"] in ids


def test_delete_profile_and_exclude_from_list(client: TestClient, db: Session):
    """
    DELETE したプロフィールは一覧から除外されること
    ついでに GET /profiles/{id} も 404 になる想定
    """
    alive = _create_profile(client, "AliveUser")
    to_delete = _create_profile(client, "DeleteMe")

    # 対象を削除
    res_del = client.delete(f"/api/profiles/{to_delete['id']}")
    assert res_del.status_code in (200, 204)

    # 一覧からは除外されている
    res_list = client.get("/api/profiles")
    assert res_list.status_code == 200
    items = res_list.json()
    ids = {p["id"] for p in items}

    assert alive["id"] in ids
    assert to_delete["id"] not in ids

    # 個別 GET も 404 になる仕様にしておくと扱いやすい
    res_get = client.get(f"/api/profiles/{to_delete['id']}")
    assert res_get.status_code == 404


def test_delete_nonexistent_profile_returns_404(client: TestClient, db: Session):
    """存在しないプロフィールを DELETE しようとすると 404"""
    res = client.delete("/api/profiles/nonexistent-id-456")
    assert res.status_code == 404
