#!/usr/bin/env python3
"""
verify_notes.py — Report which questions on a Zoomies server have a
Discussion/References note attached.

Use this to confirm whether the "Discussion & References" panel in the
instructor app has any data to show. It hits the same REST endpoints the
instructor app uses (login + GET /api/questions/{id}/note), so a note that
shows up here is a note the app can display.

No external dependencies beyond the Python standard library.

Usage:
    python tools/verify_notes.py --user instructor --password SECRET
    python tools/verify_notes.py --server https://zoomies.rudi-hq.com --user me --password SECRET
    python tools/verify_notes.py --user me --password SECRET --limit 0   # scan all questions

Server defaults come from connection.json in the project root (same file the
apps read); pass --server to override. If --password is omitted you are
prompted for it (input hidden).
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

_CONN_FILE = Path(__file__).resolve().parent.parent / "connection.json"


def _server_default() -> str:
    if _CONN_FILE.exists():
        try:
            data = json.loads(_CONN_FILE.read_text())
            host = data.get("server_host", "localhost")
            port = data.get("server_port", 5000)
            scheme = "https" if port == 443 else "http"
            if port in (80, 443):
                return f"{scheme}://{host}"
            return f"{scheme}://{host}:{port}"
        except Exception:
            pass
    return "http://localhost:5000"


def _request(base: str, method: str, path: str, body: dict | None = None,
             token: str | None = None) -> tuple[int, object]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        detail = e.read().decode()
        try:
            detail = json.loads(detail).get("detail", detail)
        except Exception:
            pass
        return e.code, detail
    except urllib.error.URLError as e:
        return 0, str(e.reason)


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(
        description="Report which questions on a Zoomies server have a note.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--server", default=_server_default(),
                    help=f"Server base URL (default: {_server_default()})")
    ap.add_argument("--user", required=True, help="Instructor/admin username")
    ap.add_argument("--password", default=None,
                    help="Password (prompted if omitted)")
    ap.add_argument("--limit", type=int, default=50,
                    help="How many questions to scan; 0 = all (default: 50)")
    args = ap.parse_args()

    base = args.server.rstrip("/")
    password = args.password or getpass.getpass(f"Password for {args.user}: ")

    print(f"Server : {base}")

    st, res = _request(base, "POST", "/api/auth/login",
                       {"username": args.user, "password": password})
    if st != 200:
        sys.exit(f"Login failed (HTTP {st}): {res}")
    token = res["token"]
    print(f"Login  : OK as {args.user}\n")

    st, questions = _request(base, "GET", "/api/questions", token=token)
    if st != 200 or not isinstance(questions, list):
        sys.exit(f"Failed to list questions (HTTP {st}): {questions}")

    scan = questions if args.limit == 0 else questions[: args.limit]
    print(f"Questions on server : {len(questions)}")
    print(f"Scanning            : {len(scan)}"
          f"{' (all)' if args.limit == 0 else f' (first {args.limit}; use --limit 0 for all)'}\n")

    with_note = 0
    errors = 0
    for q in scan:
        qid = q["id"]
        st, note = _request(base, "GET", f"/api/questions/{qid}/note", token=token)
        if st == 404:
            continue  # no note for this question — expected, stay quiet
        if st != 200 or not isinstance(note, dict):
            errors += 1
            print(f"  ! qid={qid} unexpected response (HTTP {st}): {note}")
            continue
        discussion = (note.get("discussion") or "").strip()
        citations = (note.get("citations") or "").strip()
        if not discussion and not citations:
            continue  # row exists but both fields empty — nothing to show
        with_note += 1
        preview = (q.get("text") or "")[:60]
        print(f"  ✓ qid={qid}  {preview}")
        if discussion:
            print(f"      discussion: {discussion[:80]}")
        if citations:
            print(f"      citations : {citations[:80]}")

    print()
    print(f"Result: {with_note} of {len(scan)} scanned question(s) have a "
          f"displayable note.")
    if errors:
        print(f"        {errors} question(s) returned an unexpected error.")
    if with_note == 0:
        print("\nNo notes found on this server. The instructor app's "
              "'Discussion & References' panel will stay hidden until notes "
              "are imported here (run tools/vault_to_sqlite.py against THIS "
              "server).")


if __name__ == "__main__":
    main()
