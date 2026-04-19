import random
import time
from typing import Any

from server.config import POINTS_MAX, POINTS_MIN, ELIMINATION_MARKS
from server.game.base import BaseGame
from server.game.scoring import calculate_points
from server.game.elimination import build_elimination_schedule, get_elimination_at_mark


class QuestionState:
    """Runtime state for a single question during a Zündpunkt game."""

    def __init__(
        self,
        question_id: int,
        text: str | None,
        image_filename: str | None,
        correct_answer: str,
        all_choices: list[str],
        time_seconds: int,
        question_type: str,
        display_choices: list[str],
        correct_display: str,
    ):
        self.question_id = question_id
        self.text = text
        self.image_filename = image_filename
        self.correct_answer = correct_answer
        self.all_choices = all_choices
        self.time_seconds = time_seconds
        self.total_ms = time_seconds * 1000
        self.question_type = question_type
        self.display_choices = display_choices
        self.correct_display = correct_display

        self.elimination_schedule = build_elimination_schedule(
            correct_display, display_choices, question_type,
        )
        self.eliminated: list[str] = []
        self.eliminations_fired = 0

        self.started_at: float | None = None
        self.answers: dict[int, dict[str, Any]] = {}  # player_id -> answer info

    def start(self) -> None:
        self.started_at = time.time()

    @property
    def elapsed_ms(self) -> int:
        if self.started_at is None:
            return 0
        return int((time.time() - self.started_at) * 1000)

    @property
    def time_remaining_ms(self) -> int:
        return max(0, self.total_ms - self.elapsed_ms)

    @property
    def current_points(self) -> int:
        return calculate_points(self.elapsed_ms, self.total_ms)

    @property
    def is_expired(self) -> bool:
        return self.elapsed_ms >= self.total_ms

    def check_elimination(self) -> str | None:
        """Check if an elimination should fire. Returns the choice to eliminate or None."""
        if self.question_type == "true_false":
            return None
        progress = self.elapsed_ms / self.total_ms if self.total_ms > 0 else 0
        for i, mark in enumerate(ELIMINATION_MARKS):
            if progress >= mark and self.eliminations_fired <= i:
                choice = get_elimination_at_mark(self.elimination_schedule, i)
                if choice and choice not in self.eliminated:
                    self.eliminated.append(choice)
                    self.eliminations_fired = i + 1
                    return choice
        return None

    def record_answer(self, player_id: int, choice: str, elapsed_ms: int) -> dict[str, Any]:
        """Record a player's answer and return result info."""
        if player_id in self.answers:
            return {"error": "already_answered"}

        if self.is_expired:
            return {"error": "time_expired"}

        if choice in self.eliminated:
            return {"error": "choice_eliminated"}

        is_correct = choice == self.correct_display
        points = calculate_points(elapsed_ms, self.total_ms) if is_correct else 0

        self.answers[player_id] = {
            "choice": choice,
            "elapsed_ms": elapsed_ms,
            "points": points,
            "is_correct": is_correct,
            "correct_answer_text": self.correct_answer,
            "selected_answer_text": self._display_to_stored(choice),
        }
        return self.answers[player_id]

    def _display_to_stored(self, display_choice: str) -> str:
        """Map a display choice back to the original stored answer text."""
        labels = ["A", "B", "C", "D"]
        for i, dc in enumerate(self.display_choices):
            if dc == display_choice:
                idx = i
                break
        else:
            return display_choice

        answers = [self.correct_answer]
        all_wrong = [c for c in self.all_choices if c != self.correct_answer]
        answers.extend(all_wrong)

        for i, dc in enumerate(self.display_choices):
            for ans in [self.correct_answer] + all_wrong:
                if dc == f"{labels[i]}) {ans}":
                    return ans
        return display_choice


