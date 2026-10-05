import re

MENTION_RE = re.compile(r"@(\w+)")
COMPLETION_WORDS = {"selesai", "done", "beres", "kelar"}


def extract_assignee(reply_text: str, replier_name: str) -> str:
    """Whoever the reply @-mentions gets the ticket; otherwise the replier claims it themself."""
    match = MENTION_RE.search(reply_text or "")
    return match.group(1) if match else replier_name


def is_completion(reply_text: str) -> bool:
    words = set(re.findall(r"\w+", (reply_text or "").lower()))
    return bool(words & COMPLETION_WORDS)
