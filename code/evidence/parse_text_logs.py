"""Parser for log files and plaintext records."""

import re
from pathlib import Path
from typing import List, Dict, Any, Set


def parse_key_value_log_line(line: str) -> Dict[str, str]:
    """Parses key=value tokens from standard log lines."""
    result: Dict[str, str] = {}
    tokens = re.findall(r'(\w+)=(".*?"|\S+)', line)
    for k, v in tokens:
        clean_v = v.strip('"')
        result[k] = clean_v
    return result


def parse_handover_txt(txt_path: Path) -> List[Dict[str, str]]:
    """Parses customer platform handover text files."""
    results = []
    if not txt_path.exists():
        return results

    with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if line.startswith("-") and "|" in line:
                parts = [p.strip() for p in line.lstrip("-").split("|")]
                if len(parts) >= 6:
                    results.append(
                        {
                            "timestamp": parts[0],
                            "system_id": parts[1],
                            "resource_id": parts[2],
                            "category": parts[3],
                            "status": parts[4],
                            "email": parts[5],
                        }
                    )
    return results


def search_log_lines(
    log_path: Path, identifiers: Set[str]
) -> List[Dict[str, Any]]:
    """Searches a log file for lines mentioning any target identifier."""
    matches = []
    if not log_path.exists():
        return matches

    idents_lower = {i.lower() for i in identifiers if i}

    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        for line_no, line in enumerate(f, start=1):
            line_str = line.strip()
            line_lower = line_str.lower()
            for ident in idents_lower:
                if ident in line_lower:
                    parsed = parse_key_value_log_line(line_str)
                    matches.append(
                        {
                            "line_no": line_no,
                            "line": line_str,
                            "matched_identifier": ident,
                            "parsed": parsed,
                        }
                    )
                    break
    return matches
