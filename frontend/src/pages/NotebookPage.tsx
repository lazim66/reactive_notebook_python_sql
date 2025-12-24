import { useCallback, useEffect, useMemo, useState } from "react";
import CellView from "../components/CellView";
import { ErrorBanner } from "../components/ErrorBanner";
import { useDebounce } from "../hooks/useDebounce";
import { createCell, deleteCell, fetchNotebook, runCell, updateCell, updateSettings } from "../lib/apiClient";
import { subscribeToNotebookEvents } from "../lib/sse";
import { CellType, useNotebookStore } from "../store/notebookStore";

function NotebookPage() {
  const { notebook, applyNotebook, upsertCell, updateCellLocal, removeCell } = useNotebookStore();
  const [dsnDraft, setDsnDraft] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const isLoaded = useMemo(() => Boolean(notebook), [notebook]);

  useEffect(() => {
    fetchNotebook()
      .then((data) => {
        applyNotebook(data);
        setDsnDraft(data.settings.postgresDsn ?? "");
      })
      .catch((err) => {
        console.error(err);
        setErrorMessage("Failed to load notebook. Please refresh the page.");
      });
  }, [applyNotebook]);

  useEffect(() => {
    const unsubscribe = subscribeToNotebookEvents((evt) => {
      if (evt.event === "notebook_state") {
        applyNotebook(evt.data);
        setDsnDraft(evt.data.settings.postgresDsn ?? "");
        return;
      }
      // Note: We don't check `notebook` here to avoid dependency issues
      // The event handlers will simply be no-ops if notebook isn't loaded yet
      switch (evt.event) {
        case "cell_status":
          updateCellLocal(evt.data.cellId, { status: evt.data.status as any });
          break;
        case "cell_output":
          updateCellLocal(evt.data.cellId, { outputs: evt.data.outputs, error: null });
          break;
        case "cell_error":
          updateCellLocal(evt.data.cellId, { error: evt.data.error, status: "error" });
          break;
        default:
          break;
      }
    });
    return () => unsubscribe();
  }, [applyNotebook, updateCellLocal]);

  const handleSaveSettings = useCallback(async () => {
    try {
      const updated = await updateSettings({ postgresDsn: dsnDraft });
      applyNotebook(updated);
    } catch (err) {
      console.error(err);
      setErrorMessage("Failed to save settings. Please check your connection.");
    }
  }, [dsnDraft, applyNotebook]);

  const handleAddCell = useCallback(
    async (type: CellType) => {
      try {
        const cell = await createCell({ type, code: type === "python" ? "# python\n" : "-- sql\n" });
        upsertCell(cell);
      } catch (err) {
        console.error(err);
        setErrorMessage("Failed to create cell. Please try again.");
      }
    },
    [upsertCell],
  );

  // Debounced auto-run: runs cell automatically 500ms after code stops changing
  const debouncedAutoRun = useDebounce((cellId: string) => {
    runCell(cellId).catch((err) => {
      console.error("Auto-run failed:", err);
      setErrorMessage("Failed to auto-run cell. Please try running manually.");
    });
  }, 500);

  const handleCodeChange = useCallback(
    async (cellId: string, code: string) => {
      // Immediately update local state for responsive UI
      updateCellLocal(cellId, { code });

      try {
        // Save to backend
        const updated = await updateCell(cellId, { code });
        upsertCell(updated);

        // Trigger debounced auto-run (reactive behavior)
        debouncedAutoRun(cellId);
      } catch (err) {
        console.error(err);
        setErrorMessage("Failed to save cell changes.");
      }
    },
    [updateCellLocal, upsertCell, debouncedAutoRun],
  );

  const handleTypeChange = useCallback(
    async (cellId: string, type: CellType) => {
      updateCellLocal(cellId, { type });
      try {
        const updated = await updateCell(cellId, { type });
        upsertCell(updated);
      } catch (err) {
        console.error(err);
        setErrorMessage("Failed to change cell type.");
      }
    },
    [updateCellLocal, upsertCell],
  );

  const handleDelete = useCallback(
    async (cellId: string) => {
      removeCell(cellId);
      try {
        await deleteCell(cellId);
      } catch (err) {
        console.error(err);
        setErrorMessage("Failed to delete cell.");
      }
    },
    [removeCell],
  );

  const handleRun = useCallback(async (cellId: string) => {
    try {
      await runCell(cellId);
    } catch (err) {
      console.error(err);
      setErrorMessage("Failed to run cell. Check your code and try again.");
    }
  }, []);

  if (!isLoaded) {
    return <p>Loading notebook...</p>;
  }

  return (
    <>
      <ErrorBanner message={errorMessage} onDismiss={() => setErrorMessage(null)} />
      <div className="toolbar">
        <input
          value={dsnDraft}
          onChange={(e) => setDsnDraft(e.target.value)}
          placeholder="Postgres DSN (postgresql://user:pass@host:port/db)"
          style={{ flex: 1, padding: 10, borderRadius: 8, border: "1px solid #cbd5e1" }}
        />
        <button onClick={handleSaveSettings} style={{ padding: "10px 12px", borderRadius: 8, border: "1px solid #0f172a", background: "#0f172a", color: "#fff" }}>
          Save Settings
        </button>
        <button onClick={() => handleAddCell("python")} style={{ padding: "10px 12px", borderRadius: 8, border: "1px solid #cbd5e1" }}>
          + Python
        </button>
        <button onClick={() => handleAddCell("sql")} style={{ padding: "10px 12px", borderRadius: 8, border: "1px solid #cbd5e1" }}>
          + SQL
        </button>
      </div>

      {notebook?.cells.map((cell) => (
        <CellView
          key={cell.id}
          cell={cell}
          onChangeCode={(code) => handleCodeChange(cell.id, code)}
          onChangeType={(type) => handleTypeChange(cell.id, type)}
          onDelete={() => handleDelete(cell.id)}
          onRun={() => handleRun(cell.id)}
        />
      ))}
    </>
  );
}

export default NotebookPage;


