"""Blocked topics: questions about them get a hand-off to a human instead of an answer (no engine call)."""
import re

# Extra words per topic, on top of the topic's own words.
SYNONYMS = {
    "Visa and immigration": ["visa", "immigration", "i-20", "cpt", "sevis", "work permit", "green card"],
    "Mental health": ["mental health", "anxiety", "anxious", "depressed", "depression", "counseling", "therapy", "stress"],
    "Financial aid": ["financial aid", "fafsa", "scholarship", "loan", "tuition aid", "grant"],
    "Grade appeals": ["grade appeal", "appeal", "dispute my grade", "dispute a grade", "change my grade"],
}
OFFICES = {
    "Visa and immigration": "international students office",
    "Mental health": "counseling center",
    "Financial aid": "financial aid office",
    "Grade appeals": "dean's office",
}
STOP_WORDS = {"and", "the", "for", "with"}


def _words(topic: str) -> list[str]:
    own = [word for word in re.findall(r"[a-z0-9-]+", topic.lower()) if len(word) > 3 and word not in STOP_WORDS]
    return SYNONYMS.get(topic, []) + own


def check(text: str, topics: list[str]) -> dict | None:
    """A handoff reply for the first blocked topic the text mentions, else None."""
    lowered = text.lower()
    for topic in topics:
        for word in _words(topic):
            if re.search(rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])", lowered):
                office = OFFICES.get(topic, "right campus office")
                return {
                    "kind": "handoff",
                    "text": f"I can't help with {topic.lower()}. Your advisor or the {office} can — book a meeting or message them.",
                    "payload": {"actions": [{"label": "Book a meeting", "to": "/student/book-meeting"}], "sources": []},
                }
    return None
