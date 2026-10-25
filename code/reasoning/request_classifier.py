"""Request intent classifier for distinguishing authorized deletion requests from non-deletion requests."""

import logging
import re
from typing import Tuple

logger = logging.getLogger("ghost_data_audit.classifier")

# Patterns explicitly expressing non-deletion intent (opt-out, export, access, rectification, keep account)
NON_DELETION_PATTERNS = [
    r"\bnot\s+asking\s+for\s+deletion\b",
    r"\bnot\s+a\s+request\s+to\s+erase\b",
    r"\bdo\s+not\s+(?:close|delete|erase|remove)\b",
    r"\bdon't\s+(?:close|delete|erase|remove)\b",
    r"\bleave\s+(?:the\s+account|my\s+profile|my\s+records|the\s+profile)\b",
    r"\bkeep\s+(?:the\s+account|my\s+account|the\s+profile|my\s+profile)\b",
    r"\bcontinue\s+using\s+(?:the\s+service|the\s+platform|my\s+account)\b",
    r"\bwant\s+to\s+continue\s+using\b",
    r"\bi\s+still\s+use\s+it\b",
    r"\bi\s+still\s+need\s+the\s+account\b",
    r"\bwithout\s+removing\b",
    r"\bmarketing\s+lists\s+only\b",
    r"\bpromotional\s+emails?\b",
    r"\binformation\s+request\b",
    r"\baccess\s+request\b",
    r"\bcan't\s+access\s+my\s+profile\b",
    r"\bresetting\s+the\s+login\b",
    r"\bportable\s+format\b",
    r"\bdownload\s+my\s+account\s+information\b",
    r"\bcopy\s+of\s+(?:the\s+information|last\s+year|my\s+data|my\s+records|invoices)\b",
    r"\bcorrect\s+(?:it|my|the)\b",
    r"\bmisspelled\b",
    r"\bout\s+of\s+date\b",
    r"\bchange\s+the\s+email\s+address\b",
    r"\breplace\s+it\s+with\s+the\s+new\b",
    r"\bleave\s+the\s+account\s+active\b",
    r"\bleave\s+my\s+profile\b",
    r"\bkeep\s+the\s+account\s+as\s+it\s+is\b",
    r"\bdon't\s+delete\s+or\s+change\s+anything\b",
]

NON_DELETION_REGEX = re.compile("|".join(NON_DELETION_PATTERNS), re.IGNORECASE)


def classify_request_intent(request_text: str) -> Tuple[bool, str]:
    """Determines whether request_text authorizes personal data deletion.
    Conservative: rejects requests for access, rectification, portability/export,
    and marketing opt-out.
    Returns: (is_deletion_authorized, reason)
    """
    clean_text = request_text.strip()
    if not clean_text:
        return False, "Empty request text"

    # Check for explicit non-deletion indicators
    if NON_DELETION_REGEX.search(clean_text):
        return False, "Non-deletion request: subject requested access, correction, portability, or marketing opt-out"

    return True, "Authorized deletion request"
