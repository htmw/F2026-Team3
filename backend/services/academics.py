"""Grading math shared by the academic profile, dashboard (spec 10) and courses (spec 11)."""
from typing import Iterable

# (minimum weighted score, letter), highest first.
LETTERS = [(93, "A"), (90, "A-"), (87, "B+"), (83, "B"), (80, "B-"), (77, "C+"), (73, "C"), (70, "C-"), (60, "D")]
POINTS = {"A": 4.0, "A-": 3.7, "B+": 3.3, "B": 3.0, "B-": 2.7, "C+": 2.3, "C": 2.0, "C-": 1.7, "D": 1.0, "F": 0.0}


def gpa(rows: Iterable[tuple[float, float | None]]) -> float | None:
    """GPA over (credits, grade_points) pairs: Σ(grade_points × credits) / Σ credits, 2 dp. Rows without grade points are skipped."""
    quality_points = 0.0
    credits_total = 0.0
    for credits, grade_points in rows:
        if grade_points is None:
            continue
        quality_points += float(grade_points) * float(credits)
        credits_total += float(credits)
    return round(quality_points / credits_total, 2) if credits_total > 0 else None


def letter_for(score: float) -> str:
    for minimum, letter in LETTERS:
        if score >= minimum:
            return letter
    return "F"


def next_letter_up(letter: str) -> str:
    """The next better letter grade ("B+" -> "A-"); "A" stays "A"."""
    letters = [name for _, name in LETTERS]
    if letter not in letters:
        return letters[-1]
    return letters[max(0, letters.index(letter) - 1)]


def points_for(letter: str) -> float | None:
    return POINTS.get(letter)


def weighted_score(items) -> float | None:
    """Σ(score × weight) / Σ weight over graded items (objects with .score and .weight), 1 dp; None if none graded."""
    graded = [item for item in items if item.score is not None]
    weight = sum(float(item.weight) for item in graded)
    if weight <= 0:
        return None
    return round(sum(float(item.score) * float(item.weight) for item in graded) / weight, 1)


def current_grade(items) -> str:
    """Letter grade so far from an enrollment's grade items, or "—" when nothing is graded."""
    score = weighted_score(items)
    return letter_for(score) if score is not None else "—"
