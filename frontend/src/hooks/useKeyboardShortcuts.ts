import { useEffect } from "react";

export interface KeyboardShortcutHandlers {
  onRunCell?: (cellId: string) => void;
  onDeleteCell?: (cellId: string) => void;
  onAddPythonCell?: () => void;
  onAddSqlCell?: () => void;
  onFocusNext?: () => void;
  onFocusPrevious?: () => void;
}

/**
 * Hook to handle global keyboard shortcuts for notebook operations.
 *
 * Shortcuts (tested to work without conflicts):
 * - Ctrl/Cmd+Shift+Enter: Run focused cell
 * - Ctrl/Cmd+Shift+Backspace: Delete focused cell
 * - Ctrl/Cmd+B: Add new Python cell (B for "Below")
 * - Ctrl/Cmd+L: Add new SQL cell (L for "sQl")
 * - Ctrl/Cmd+↑: Focus previous cell
 * - Ctrl/Cmd+↓: Focus next cell
 */
export function useKeyboardShortcuts(
  handlers: KeyboardShortcutHandlers,
  focusedCellId: string | null
) {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const isMac = navigator.platform.toUpperCase().indexOf("MAC") >= 0;
      const ctrlOrCmd = isMac ? event.metaKey : event.ctrlKey;

      // Ctrl/Cmd+Shift+Enter: Run current cell
      if (ctrlOrCmd && event.shiftKey && event.key === "Enter" && focusedCellId) {
        event.preventDefault();
        handlers.onRunCell?.(focusedCellId);
        return;
      }

      // Ctrl/Cmd+Shift+Backspace: Delete current cell
      if (ctrlOrCmd && event.shiftKey && (event.key === "Backspace" || event.key === "Delete") && focusedCellId) {
        event.preventDefault();
        handlers.onDeleteCell?.(focusedCellId);
        return;
      }

      // Ctrl/Cmd+B: Add Python cell (B for "Below")
      if (ctrlOrCmd && !event.shiftKey && event.key === "b") {
        event.preventDefault();
        handlers.onAddPythonCell?.();
        return;
      }

      // Ctrl/Cmd+L: Add SQL cell (L for "sQl" or "Line")
      if (ctrlOrCmd && !event.shiftKey && event.key === "l") {
        event.preventDefault();
        handlers.onAddSqlCell?.();
        return;
      }

      // Ctrl/Cmd+ArrowUp: Focus previous cell
      if (ctrlOrCmd && event.key === "ArrowUp") {
        event.preventDefault();
        handlers.onFocusPrevious?.();
        return;
      }

      // Ctrl/Cmd+ArrowDown: Focus next cell
      if (ctrlOrCmd && event.key === "ArrowDown") {
        event.preventDefault();
        handlers.onFocusNext?.();
        return;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handlers, focusedCellId]);
}
