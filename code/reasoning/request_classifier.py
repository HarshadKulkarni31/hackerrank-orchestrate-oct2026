"""Request intent classifier for distinguishing deletion requests from non-deletion requests."""

import re
from typing import Tuple


NON_DELETION_PATTERNS = [
    r"\bnot\s+asking\s+for\s+deletion\b",
    r"\bnot\s+a\s+request\s+to\s+erase\b",
    r"\bdo\s+not\s+(?:close|delete|erase|remove)\b",
    r"\bdon't\s+(?:close|delete|erase|remove)\b",
    r"\bleave\s+(?:the\s+account|my\s+profile)\b",
    r"\bkeep\s+the\s+account\b",
    r"\bcontinue\s+using\s+the\s+service\b",
    r"\bi\s+still\s+use\s+it\b",
    r"\bwithout\s+removing\b",
    r"\bmarketing\s+lists\s+only\b",
    r"\binformation\s+request\b",
]

NON_DELETION_REGEX = re.compile("|".join(NON_DELETION_PATTERNS), re.IGNORECASE)


def classify_request_intent(request_text: str) -> Tuple[bool, str]:
    """Determines whether request_text authorizes personal data deletion.
    Returns: (is_deletion_authorized, reason)
    """
    clean_text = request_text.strip()
    if not clean_text:
        return False, "Empty request text"

    # Check for explicit non-deletion indicators
    if NON_DELETION_REGEX.search(clean_text):
        return False, "Explicit non-deletion request (access/correction/opt-out/keep account)"

    return True, "Authorized deletion request"
