from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Set


@dataclass(frozen=True)
class AnalysisResult:
    defs: Set[str]
    refs: Set[str]


class _DefRefVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.defs: Set[str] = set()
        self.refs: Set[str] = set()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.defs.add(node.name)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.defs.add(node.name)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.defs.add(node.name)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            self._collect_target(target)
        self.generic_visit(node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._collect_target(node.target)
        if node.value:
            self.generic_visit(node.value)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self._collect_target(node.target)
        self.generic_visit(node.value)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            self.refs.add(node.id)

    def _collect_target(self, target: ast.expr) -> None:
        if isinstance(target, ast.Name):
            self.defs.add(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                self._collect_target(elt)


def extract_defs_refs(code: str) -> AnalysisResult:
    """Extract variable/function/class definitions and references from Python code."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return AnalysisResult(defs=set(), refs=set())

    visitor = _DefRefVisitor()
    visitor.visit(tree)
    # remove defs from refs to reduce false positives
    refs = {ref for ref in visitor.refs if ref not in visitor.defs}
    return AnalysisResult(defs=visitor.defs, refs=refs)


