import random


def build_elimination_schedule(
    correct_answer: str,
    all_choices: list[str],
    question_type: str,
) -> list[str]:
    """Return ordered list of wrong answers to eliminate at 33% and 66% marks.

    For true_false questions, no elimination occurs (returns empty list).
    For multiple_choice and technician_ab, eliminates 2 wrong answers in random order.
    """
    if question_type == "true_false":
        return []

    wrong = [c for c in all_choices if c != correct_answer]
    random.shuffle(wrong)
    return wrong[:2]


def get_elimination_at_mark(
    schedule: list[str],
    mark_index: int,
) -> str | None:
    """Return the choice to eliminate at the given mark (0 = 33%, 1 = 66%).

    Returns None if no elimination is scheduled for this mark.
    """
    if mark_index < len(schedule):
        return schedule[mark_index]
    return None
