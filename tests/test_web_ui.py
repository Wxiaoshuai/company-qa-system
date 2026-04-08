import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class WebUITestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_home_page_serves_chat_ui(self) -> None:
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("企业知识问答", response.text)
        self.assertIn("/static/app.js", response.text)
        self.assertIn("年假政策", response.text)

    def test_static_assets_are_served(self) -> None:
        response = self.client.get("/static/styles.css")

        self.assertEqual(response.status_code, 200)
        self.assertIn("composer", response.text)

    def test_ask_api_is_unchanged(self) -> None:
        with patch("app.api.routes.qa_service.answer") as mock_answer:
            class Result:
                answer = "示例回答"
                references = ["data/docs/employee_handbook.md#0"]

            mock_answer.return_value = Result()

            response = self.client.post("/api/v1/qa/ask", json={"question": "测试问题"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "answer": "示例回答",
                "references": ["data/docs/employee_handbook.md#0"],
            },
        )

    def test_stream_api_emits_sse_events(self) -> None:
        with patch("app.api.routes.qa_service.stream_answer") as mock_stream_answer:
            mock_stream_answer.return_value = (iter(["示例", "回答"]), ["data/docs/employee_handbook.md#0"])

            with self.client.stream("POST", "/api/v1/qa/stream", json={"question": "测试问题"}) as response:
                payload = "".join(response.iter_text())

        self.assertEqual(response.status_code, 200)
        self.assertIn("event: token", payload)
        self.assertIn("event: references", payload)
        self.assertIn("event: done", payload)


if __name__ == "__main__":
    unittest.main()
