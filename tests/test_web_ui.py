import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.auth_store import auth_store
from app.main import app
from app.services.qa_service import QAServiceFacade


class WebUITestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = str((Path.cwd() / "tests" / ".tmp_auth.db").resolve())
        db_file = Path(self.db_path)
        if db_file.exists():
            db_file.unlink()
        self.patchers = [
            patch("app.core.config.settings.auth_db_path", self.db_path),
            patch("app.core.config.settings.auth_init_admin_enabled", True),
            patch("app.core.config.settings.auth_init_admin_username", "admin"),
            patch("app.core.config.settings.auth_init_admin_password", "ChangeMe123!"),
            patch("app.core.config.settings.auth_init_admin_display_name", "System Admin"),
            patch("app.main.settings.auth_db_path", self.db_path),
            patch("app.core.auth.settings.auth_db_path", self.db_path),
            patch("app.api.auth_routes.settings.auth_db_path", self.db_path),
        ]
        for patcher in self.patchers:
            patcher.start()
        auth_store._initialized_path = None
        auth_store.init_db()
        auth_store.ensure_admin_user()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        for patcher in reversed(self.patchers):
            patcher.stop()
        db_file = Path(self.db_path)
        if db_file.exists():
            db_file.unlink()

    def login(self, username: str = "admin", password: str = "ChangeMe123!") -> dict:
        response = self.client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_root_redirects_to_login_when_unauthenticated(self) -> None:
        response = self.client.get("/", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["location"], "/login")

    def test_login_page_serves_form(self) -> None:
        response = self.client.get("/login")

        self.assertEqual(response.status_code, 200)
        self.assertIn("员工登录", response.text)
        self.assertIn("/static/login.js", response.text)

    def test_login_success_and_me_endpoint(self) -> None:
        self.login()
        response = self.client.get("/api/v1/auth/me")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["username"], "admin")
        self.assertEqual(payload["role"], "admin")

    def test_login_failure_returns_401(self) -> None:
        response = self.client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "wrong-password"},
        )

        self.assertEqual(response.status_code, 401)

    def test_ask_requires_authentication(self) -> None:
        response = self.client.post("/api/v1/qa/ask", json={"question": "测试问题"})

        self.assertEqual(response.status_code, 401)

    def test_home_page_serves_chat_ui_after_login(self) -> None:
        self.login()
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("企业知识问答", response.text)
        self.assertIn("/static/app.js", response.text)
        self.assertIn("年假政策", response.text)

    def test_stream_api_emits_sse_events(self) -> None:
        self.login()
        with patch("app.api.routes.qa_service.stream_answer") as mock_stream_answer:
            mock_stream_answer.return_value = (iter(["示例", "回答"]), ["data/docs/employee_handbook.md#0"])

            with self.client.stream("POST", "/api/v1/qa/stream", json={"question": "测试问题"}) as response:
                payload = "".join(response.iter_text())

        self.assertEqual(response.status_code, 200)
        self.assertIn("event: token", payload)
        self.assertIn("event: references", payload)
        self.assertIn("event: done", payload)

    def test_auto_mode_falls_back_to_native_when_llamaindex_is_unavailable(self) -> None:
        service = QAServiceFacade()

        with patch("app.services.qa_service.settings.rag_engine", "auto"):
            with patch.object(service._llamaindex, "is_available", return_value=False):
                backend = service._select_backend()

        self.assertIs(backend, service._native)

    def test_admin_can_create_user_and_user_cannot_open_admin_page(self) -> None:
        self.login()
        create_response = self.client.post(
            "/api/v1/admin/users",
            json={
                "username": "alice",
                "display_name": "Alice",
                "password": "AlicePass123",
                "role": "user",
                "is_active": True,
            },
        )
        self.assertEqual(create_response.status_code, 200)

        self.client.post("/api/v1/auth/logout")
        self.login("alice", "AlicePass123")
        admin_response = self.client.get("/admin", follow_redirects=False)

        self.assertEqual(admin_response.status_code, 403)

    def test_admin_can_reset_password(self) -> None:
        self.login()
        create_response = self.client.post(
            "/api/v1/admin/users",
            json={
                "username": "bob",
                "display_name": "Bob",
                "password": "BobPass123",
                "role": "user",
                "is_active": True,
            },
        )
        user_id = create_response.json()["id"]

        reset_response = self.client.post(
            f"/api/v1/admin/users/{user_id}/reset-password",
            json={"password": "NewBobPass123"},
        )
        self.assertEqual(reset_response.status_code, 200)

        self.client.post("/api/v1/auth/logout")
        login_response = self.client.post(
            "/api/v1/auth/login",
            json={"username": "bob", "password": "NewBobPass123"},
        )
        self.assertEqual(login_response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
