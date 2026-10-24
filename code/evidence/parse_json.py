"""Parser for JSON evidence records and bundles."""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Set


def load_json_file(json_path: Path) -> Any:
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def search_json_records(
    data: Any, identifiers: Set[str]
) -> List[Dict[str, Any]]:
    """Recursively searches JSON structures for objects containing any target identifiers."""
    matches = []
    idents_lower = {i.lower() for i in identifiers if i}

    def _traverse(node: Any, current_path: str = ""):
        if isinstance(node, dict):
            # Check if this dict itself matches
            for k, v in node.items():
                if isinstance(v, (str, int)):
                    if str(v).strip().lower() in idents_lower:
                        matches.append(
                            {
                                "path": current_path,
                                "matched_field": k,
                                "matched_value": str(v),
                                "record": node,
                            }
                        )
                        break
            for k, v in node.items():
                _traverse(v, f"{current_path}.{k}" if current_path else k)
        elif isinstance(node, list):
            for idx, item in enumerate(node):
                _traverse(item, f"{current_path}[{idx}]")

    _traverse(data)
    return matches
