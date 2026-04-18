"""Quick WebSocket connectivity test."""
import asyncio
import json
import websockets


async def test():
    # First create a session + init game via REST
    import httpx
    c = httpx.Client(base_url="http://localhost:5000", timeout=10)

    # Setup test data
    t = c.post("/api/topics", json={"name": "WS Test Topic"}).json()
    q = c.post("/api/questions", json={
        "topic_id": t["id"], "question_type": "multiple_choice",
        "text": "Test question?", "correct_answer": "A",
        "wrong_answer_1": "B", "wrong_answer_2": "C", "wrong_answer_3": "D",
        "time_seconds": 15,
    }).json()
    qz = c.post("/api/quizzes", json={"name": "WS Test Quiz"}).json()
    c.post(f"/api/quizzes/{qz['id']}/questions", json={"question_id": q["id"]})
    sess = c.post("/api/sessions", json={"quiz_id": qz["id"]}).json()
    init = c.post(f"/api/sessions/{sess['id']}/init-game").json()
    print(f"Session #{sess['id']} created, game init: {init}")

    sid = sess["id"]

    # Connect as instructor
    print("\n--- Connecting instructor WS ---")
    instr_ws = await websockets.connect(f"ws://localhost:5000/ws/instructor/{sid}")
    print(f"Instructor connected: {instr_ws}")

    # Connect as student
    print("\n--- Connecting student WS ---")
    student_ws = await websockets.connect(f"ws://localhost:5000/ws/student/{sid}")
    print(f"Student connected: {student_ws}")

    # Student sends join
    await student_ws.send(json.dumps({"type": "player_join", "name": "TestStudent"}))
    print("Student sent player_join")

    # Read messages on both sides
    for _ in range(5):
        try:
            msg = await asyncio.wait_for(student_ws.recv(), timeout=1)
            print(f"Student got: {json.loads(msg).get('type')}")
        except asyncio.TimeoutError:
            break

    for _ in range(5):
        try:
            msg = await asyncio.wait_for(instr_ws.recv(), timeout=1)
            print(f"Instructor got: {json.loads(msg).get('type')}")
        except asyncio.TimeoutError:
            break

    # Instructor starts game
    print("\n--- Instructor sends start_game ---")
    await instr_ws.send(json.dumps({"type": "start_game"}))
    await asyncio.sleep(0.5)

    for _ in range(5):
        try:
            msg = await asyncio.wait_for(student_ws.recv(), timeout=1)
            parsed = json.loads(msg)
            print(f"Student got: {parsed.get('type')}")
        except asyncio.TimeoutError:
            break

    for _ in range(5):
        try:
            msg = await asyncio.wait_for(instr_ws.recv(), timeout=1)
            parsed = json.loads(msg)
            print(f"Instructor got: {parsed.get('type')}")
        except asyncio.TimeoutError:
            break

    # Instructor sends next_question
    print("\n--- Instructor sends next_question ---")
    await instr_ws.send(json.dumps({"type": "next_question"}))
    await asyncio.sleep(0.5)

    for _ in range(5):
        try:
            msg = await asyncio.wait_for(student_ws.recv(), timeout=1)
            parsed = json.loads(msg)
            print(f"Student got: {parsed.get('type')} -> choices={parsed.get('choices', 'N/A')}")
        except asyncio.TimeoutError:
            break

    for _ in range(5):
        try:
            msg = await asyncio.wait_for(instr_ws.recv(), timeout=1)
            parsed = json.loads(msg)
            print(f"Instructor got: {parsed.get('type')}")
        except asyncio.TimeoutError:
            break

    # Cleanup
    await student_ws.close()
    await instr_ws.close()

    c.delete(f"/api/sessions/{sid}")
    c.delete(f"/api/quizzes/{qz['id']}")
    c.delete(f"/api/questions/{q['id']}")
    c.delete(f"/api/topics/{t['id']}")
    print("\nDone! Cleaned up.")


if __name__ == "__main__":
    asyncio.run(test())
