"""End-to-end integration test for Zündpunkt API. Run with: python test_integration.py"""
import httpx
import sys

BASE = "http://localhost:5000"

def main():
    c = httpx.Client(base_url=BASE, timeout=10)
    errors = []

    def check(label, condition, detail=""):
        if not condition:
            errors.append(f"FAIL: {label} {detail}")
            print(f"  FAIL: {label} {detail}")
        else:
            print(f"  OK: {label}")

    # ── Topics ─────────────────────────────────────────────────────────────
    print("\n=== Topics ===")
    t = c.post("/api/topics", json={"name": "Physics", "description": "Mechanics & Thermo"}).json()
    check("Create topic", t.get("id") and t["name"] == "Physics")

    topics = c.get("/api/topics").json()
    check("List topics", len(topics) >= 1)

    t_updated = c.put(f"/api/topics/{t['id']}", json={"name": "Physics 101"}).json()
    check("Update topic", t_updated["name"] == "Physics 101")

    t_detail = c.get(f"/api/topics/{t['id']}").json()
    check("Get topic", t_detail["name"] == "Physics 101")

    # ── Questions ──────────────────────────────────────────────────────────
    print("\n=== Questions ===")
    q1 = c.post("/api/questions", json={
        "topic_id": t["id"], "question_type": "multiple_choice",
        "text": "What is Newton's first law about?",
        "correct_answer": "Inertia", "wrong_answer_1": "Gravity",
        "wrong_answer_2": "Acceleration", "wrong_answer_3": "Momentum",
        "time_seconds": 10,
    }).json()
    check("Create MC question", q1.get("id") and q1["correct_answer"] == "Inertia")

    q2 = c.post("/api/questions", json={
        "topic_id": t["id"], "question_type": "true_false",
        "text": "Gravity on Earth is approximately 9.8 m/s^2.",
        "correct_answer": "True", "wrong_answer_1": "False",
        "time_seconds": 8,
    }).json()
    check("Create TF question", q2.get("id") and q2["question_type"] == "true_false")

    q3 = c.post("/api/questions", json={
        "topic_id": t["id"], "question_type": "multiple_choice",
        "text": "What unit measures force?",
        "correct_answer": "Newton", "wrong_answer_1": "Joule",
        "wrong_answer_2": "Watt", "wrong_answer_3": "Pascal",
        "time_seconds": 12,
    }).json()
    check("Create MC question 2", q3.get("id"))

    questions = c.get("/api/questions").json()
    check("List questions", len(questions) >= 3)

    q1_up = c.put(f"/api/questions/{q1['id']}", json={"time_seconds": 15}).json()
    check("Update question", q1_up["time_seconds"] == 15)

    by_topic = c.get("/api/questions", params={"topic_id": t["id"]}).json()
    check("Filter by topic", len(by_topic) >= 3)

    # ── Quizzes ────────────────────────────────────────────────────────────
    print("\n=== Quizzes ===")
    qz = c.post("/api/quizzes", json={
        "name": "Physics Unit Test", "description": "Chapters 1-3", "randomize_order": True,
    }).json()
    check("Create quiz", qz.get("id") and qz["randomize_order"] is True)

    # Add questions
    for q in [q1, q2, q3]:
        r = c.post(f"/api/quizzes/{qz['id']}/questions", json={"question_id": q["id"]})
        check(f"Add Q{q['id']} to quiz", r.status_code == 201)

    detail = c.get(f"/api/quizzes/{qz['id']}").json()
    check("Quiz detail", detail["question_count"] == 3 and len(detail["questions"]) == 3)

    # Reorder
    ids = [q3["id"], q1["id"], q2["id"]]
    reordered = c.put(f"/api/quizzes/{qz['id']}/questions/reorder", json={"question_ids": ids}).json()
    check("Reorder questions", reordered[0]["question_id"] == q3["id"])

    # Remove and re-add
    r = c.delete(f"/api/quizzes/{qz['id']}/questions/{q2['id']}")
    check("Remove question from quiz", r.status_code == 204)
    detail2 = c.get(f"/api/quizzes/{qz['id']}").json()
    check("Quiz now has 2 questions", detail2["question_count"] == 2)

    c.post(f"/api/quizzes/{qz['id']}/questions", json={"question_id": q2["id"]})

    # ── Games ─────────────────────────────────────────────────────────────────────
    print("\n=== Games ===")
    game = c.post("/api/games", json={"quiz_id": qz["id"]}).json()
    check("Create game", game.get("id") and game["status"] == "waiting")

    game_detail = c.get(f"/api/games/{game['id']}").json()
    check("Get game", game_detail["quiz_name"] == "Physics Unit Test")

    games_list = c.get("/api/games").json()
    check("List games", len(games_list) >= 1)

    # ── Engine Init ──────────────────────────────────────────────────────────────
    print("\n=== Engine Init ===")
    init = c.post(f"/api/games/{game['id']}/init").json()
    check("Init game engine", init.get("status") == "ok" and init["question_count"] == 3)

    # ── Start/End game via REST ───────────────────────────────────────────────────
    started = c.put(f"/api/games/{game['id']}/start").json()
    check("Start game", started["status"] == "active" and started["started_at"] is not None)

    ended = c.put(f"/api/games/{game['id']}/end").json()
    check("End game", ended["status"] == "finished" and ended["ended_at"] is not None)

    # ── Admin backup ────────────────────────────────────────────────────
    print("\n=== Admin ===")
    backup = c.post("/api/admin/backup").json()
    check("Create backup", backup.get("path") and backup.get("size_bytes", 0) > 0)

    # ── Cleanup test: delete ─────────────────────────────────────────────
    print("\n=== Cleanup ===")
    r = c.delete(f"/api/games/{game['id']}")
    check("Delete game", r.status_code == 204)

    r = c.delete(f"/api/quizzes/{qz['id']}")
    check("Delete quiz", r.status_code == 204)

    for q in [q1, q2, q3]:
        r = c.delete(f"/api/questions/{q['id']}")
        check(f"Delete Q{q['id']}", r.status_code == 204)

    r = c.delete(f"/api/topics/{t['id']}")
    check("Delete topic", r.status_code == 204)

    # ── Summary ────────────────────────────────────────────────────────────
    print("\n" + "=" * 50)
    if errors:
        print(f"FAILED: {len(errors)} error(s)")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)
    else:
        print("ALL INTEGRATION TESTS PASSED")


if __name__ == "__main__":
    main()
