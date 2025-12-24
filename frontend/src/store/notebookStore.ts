import { useCallback, useState } from "react";

export type CellType = "python" | "sql";
export type CellStatus = "idle" | "running" | "success" | "error";

export interface Cell {
  id: string;
  type: CellType;
  code: string;
  order: number;
  status: CellStatus;
  outputs: string[];
  error?: string | null;
  defs?: string[];
  refs?: string[];
}

export interface NotebookSettings {
  postgresDsn?: string | null;
}

export interface Notebook {
  settings: NotebookSettings;
  cells: Cell[];
}

export function useNotebookStore() {
  const [notebook, setNotebook] = useState<Notebook | null>(null);

  const applyNotebook = useCallback((next: Notebook) => {
    const sorted = {
      ...next,
      cells: [...next.cells].sort((a, b) => a.order - b.order),
    };
    setNotebook(sorted);
  }, []);

  const updateCellLocal = useCallback((cellId: string, patch: Partial<Cell>) => {
    setNotebook((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        cells: prev.cells.map((cell) => (cell.id === cellId ? { ...cell, ...patch } : cell)),
      };
    });
  }, []);

  const upsertCell = useCallback((cell: Cell) => {
    setNotebook((prev) => {
      if (!prev) {
        return { settings: { postgresDsn: null }, cells: [cell] };
      }
      const others = prev.cells.filter((c) => c.id !== cell.id);
      return { ...prev, cells: [...others, cell].sort((a, b) => a.order - b.order) };
    });
  }, []);

  const removeCell = useCallback((cellId: string) => {
    setNotebook((prev) => {
      if (!prev) return prev;
      return { ...prev, cells: prev.cells.filter((cell) => cell.id !== cellId) };
    });
  }, []);

  return { notebook, applyNotebook, updateCellLocal, upsertCell, removeCell, setNotebook };
}


