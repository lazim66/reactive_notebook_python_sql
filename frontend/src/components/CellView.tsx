import CodeMirror from "@uiw/react-codemirror";
import { python } from "@codemirror/lang-python";
import { sql } from "@codemirror/lang-sql";
import type { Cell, CellType } from "../store/notebookStore";

interface Props {
  cell: Cell;
  onChangeCode: (code: string) => void;
  onChangeType: (type: CellType) => void;
  onRun: () => void;
  onDelete: () => void;
}

const statusClass = (status: Cell["status"]) => {
  switch (status) {
    case "running":
      return "status status-running";
    case "success":
      return "status status-success";
    case "error":
      return "status status-error";
    default:
      return "status status-idle";
  }
};

function CellView({ cell, onChangeCode, onChangeType, onRun, onDelete }: Props) {
  return (
    <div className="cell">
      <div className="cell-header">
        <select value={cell.type} onChange={(e) => onChangeType(e.target.value as CellType)} style={{ padding: "6px 8px", borderRadius: 8, border: "1px solid #cbd5e1" }}>
          <option value="python">Python</option>
          <option value="sql">SQL</option>
        </select>
        <div style={{ display: "flex", gap: 8, alignItems: "center", marginLeft: "auto" }}>
          <span className={statusClass(cell.status)}>{cell.status}</span>
          <button onClick={onRun} style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid #0f172a", background: "#0f172a", color: "#fff" }}>
            Run
          </button>
          <button onClick={onDelete} style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid #e11d48", background: "#fff", color: "#e11d48" }}>
            Delete
          </button>
        </div>
      </div>

      <CodeMirror
        value={cell.code}
        onChange={(value) => onChangeCode(value)}
        height="200px"
        extensions={[cell.type === "python" ? python() : sql()]}
        theme="light"
      />

      {cell.outputs.length > 0 && <div className="outputs">{cell.outputs.join("\n")}</div>}
      {cell.error && <div className="outputs" style={{ background: "#7f1d1d" }}>{cell.error}</div>}
    </div>
  );
}

export default CellView;


