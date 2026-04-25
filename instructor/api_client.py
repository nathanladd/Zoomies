import httpx
from typing import Any

BASE_URL = "http://localhost:5000"


class ApiClient:
    """Synchronous HTTP client for the instructor app to communicate with the server."""

    def __init__(self, base_url: str = BASE_URL):
        self.client = httpx.Client(base_url=base_url, timeout=10.0)

    def close(self):
        self.client.close()

    # ── Topics ─────────────────────────────────────────────────────────────

    def list_topics(self) -> list[dict[str, Any]]:
        return self.client.get("/api/topics").json()

    def get_topic(self, topic_id: int) -> dict[str, Any]:
        return self.client.get(f"/api/topics/{topic_id}").json()

    def create_topic(self, name: str, description: str | None = None) -> dict[str, Any]:
        return self.client.post("/api/topics", json={"name": name, "description": description}).json()

    def update_topic(self, topic_id: int, **kwargs) -> dict[str, Any]:
        return self.client.put(f"/api/topics/{topic_id}", json=kwargs).json()

    def delete_topic(self, topic_id: int) -> None:
        self.client.delete(f"/api/topics/{topic_id}")

    # ── Questions ──────────────────────────────────────────────────────────

    def list_questions(self, topic_id: int | None = None) -> list[dict[str, Any]]:
        params = {}
        if topic_id is not None:
            params["topic_id"] = topic_id
        return self.client.get("/api/questions", params=params).json()

    def get_question(self, question_id: int) -> dict[str, Any]:
        return self.client.get(f"/api/questions/{question_id}").json()

    def create_question(self, data: dict[str, Any]) -> dict[str, Any]:
        return self.client.post("/api/questions", json=data).json()

    def update_question(self, question_id: int, data: dict[str, Any]) -> dict[str, Any]:
        return self.client.put(f"/api/questions/{question_id}", json=data).json()

    def delete_question(self, question_id: int) -> None:
        self.client.delete(f"/api/questions/{question_id}")

    def upload_image(self, question_id: int, filepath: str) -> dict[str, Any]:
        with open(filepath, "rb") as f:
            resp = self.client.post(
                f"/api/questions/{question_id}/image",
                files={"file": f},
            )
        return resp.json()

    def delete_image(self, question_id: int) -> None:
        self.client.delete(f"/api/questions/{question_id}/image")

    # ── Quizzes ────────────────────────────────────────────────────────────

    def list_quizzes(self) -> list[dict[str, Any]]:
        return self.client.get("/api/quizzes").json()

    def get_quiz(self, quiz_id: int) -> dict[str, Any]:
        return self.client.get(f"/api/quizzes/{quiz_id}").json()

    def create_quiz(self, name: str, description: str | None = None, randomize_order: bool = False) -> dict[str, Any]:
        return self.client.post("/api/quizzes", json={
            "name": name, "description": description, "randomize_order": randomize_order,
        }).json()

    def update_quiz(self, quiz_id: int, **kwargs) -> dict[str, Any]:
        return self.client.put(f"/api/quizzes/{quiz_id}", json=kwargs).json()

    def delete_quiz(self, quiz_id: int) -> None:
        self.client.delete(f"/api/quizzes/{quiz_id}")

    def add_question_to_quiz(self, quiz_id: int, question_id: int, position: int | None = None) -> dict[str, Any]:
        data: dict[str, Any] = {"question_id": question_id}
        if position is not None:
            data["position"] = position
        return self.client.post(f"/api/quizzes/{quiz_id}/questions", json=data).json()

    def reorder_quiz_questions(self, quiz_id: int, question_ids: list[int]) -> list[dict[str, Any]]:
        return self.client.put(
            f"/api/quizzes/{quiz_id}/questions/reorder",
            json={"question_ids": question_ids},
        ).json()

    def remove_question_from_quiz(self, quiz_id: int, question_id: int) -> None:
        self.client.delete(f"/api/quizzes/{quiz_id}/questions/{question_id}")

    # ── Games ──────────────────────────────────────────────────────────────

    def list_games(self, quiz_id: int | None = None, status: str | None = None) -> list[dict[str, Any]]:
        params = {}
        if quiz_id is not None:
            params["quiz_id"] = quiz_id
        if status is not None:
            params["status"] = status
        return self.client.get("/api/games", params=params).json()

    def create_game(self, quiz_id: int) -> dict[str, Any]:
        return self.client.post("/api/games", json={"quiz_id": quiz_id}).json()

    def init_game(self, game_id: int) -> dict[str, Any]:
        return self.client.post(f"/api/games/{game_id}/init").json()

    def end_game(self, game_id: int) -> dict[str, Any]:
        return self.client.put(f"/api/games/{game_id}/end").json()

    def get_game(self, game_id: int) -> dict[str, Any]:
        return self.client.get(f"/api/games/{game_id}").json()

    def get_game_players(self, game_id: int) -> list[dict[str, Any]]:
        return self.client.get(f"/api/games/{game_id}/players").json()

    def delete_game(self, game_id: int) -> None:
        self.client.delete(f"/api/games/{game_id}")

    # ── Admin (backup / restore) ────────────────────────────────────────────────────

    def backup_database(self, path: str | None = None) -> dict[str, Any]:
        params = {"path": path} if path else {}
        resp = self.client.post("/api/admin/backup", params=params, timeout=60.0)
        resp.raise_for_status()
        return resp.json()

    def restore_database(self, path: str) -> dict[str, Any]:
        resp = self.client.post("/api/admin/restore", json={"path": path}, timeout=60.0)
        resp.raise_for_status()
        return resp.json()

    # ── Settings (scoring curve) ───────────────────────────────────────────

    def get_scoring(self) -> dict[str, Any]:
        resp = self.client.get("/api/settings/scoring")
        resp.raise_for_status()
        return resp.json()

    def set_scoring(self, points: list[dict[str, Any]]) -> dict[str, Any]:
        resp = self.client.put(
            "/api/settings/scoring",
            json={"points": points},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()
