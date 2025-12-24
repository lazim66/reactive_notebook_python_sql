import { useCallback, useEffect, useMemo, useState } from "react";
import CellView from "../components/CellView";
import { ErrorBanner } from "../components/ErrorBanner";
import { useDebounce } from "../hooks/useDebounce";
import { useKeyboardShortcuts } from "../hooks/useKeyboardShortcuts";
import { createCell, deleteCell, fetchNotebook, runCell, testConnection, updateCell, updateSettings } from "../lib/apiClient";
import { subscribeToNotebookEvents } from "../lib/sse";
import { CellType, useNotebookStore } from "../store/notebookStore";

type ConnectionStatus = "idle" | "testing" | "success" | "error";

function NotebookPage() {
  const { notebook, applyNotebook, upsertCell, updateCellLocal, removeCell } = useNotebookStore();
  const [dsnDraft, setDsnDraft] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [focusedCellId, setFocusedCellId] = useState<string | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("idle");
  const [connectionMessage, setConnectionMessage] = useState<string>("");
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

      // Test the connection after saving
      if (dsnDraft) {
        setConnectionStatus("testing");
        setConnectionMessage("Testing connection...");

        try {
          const result = await testConnection();
          if (result.status === "success") {
            setConnectionStatus("success");
            setConnectionMessage(result.message);
          } else {
            setConnectionStatus("error");
            setConnectionMessage(result.message);
          }
        } catch (err) {
          setConnectionStatus("error");
          setConnectionMessage("Failed to test connection");
        }
      } else {
        setConnectionStatus("idle");
        setConnectionMessage("");
      }
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
      // Reset code to default template when switching type
      const newCode = type === "python" ? "# Python\n" : "-- SQL\n";
      updateCellLocal(cellId, { type, code: newCode });
      try {
        const updated = await updateCell(cellId, { type, code: newCode });
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

  const focusNextCell = useCallback(() => {
    if (!notebook?.cells.length) return;

    if (!focusedCellId) {
      setFocusedCellId(notebook.cells[0].id);
      return;
    }

    const currentIndex = notebook.cells.findIndex(c => c.id === focusedCellId);
    if (currentIndex < notebook.cells.length - 1) {
      setFocusedCellId(notebook.cells[currentIndex + 1].id);
    }
  }, [notebook, focusedCellId]);

  const focusPreviousCell = useCallback(() => {
    if (!notebook?.cells.length) return;

    if (!focusedCellId) {
      setFocusedCellId(notebook.cells[notebook.cells.length - 1].id);
      return;
    }

    const currentIndex = notebook.cells.findIndex(c => c.id === focusedCellId);
    if (currentIndex > 0) {
      setFocusedCellId(notebook.cells[currentIndex - 1].id);
    }
  }, [notebook, focusedCellId]);

  useKeyboardShortcuts(
    {
      onRunCell: handleRun,
      onDeleteCell: handleDelete,
      onAddPythonCell: () => handleAddCell("python"),
      onAddSqlCell: () => handleAddCell("sql"),
      onFocusNext: focusNextCell,
      onFocusPrevious: focusPreviousCell,
    },
    focusedCellId
  );

  if (!isLoaded) {
    return <p>Loading notebook...</p>;
  }

  const getConnectionIndicator = () => {
    const styles = {
      idle: { color: "#64748b", icon: "⚪" },
      testing: { color: "#eab308", icon: "🟡" },
      success: { color: "#22c55e", icon: "🟢" },
      error: { color: "#ef4444", icon: "🔴" },
    };
    const { color, icon } = styles[connectionStatus];
    return (
      <span style={{ color, fontSize: "12px", display: "flex", alignItems: "center", gap: 4, whiteSpace: "nowrap", minWidth: "fit-content" }}>
        <span>{icon}</span>
        {connectionMessage && <span>{connectionMessage}</span>}
      </span>
    );
  };

  return (
    <>
      <ErrorBanner message={errorMessage} onDismiss={() => setErrorMessage(null)} />
      <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 20 }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <input
            value={dsnDraft}
            onChange={(e) => setDsnDraft(e.target.value)}
            placeholder="Postgres DSN (postgresql://user:pass@host:port/db)"
            style={{ flex: "1 1 200px", minWidth: "200px", padding: 10, borderRadius: 8, border: "1px solid #cbd5e1" }}
          />
          {getConnectionIndicator()}
          <button onClick={handleSaveSettings} style={{ padding: "10px 12px", borderRadius: 8, border: "1px solid #0f172a", background: "#0f172a", color: "#fff", whiteSpace: "nowrap", flexShrink: 0 }}>
            Save Settings
          </button>
        </div>

        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={() => handleAddCell("python")} style={{ padding: "10px 16px", borderRadius: 8, border: "1px solid #0f172a", background: "#fff", color: "#0f172a", fontWeight: 500 }}>
            + Python
          </button>
          <button onClick={() => handleAddCell("sql")} style={{ padding: "10px 16px", borderRadius: 8, border: "1px solid #0f172a", background: "#fff", color: "#0f172a", fontWeight: 500 }}>
            + SQL
          </button>
          <span style={{ marginLeft: "auto", fontSize: "12px", color: "#64748b", alignSelf: "center" }}>
            💡 Ctrl/Cmd+↑/↓: Navigate | Ctrl/Cmd+Shift+Enter: Run | Ctrl/Cmd+Shift+⌫: Delete | Ctrl/Cmd+B: Python | Ctrl/Cmd+L: SQL
          </span>
        </div>
      </div>

      {notebook?.cells.map((cell) => (
        <CellView
          key={cell.id}
          cell={cell}
          isFocused={focusedCellId === cell.id}
          onFocus={() => setFocusedCellId(cell.id)}
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


