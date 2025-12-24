from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Set


PLACEHOLDER_PATTERN = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")


@dataclass(frozen=True)
class AnalysisResult:
    defs: Set[str]
    refs: Set[str]


def extract_defs_refs(code: str) -> AnalysisResult:
    """Extract references from SQL code using {{var}} placeholders."""
    refs = set(PLACEHOLDER_PATTERN.findall(code))
    return AnalysisResult(defs=set(), refs=refs)


