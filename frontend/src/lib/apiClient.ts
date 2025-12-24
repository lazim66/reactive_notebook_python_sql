import type { Cell, CellType, Notebook, NotebookSettings } from "../store/notebookStore";

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
    },
    ...options,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export async function fetchNotebook(): Promise<Notebook> {
  return request<Notebook>("/notebook");
}

export async function updateSettings(settings: NotebookSettings): Promise<Notebook> {
  return request<Notebook>("/notebook/settings", {
    method: "PATCH",
    body: JSON.stringify(settings),
  });
}

export async function createCell(payload: { type: CellType; code?: string }): Promise<Cell> {
  return request<Cell>("/notebook/cells", {
    method: "POST",
    body: JSON.stringify({ type: payload.type, code: payload.code ?? "" }),
  });
}

export async function updateCell(cellId: string, payload: Partial<Pick<Cell, "code" | "type">>): Promise<Cell> {
  return request<Cell>(`/notebook/cells/${cellId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function deleteCell(cellId: string): Promise<void> {
  await request(`/notebook/cells/${cellId}`, { method: "DELETE" });
}

export async function runCell(cellId: string): Promise<{ runId: number }> {
  return request<{ runId: number }>("/notebook/run", {
    method: "POST",
    body: JSON.stringify({ cellId }),
  });
}

export async function testConnection(): Promise<{ status: string; message: string }> {
  return request<{ status: string; message: string }>("/notebook/test-connection", {
    method: "POST",
  });
}


