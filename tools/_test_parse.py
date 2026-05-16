"""Quick parser smoke test — run with: python tools/_test_parse.py"""
import re
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.vault_to_sqlite import _parse_frontmatter, _parse_block

SAMPLE = """\
---
tags:
  - lesson-questions
  - safety
  - machine/s770
  - source/operator-manual
created: 2026-05-07
---

# S770 Safety Questions

---

**Technician A says you should always maintain three points of contact. Technician B says it is safe to jump down. Who is correct?**
- <span style="color:#16a34a">**A. Technician A only**</span>
- B. Technician B only
- C. Both technicians A and B
- D. Neither technician A nor B

> **Source:** S770 OMM pg 108

---

**True or False. It is OK to use a Bobcat loader as a personnel lift.**
- TRUE
- <span style="color:#16a34a">**FALSE**</span>

> **Source:** S770 OMM pg 2

---

**Choose all that apply: Which conditions must be met for functions to operate?**
- <span style="color:#16a34a">**A. Seat bar down**</span>
- <span style="color:#16a34a">**B. Engine running**</span>
- <span style="color:#16a34a">**C. Parking brake released**</span>
- <span style="color:#16a34a">**D. Button activated**</span>

> **Source:** S770 OMM pg 145

---

**What is the function of the evaporator?**
- A. To pump refrigerant
- <span style="color:#16a34a">**B. To absorb heat**</span>
- C. To reject heat
- D. To control refrigerant

> **Source:** HVAC Final Q2.
"""

tags, body = _parse_frontmatter(SAMPLE)
print("Tags:", tags)
print()

blocks = re.split(r'\n---\n', body)
for i, block in enumerate(blocks):
    q, reason = _parse_block(block, tags)
    if q:
        print(f"Q: {q['text'][:60]}")
        print(f"   type   : {q['question_type']}")
        print(f"   correct: {q['correct_answer']}")
        print(f"   wrong1 : {q['wrong_answer_1']}")
        print(f"   wrong2 : {q['wrong_answer_2']}")
        print()
    elif reason:
        print(f"SKIP: {reason}")
        print()

print("Parser test passed.")
