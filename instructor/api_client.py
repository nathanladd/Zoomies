import httpx
from typing import Any


def _raise_for_status(resp: httpx.Response) -> None:
    """Raise a RuntimeError with the server's detail message on HTTP error."""
    if resp.is_success:
        return
    detail: str
    try:
        data = resp.json()
        detail = data.get("detail") if isinstance(data, dict) else None
        detail = detail or resp.text
    except Exception:
        detail = resp.text or f"HTTP {resp.status_code}"
    raise RuntimeError(detail)


class ApiClient:
    """Synchronous HTTP client for the instructor app to communicate with the server."""

    def __init__(self, base_url: str = "http://localhost:5000", token: str | None = None):
        self.base_url = base_url
        self.token: str | None = token
        self.role: str = "instructor"
        self.username: str = ""
        self.client = self._make_client(base_url, token)

    @staticmethod
    def _make_client(base_url: str, token: str | None = None) -> httpx.Client:
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return httpx.Client(base_url=base_url, timeout=10.0, headers=headers)

    def set_token(self, token: str) -> None:
        """Update the auth token and rebuild the underlying HTTP client."""
        self.token = token
        self.client.close()
        self.client = self._make_client(self.base_url, token)

    def login(self, username: str, password: str) -> str:
        """Authenticate with the server. Returns the JWT token. Raises RuntimeError on failure."""
        resp = httpx.post(
            f"{self.base_url}/api/auth/login",
            json={"username": username, "password": password},
            timeout=10.0,
        )
        _raise_for_status(resp)
        data = resp.json()
        token = data["token"]
        self.role = data.get("role", "instructor")
        self.username = data.get("username", username)
        self.set_token(token)
        return token

    def close(self):
        self.client.close()

    # ── Topics ─────────────────────────────────────────────────────────────

    def list_topics(self) -> list[dict[str, Any]]:
        resp = self.client.get("/api/topics")
        _raise_for_status(resp)
        return resp.json()

    def get_topic(self, topic_id: int) -> dict[str, Any]:
        resp = self.client.get(f"/api/topics/{topic_id}")
        _raise_for_status(resp)
        return resp.json()

    def create_topic(self, name: str, description: str | None = None) -> dict[str, Any]:
        resp = self.client.post("/api/topics", json={"name": name, "description": description})
        _raise_for_status(resp)
        return resp.json()

    def update_topic(self, topic_id: int, **kwargs) -> dict[str, Any]:
        resp = self.client.put(f"/api/topics/{topic_id}", json=kwargs)
        _raise_for_status(resp)
        return resp.json()

    def delete_topic(self, topic_id: int) -> None:
        resp = self.client.delete(f"/api/topics/{topic_id}")
        _raise_for_status(resp)

    # ── Questions ──────────────────────────────────────────────────────────

    def list_questions(self, topic_id: int | None = None) -> list[dict[str, Any]]:
        params = {}
        if topic_id is not None:
            params["topic_id"] = topic_id
        resp = self.client.get("/api/questions", params=params)
        _raise_for_status(resp)
        return resp.json()

    def get_question(self, question_id: int) -> dict[str, Any]:
        resp = self.client.get(f"/api/questions/{question_id}")
        _raise_for_status(resp)
        return resp.json()

    def create_question(self, data: dict[str, Any]) -> dict[str, Any]:
        resp = self.client.post("/api/questions", json=data)
        _raise_for_status(resp)
        return resp.json()

    def update_question(self, question_id: int, data: dict[str, Any]) -> dict[str, Any]:
        resp = self.client.put(f"/api/questions/{question_id}", json=data)
        _raise_for_status(resp)
        return resp.json()

    def delete_question(self, question_id: int) -> None:
        resp = self.client.delete(f"/api/questions/{question_id}")
        _raise_for_status(resp)

    def upload_image(self, question_id: int, filepath: str) -> dict[str, Any]:
        with open(filepath, "rb") as f:
            resp = self.client.post(
                f"/api/questions/{question_id}/image",
                files={"file": f},
            )
        _raise_for_status(resp)
        return resp.json()

    def delete_image(self, question_id: int) -> None:
        resp = self.client.delete(f"/api/questions/{question_id}/image")
        _raise_for_status(resp)

    def get_question_stats(self, question_id: int) -> dict[str, Any]:
        resp = self.client.get(f"/api/questions/{question_id}/stats")
        _raise_for_status(resp)
        return resp.json()

    def list_question_stats_summary(self) -> list[dict[str, Any]]:
        resp = self.client.get("/api/questions/stats/summary")
        _raise_for_status(resp)
        return resp.json()

    def reset_question_stats(self, question_id: int) -> None:
        resp = self.client.delete(f"/api/questions/{question_id}/stats")
        _raise_for_status(resp)

    # ── Quizzes ────────────────────────────────────────────────────────────

    def list_quizzes(self) -> list[dict[str, Any]]:
        resp = self.client.get("/api/quizzes")
        _raise_for_status(resp)
        return resp.json()

    def get_quiz(self, quiz_id: int) -> dict[str, Any]:
        resp = self.client.get(f"/api/quizzes/{quiz_id}")
        _raise_for_status(resp)
        return resp.json()

    def create_quiz(self, name: str, description: str | None = None, randomize_order: bool = False) -> dict[str, Any]:
        resp = self.client.post("/api/quizzes", json={
            "name": name, "description": description, "randomize_order": randomize_order,
        })
        _raise_for_status(resp)
        return resp.json()

    def update_quiz(self, quiz_id: int, **kwargs) -> dict[str, Any]:
        resp = self.client.put(f"/api/quizzes/{quiz_id}", json=kwargs)
        _raise_for_status(resp)
        return resp.json()

    def delete_quiz(self, quiz_id: int) -> None:
        resp = self.client.delete(f"/api/quizzes/{quiz_id}")
        _raise_for_status(resp)

    def add_question_to_quiz(self, quiz_id: int, question_id: int, position: int | None = None) -> dict[str, Any]:
        data: dict[str, Any] = {"question_id": question_id}
        if position is not None:
            data["position"] = position
        resp = self.client.post(f"/api/quizzes/{quiz_id}/questions", json=data)
        _raise_for_status(resp)
        return resp.json()

    def reorder_quiz_questions(self, quiz_id: int, question_ids: list[int]) -> list[dict[str, Any]]:
        resp = self.client.put(
            f"/api/quizzes/{quiz_id}/questions/reorder",
            json={"question_ids": question_ids},
        )
        _raise_for_status(resp)
        return resp.json()

    def remove_question_from_quiz(self, quiz_id: int, question_id: int) -> None:
        resp = self.client.delete(f"/api/quizzes/{quiz_id}/questions/{question_id}")
        _raise_for_status(resp)

    # ── Games ──────────────────────────────────────────────────────────────

    def list_games(self, quiz_id: int | None = None, status: str | None = None) -> list[dict[str, Any]]:
        params = {}
        if quiz_id is not None:
            params["quiz_id"] = quiz_id
        if status is not None:
            params["status"] = status
        resp = self.client.get("/api/games", params=params)
        _raise_for_status(resp)
        return resp.json()

    def create_game(self, quiz_id: int) -> dict[str, Any]:
        resp = self.client.post("/api/games", json={"quiz_id": quiz_id})
        _raise_for_status(resp)
        return resp.json()

    def init_game(self, game_id: int, question_count: int | None = None, randomize_order: bool | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if question_count is not None:
            body["question_count"] = question_count
        if randomize_order is not None:
            body["randomize_order"] = randomize_order
        resp = self.client.post(f"/api/games/{game_id}/init", json=body)
        _raise_for_status(resp)
        return resp.json()

    def end_game(self, game_id: int) -> dict[str, Any]:
        resp = self.client.put(f"/api/games/{game_id}/end")
        _raise_for_status(resp)
        return resp.json()

    def get_game(self, game_id: int) -> dict[str, Any]:
        resp = self.client.get(f"/api/games/{game_id}")
        _raise_for_status(resp)
        return resp.json()

    def get_game_players(self, game_id: int) -> list[dict[str, Any]]:
        resp = self.client.get(f"/api/games/{game_id}/players")
        _raise_for_status(resp)
        return resp.json()

    def delete_game(self, game_id: int) -> None:
        resp = self.client.delete(f"/api/games/{game_id}")
        _raise_for_status(resp)

    # ── Settings (scoring curve) ───────────────────────────────────────────

    def get_scoring(self) -> dict[str, Any]:
        resp = self.client.get("/api/settings/scoring")
        _raise_for_status(resp)
        return resp.json()

    # ── Account ────────────────────────────────────────────────────────────

    def change_password(self, current_password: str, new_password: str) -> None:
        resp = self.client.post("/api/auth/change-password", json={
            "current_password": current_password,
            "new_password": new_password,
        })
        _raise_for_status(resp)

    # ── User management (admin only) ───────────────────────────────────────

    def list_users(self) -> list[dict[str, Any]]:
        resp = self.client.get("/api/auth/users")
        _raise_for_status(resp)
        return resp.json()

    def create_user(self, username: str, password: str, role: str = "instructor") -> dict[str, Any]:
        resp = self.client.post("/api/auth/users", json={
            "username": username, "password": password, "role": role,
        })
        _raise_for_status(resp)
        return resp.json()

    def patch_user(self, username: str, **kwargs: Any) -> dict[str, Any]:
        resp = self.client.patch(f"/api/auth/users/{username}", json=kwargs)
        _raise_for_status(resp)
        return resp.json()

    def reset_user_password(self, username: str, new_password: str) -> None:
        resp = self.client.post(
            f"/api/auth/users/{username}/reset-password",
            json={"new_password": new_password},
        )
        _raise_for_status(resp)

    def delete_user(self, username: str) -> None:
        resp = self.client.delete(f"/api/auth/users/{username}")
        _raise_for_status(resp)

    def set_scoring(self, points: list[dict[str, Any]]) -> dict[str, Any]:
        resp = self.client.put(
            "/api/settings/scoring",
            json={"points": points},
            timeout=10.0,
        )
        _raise_for_status(resp)
        return resp.json()

    def get_elimination(self) -> dict[str, Any]:
        resp = self.client.get("/api/settings/elimination")
        _raise_for_status(resp)
        return resp.json()

    def set_elimination(self, marks: list[float]) -> dict[str, Any]:
        resp = self.client.put(
            "/api/settings/elimination",
            json={"marks": marks},
            timeout=10.0,
        )
        _raise_for_status(resp)
        return resp.json()
