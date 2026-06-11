#!/usr/bin/env python3
"""
vault_to_sqlite.py — Bulk-import Obsidian lesson-question markdown files into Rudi via the REST API.

No external dependencies beyond the Python standard library.

Usage:
    python tools/vault_to_sqlite.py [vault_dir] [--dry-run]
    python tools/vault_to_sqlite.py [vault_dir] --server http://host:port --user instructor --password rudi

Defaults (reads connection.json from the project root if present):
    vault_dir   C:\\Users\\natha\\OneDrive\\Documents\\Vault\\Atlas\\Lesson Questions
    server      https://rudi-server.duckdns.org  (from connection.json)
    user        instructor
    password    rudi

Expected vault layout:
    Lesson Questions/
        Safety/
            S770 Safety Questions.md
        Hydraulics/
            S770 Hydraulics Questions.md
        ...

    Each subdirectory name becomes a topic in Rudi.
    Root-level .md files are skipped (they are index files).

Question file format — questions separated by --- dividers:

    ---
    tags:
      - type/true-false
      - machine/s770
    ---

    **Question text goes here, in bold.**

    - A. Wrong option
    - <span style="color:#16a34a">**B. Correct option (correct)**</span>
    - C. Another wrong option
    - D. Yet another wrong option

    > **Citations:** Operator manual, p. 42.

    ---

    **Next question.**
    ...

Frontmatter tags:
    type/true-false  -> question_type = true_false
    type/tech-a-b    -> question_type = technician_ab
    (default)        -> multiple_choice

"Choose all that apply" questions (multiple green spans) are reported and skipped —
Rudi only supports a single correct answer per question.

Duplicate detection: any question already on the server with the same text + correct
answer is skipped, so it is safe to run this script more than once.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path


# ---------------------------------------------------------------------------
# Markdown parsing
# ---------------------------------------------------------------------------

_CORRECT_SPAN = re.compile(
    r'<span[^>]*color\s*:\s*#16a34a[^>]*>\s*\*\*(.+?)\*\*\s*</span>',
    re.IGNORECASE,
)
_ANSWER_LINE = re.compile(r'^\s*-\s+(?:[A-D]\.\s+)?(\S.+)$')
_QUESTION_LINE = re.compile(r'^\*\*(.+?)\*\*\s*$')
_DISCUSSION_HEADER = re.compile(r'^>\s*\*\*Discussion:\*\*\s*', re.IGNORECASE)
_CITATIONS_HEADER = re.compile(r'^>\s*\*\*Citations:\*\*\s*', re.IGNORECASE)
_BLOCKQUOTE_LINE = re.compile(r'^>\s?')


def _parse_frontmatter(text: str) -> tuple[list[str], str]:
    lines = text.split('\n')
    if not lines or lines[0].strip() != '---':
        return [], text
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == '---':
            fm = '\n'.join(lines[1:i])
            body = '\n'.join(lines[i + 1:])
            tags = re.findall(r'^\s*-\s+([\w][\w/.-]*)$', fm, re.MULTILINE)
            return tags, body
    return [], text


def _question_type(tags: list[str]) -> str:
    for t in tags:
        if 'true-false' in t:
            return 'true_false'
        if 'tech-a-b' in t:
            return 'technician_ab'
    return 'multiple_choice'


def _clean_answer(text: str) -> str:
    text = re.sub(r'^[A-D]\.\s*', '', text)
    text = re.sub(r'\s*\(correct\)\s*$', '', text, flags=re.IGNORECASE)
    return text.strip()


def _parse_block(block: str, tags: list[str]) -> tuple[dict | None, str | None]:
    question_text: str | None = None
    correct_answers: list[str] = []
    wrong_answers: list[str] = []
    discussion: str | None = None
    citations: str | None = None
    _active_field: str | None = None  # 'discussion' | 'citations' | None

    for line in block.split('\n'):
        s = line.strip()

        # Blockquote lines — check for Discussion/Citations headers
        if s.startswith('>'):
            if _DISCUSSION_HEADER.match(s):
                discussion = _DISCUSSION_HEADER.sub('', s).strip() or None
                _active_field = 'discussion'
            elif _CITATIONS_HEADER.match(s):
                citations = _CITATIONS_HEADER.sub('', s).strip() or None
                _active_field = 'citations'
            else:
                # Continuation of the active blockquote field
                continuation = _BLOCKQUOTE_LINE.sub('', s).strip()
                if continuation and _active_field == 'discussion':
                    discussion = ((discussion or '') + ' ' + continuation).strip()
                elif continuation and _active_field == 'citations':
                    citations = ((citations or '') + ' ' + continuation).strip()
            continue

        _active_field = None  # non-blockquote line ends continuation

        m = _CORRECT_SPAN.search(s)
        if m:
            correct_answers.append(_clean_answer(m.group(1)))
            continue
        ma = _ANSWER_LINE.match(s)
        if ma:
            wrong_answers.append(ma.group(1).strip())
            continue
        if not s.startswith(('-', '#')):
            mq = _QUESTION_LINE.match(s)
            if mq:
                question_text = mq.group(1).strip()

    if not question_text:
        return None, None

    if len(correct_answers) > 1:
        return None, f'skipped "choose all" ({len(correct_answers)} correct answers): {question_text[:60]}'

    if not correct_answers or not wrong_answers:
        return None, None

    return {
        'question_type': _question_type(tags),
        'text': question_text,
        'correct_answer': correct_answers[0],
        'wrong_answer_1': wrong_answers[0] if len(wrong_answers) > 0 else None,
        'wrong_answer_2': wrong_answers[1] if len(wrong_answers) > 1 else None,
        'wrong_answer_3': wrong_answers[2] if len(wrong_answers) > 2 else None,
        'discussion': discussion,
        'citations': citations,
    }, None


def parse_vault_file(path: Path) -> tuple[list[dict], list[str]]:
    content = path.read_text(encoding='utf-8')
    tags, body = _parse_frontmatter(content)
    blocks = re.split(r'\n---\n', body)
    questions: list[dict] = []
    skips: list[str] = []
    for block in blocks:
        q, reason = _parse_block(block, tags)
        if q:
            questions.append(q)
        elif reason:
            skips.append(reason)
    return questions, skips


# ---------------------------------------------------------------------------
# REST API client (stdlib only)
# ---------------------------------------------------------------------------

class RudiClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self._token: str | None = None

    def _headers(self) -> dict:
        h = {'Content-Type': 'application/json'}
        if self._token:
            h['Authorization'] = f'Bearer {self._token}'
        return h

    def _request(self, method: str, path: str, body: dict | None = None) -> dict | list:
        url = self.base_url + path
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, headers=self._headers(), method=method)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            detail = e.read().decode()
            try:
                detail = json.loads(detail).get('detail', detail)
            except Exception:
                pass
            raise RuntimeError(f'HTTP {e.code} {method} {path}: {detail}') from None

    def login(self, username: str, password: str) -> None:
        result = self._request('POST', '/api/auth/login',
                               {'username': username, 'password': password})
        self._token = result['token']

    def list_topics(self) -> list[dict]:
        return self._request('GET', '/api/topics')

    def create_topic(self, name: str) -> dict:
        return self._request('POST', '/api/topics', {'name': name})

    def list_questions(self) -> list[dict]:
        return self._request('GET', '/api/questions')

    def create_question(self, data: dict) -> dict:
        return self._request('POST', '/api/questions', data)

    def upsert_note(self, question_id: int, discussion: str | None, citations: str | None) -> dict:
        return self._request('PUT', f'/api/questions/{question_id}/note',
                             {'discussion': discussion, 'citations': citations})


# ---------------------------------------------------------------------------
# Import logic
# ---------------------------------------------------------------------------

def run_import(vault_dir: Path, client: RudiClient, dry_run: bool) -> None:
    if not vault_dir.exists():
        sys.exit(f'ERROR: vault directory not found:\n  {vault_dir}')

    topic_map: dict[str, int] = {}
    existing_keys: set[tuple[str, str]] = set()

    if not dry_run:
        print('Connecting to server...')
        topics_list: list[dict] = client.list_topics()
        topic_map = {t['name']: t['id'] for t in topics_list}

        print('Fetching existing questions for duplicate check...')
        existing = client.list_questions()
        existing_keys = {
            (q['text'], q['correct_answer']) for q in existing
            if q.get('text') and q.get('correct_answer')
        }
        print(f'  {len(existing_keys)} questions already on server\n')

    md_files = [p for p in sorted(vault_dir.rglob('*.md')) if p.parent != vault_dir]
    if not md_files:
        print('No question files found in subdirectories of the vault dir.')
        return

    created = skipped_dupes = skipped_empty = 0
    errors: list[str] = []

    for md_path in md_files:
        topic_name = md_path.parent.name
        try:
            questions, skips = parse_vault_file(md_path)
        except Exception as exc:
            errors.append(f'{md_path.relative_to(vault_dir)}: {exc}')
            continue

        rel = md_path.relative_to(vault_dir)

        for skip_msg in skips:
            print(f'  ! {skip_msg}')

        if not questions:
            skipped_empty += 1
            continue

        print(f'[{topic_name}]  {rel}  --  {len(questions)} question(s)')

        for q in questions:
            preview = (q['text'] or '')[:72]
            key = (q['text'], q['correct_answer'])

            if key in existing_keys:
                print(f'  = (duplicate) {preview}')
                skipped_dupes += 1
                continue

            if dry_run:
                print(f'  > {preview}')
                created += 1
                continue

            # Ensure topic exists
            if topic_name not in topic_map:
                new_topic = client.create_topic(topic_name)
                topic_map[topic_name] = new_topic['id']
                print(f'  + topic created: {topic_name}')

            payload = {
                'topic_id': topic_map[topic_name],
                'question_type': q['question_type'],
                'text': q['text'],
                'correct_answer': q['correct_answer'],
                'wrong_answer_1': q['wrong_answer_1'],
                'wrong_answer_2': q['wrong_answer_2'],
                'wrong_answer_3': q['wrong_answer_3'],
                'time_seconds': 20,
                'randomize_answers': True,
                'correct_index': 0,
            }
            try:
                created_q = client.create_question(payload)
                existing_keys.add(key)
                print(f'  + {preview}')
                created += 1

                if q.get('discussion') or q.get('citations'):
                    try:
                        client.upsert_note(created_q['id'], q.get('discussion'), q.get('citations'))
                    except RuntimeError as exc:
                        print(f'    ! note failed: {exc}')
            except RuntimeError as exc:
                errors.append(f'{preview[:40]}: {exc}')
                print(f'  X ERROR: {exc}')

        print()

    action = 'Would import' if dry_run else 'Imported'
    print(f'{action}: {created}')
    if skipped_dupes:
        print(f'Duplicates skipped: {skipped_dupes}')
    if skipped_empty:
        print(f'Empty files skipped: {skipped_empty}')
    if errors:
        print(f'Errors: {len(errors)}')
        for e in errors:
            print(f'  {e}')


# ---------------------------------------------------------------------------
# Connection defaults and entry point
# ---------------------------------------------------------------------------

_VAULT_DEFAULT = Path(r'C:\Users\natha\OneDrive\Documents\Vault\Atlas\Lesson Questions')
_CONN_FILE = Path(__file__).resolve().parent.parent / 'connection.json'


def _load_connection_defaults() -> dict:
    if _CONN_FILE.exists():
        data = json.loads(_CONN_FILE.read_text())
        host = data.get('server_host', 'localhost')
        port = data.get('server_port', 80)
        scheme = 'https' if port == 443 else 'http'
        url = f'{scheme}://{host}' if port in (80, 443) else f'{scheme}://{host}:{port}'
        return {
            'server': url,
            'username': data.get('username', 'instructor'),
            'password': data.get('password', 'rudi'),
        }
    return {'server': 'http://localhost:5000', 'username': 'instructor', 'password': 'rudi'}


def main() -> None:
    defaults = _load_connection_defaults()

    ap = argparse.ArgumentParser(
        description='Import Obsidian lesson-question markdown files into Rudi via the REST API.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument('vault_dir', nargs='?', type=Path, default=_VAULT_DEFAULT,
                    help='Lesson Questions folder in the vault')
    ap.add_argument('--server', default=defaults['server'],
                    help=f'Server base URL (default: {defaults["server"]})')
    ap.add_argument('--user', default=defaults['username'],
                    help=f'Instructor username (default: {defaults["username"]})')
    ap.add_argument('--password', default=defaults['password'],
                    help='Instructor password')
    ap.add_argument('--dry-run', action='store_true',
                    help='Parse and preview without writing anything to the server')
    args = ap.parse_args()

    print(f'Vault  : {args.vault_dir}')
    print(f'Server : {args.server}')
    if args.dry_run:
        print('Mode   : DRY RUN -- nothing will be sent to the server\n')
    else:
        print()

    client = RudiClient(args.server)
    if not args.dry_run:
        print(f'Logging in as {args.user}...')
        try:
            client.login(args.user, args.password)
            print('Login OK\n')
        except RuntimeError as exc:
            sys.exit(f'Login failed: {exc}')

    run_import(args.vault_dir, client, args.dry_run)


if __name__ == '__main__':
    main()
