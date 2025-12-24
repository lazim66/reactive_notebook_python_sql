from __future__ import annotations

from dataclasses import dataclass
from graphlib import CycleError, TopologicalSorter
from typing import Dict, Iterable, List, Set

from ..domain.models import Cell


@dataclass(frozen=True)
class DependencyGraph:
    adjacency: Dict[str, Set[str]]

    def impacted_subgraph(self, root: str) -> Dict[str, Set[str]]:
        impacted: Dict[str, Set[str]] = {}
        stack = [root]
        seen: Set[str] = set()
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            children = self.adjacency.get(current, set())
            impacted[current] = children
            stack.extend(children)
        return impacted

    def topo_order(self, subgraph: Dict[str, Set[str]]) -> List[str]:
        # TopologicalSorter expects {node: dependencies}, but our adjacency is {node: dependents}
        # So we need to invert the graph: for each edge A→B, create B→A
        inverted: Dict[str, Set[str]] = {node: set() for node in subgraph}
        for node, children in subgraph.items():
            for child in children:
                inverted[child].add(node)

        sorter = TopologicalSorter(inverted)
        try:
            return list(sorter.static_order())
        except CycleError as exc:
            raise ValueError(f"Cycle detected: {exc}") from exc


def build_graph(cells: Iterable[Cell]) -> DependencyGraph:
    """Build dependency edges where A -> B if B refs any of A defs."""
    defs_to_cell: Dict[str, str] = {}
    adjacency: Dict[str, Set[str]] = {cell.id: set() for cell in cells}

    for cell in cells:
        for name in cell.defs:
            if name in defs_to_cell and defs_to_cell[name] != cell.id:
                raise ValueError(f"Duplicate definition of '{name}' between {defs_to_cell[name]} and {cell.id}")
            defs_to_cell[name] = cell.id

    for cell in cells:
        for ref in cell.refs:
            upstream = defs_to_cell.get(ref)
            if upstream and upstream != cell.id:
                adjacency.setdefault(upstream, set()).add(cell.id)
    return DependencyGraph(adjacency=adjacency)