class GameEngine(BaseGame):
    """Zündpunkt game state machine."""

    def __init__(
        self,
        game_id: int,
        quiz_name: str,
        questions: list[dict[str, Any]],
        randomize_order: bool = False,
    ):
        self.game_id = game_id
        self.quiz_name = quiz_name
        self.randomize_order = randomize_order

        if randomize_order:
            random.shuffle(questions)
        self.questions_data = questions
        self.question_count = len(questions)

        self.players: dict[int, dict[str, Any]] = {}  # player_id -> {name, score}
        self.current_index = -1
        self.current_question: QuestionState | None = None
        self.status = "waiting"  # waiting / active / revealing / finished

    async def on_player_join(self, player_id: int, name: str) -> dict[str, Any]:
        self.players[player_id] = {"name": name, "score": 0}
        return {
            "player_id": player_id,
            "name": name,
            "player_count": len(self.players),
        }

    async def on_start(self) -> dict[str, Any]:
        self.status = "active"
        return {
            "quiz_name": self.quiz_name,
            "question_count": self.question_count,
        }

    async def on_next_question(self) -> dict[str, Any] | None:
        self.current_index += 1
        if self.current_index >= self.question_count:
            return None

        qdata = self.questions_data[self.current_index]
        choices, correct_display = self._build_display_choices(qdata)

        self.current_question = QuestionState(
            question_id=qdata["id"],
            text=qdata["text"],
            image_filename=qdata["image_filename"],
            correct_answer=qdata["correct_answer"],
            all_choices=self._get_raw_choices(qdata),
            time_seconds=qdata["time_seconds"],
            question_type=qdata["question_type"],
            display_choices=choices,
            correct_display=correct_display,
        )
        self.current_question.start()
        self.status = "active"

        return {
            "index": self.current_index,
            "total": self.question_count,
            "text": qdata["text"],
            "image_url": f"/media/questions/{qdata['image_filename']}" if qdata.get("image_filename") else None,
            "choices": choices,
            "time_seconds": qdata["time_seconds"],
            "max_points": POINTS_MAX,
            "question_type": qdata["question_type"],
        }

    async def on_submit_answer(self, player_id: int, choice: str, elapsed_ms: int) -> dict[str, Any]:
        if not self.current_question:
            return {"error": "no_active_question"}
        if player_id not in self.players:
            return {"error": "unknown_player"}

        result = self.current_question.record_answer(player_id, choice, elapsed_ms)
        if "error" not in result:
            self.players[player_id]["score"] += result["points"]

        return result

    async def on_reveal(self) -> dict[str, Any]:
        if not self.current_question:
            return {"error": "no_active_question"}

        self.status = "revealing"
        q = self.current_question

        player_scores = []
        for pid, pdata in self.players.items():
            ans = q.answers.get(pid)
            player_scores.append({
                "player_id": pid,
                "name": pdata["name"],
                "total_score": pdata["score"],
                "points_earned": ans["points"] if ans else 0,
                "is_correct": ans["is_correct"] if ans else False,
                "selected": ans["choice"] if ans else None,
            })
        player_scores.sort(key=lambda x: x["total_score"], reverse=True)

        return {
            "correct_choice": q.correct_display,
            "player_scores": player_scores,
            "answers_received": len(q.answers),
            "total_players": len(self.players),
        }

    async def on_end(self) -> dict[str, Any]:
        self.status = "finished"
        rankings = sorted(
            [{"player_id": pid, "name": p["name"], "total_score": p["score"]}
             for pid, p in self.players.items()],
            key=lambda x: x["total_score"],
            reverse=True,
        )
        for i, r in enumerate(rankings):
            r["rank"] = i + 1

        return {
            "final_rankings": rankings,
            "question_count": self.question_count,
            "player_count": len(self.players),
        }

    def get_status(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "status": self.status,
            "current_index": self.current_index,
            "question_count": self.question_count,
            "player_count": len(self.players),
            "current_points": self.current_question.current_points if self.current_question else None,
            "time_remaining_ms": self.current_question.time_remaining_ms if self.current_question else None,
        }

    def check_elimination(self) -> str | None:
        if self.current_question:
            return self.current_question.check_elimination()
        return None

    def get_answer_count(self) -> tuple[int, int]:
        answered = len(self.current_question.answers) if self.current_question else 0
        return answered, len(self.players)

    def _get_raw_choices(self, qdata: dict) -> list[str]:
        choices = [qdata["correct_answer"], qdata["wrong_answer_1"]]
        if qdata.get("wrong_answer_2"):
            choices.append(qdata["wrong_answer_2"])
        if qdata.get("wrong_answer_3"):
            choices.append(qdata["wrong_answer_3"])
        return choices

    def _build_display_choices(self, qdata: dict) -> tuple[list[str], str]:
        """Build labeled display choices (A/B/C/D) with randomization rules."""
        labels = ["A", "B", "C", "D"]
        qtype = qdata["question_type"]

        if qtype == "true_false":
            choices = [f"A) True", f"B) False"]
            correct = "A) True" if qdata["correct_answer"].lower() == "true" else "B) False"
            return choices, correct

        if qtype == "technician_ab":
            fixed = [
                "Technician A only",
                "Technician B only",
                "Both Technician A and Technician B",
                "Neither Technician A nor Technician B",
            ]
            choices = [f"{labels[i]}) {fixed[i]}" for i in range(4)]
            correct_map = {"A": 0, "B": 1, "C": 2, "D": 3}
            correct_idx = correct_map.get(qdata["correct_answer"], 0)
            correct = choices[correct_idx]
            return choices, correct

        # multiple_choice: shuffle answers
        raw = self._get_raw_choices(qdata)
        random.shuffle(raw)
        choices = [f"{labels[i]}) {raw[i]}" for i in range(len(raw))]
        correct = next(c for c in choices if c.endswith(f") {qdata['correct_answer']}"))
        return choices, correct
