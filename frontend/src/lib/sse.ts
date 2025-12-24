import type { Notebook } from "../store/notebookStore";

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

export type NotebookEvent =
  | { event: "notebook_state"; data: Notebook; runId?: number }
  | { event: "run_started"; data: { cellId: string }; runId?: number }
  | { event: "cell_status"; data: { cellId: string; status: string }; runId?: number }
  | { event: "cell_output"; data: { cellId: string; outputs: string[] }; runId?: number }
  | { event: "cell_error"; data: { cellId: string; error: string }; runId?: number }
  | { event: "run_finished"; data: { cellId: string }; runId?: number };

export function subscribeToNotebookEvents(onEvent: (event: NotebookEvent) => void): () => void {
  const source = new EventSource(`${API_BASE}/notebook/events`);
  const eventNames: NotebookEvent["event"][] = [
    "notebook_state",
    "run_started",
    "cell_status",
    "cell_output",
    "cell_error",
    "run_finished",
  ];

  eventNames.forEach((eventName) => {
    source.addEventListener(eventName, (evt) => {
      const parsed = JSON.parse((evt as MessageEvent).data);
      const runId = (evt as MessageEvent).lastEventId ? Number((evt as MessageEvent).lastEventId) : undefined;
      onEvent({ event: eventName, data: parsed, runId } as NotebookEvent);
    });
  });

  source.onerror = (err) => {
    console.error("SSE connection error:", err);
    // EventSource will automatically reconnect, don't close manually
  };

  return () => source.close();
}


