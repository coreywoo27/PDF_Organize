from __future__ import annotations

import queue
import threading
import webbrowser
from pathlib import Path
from tkinter import (
    BOTH,
    DISABLED,
    END,
    EXTENDED,
    LEFT,
    NORMAL,
    RIGHT,
    VERTICAL,
    Button,
    Entry,
    Frame,
    Label,
    LabelFrame,
    Listbox,
    Scrollbar,
    StringVar,
    Text,
    Tk,
    filedialog,
    messagebox,
    ttk,
)

from mat1002_pdf_review import AnalysisResult, run_analysis


APP_TITLE = "PDF Exam Topic Reviewer"
DEFAULT_REPORT_NAME = "pdf_quick_review_report.md"
DEFAULT_JSON_NAME = "pdf_question_analysis.json"


class PdfReviewApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1040x720")
        self.root.minsize(860, 600)

        self.folder_var = StringVar()
        self.output_folder_var = StringVar(value=str(Path.cwd()))
        self.status_var = StringVar(value="Choose a folder to begin.")
        self.pdf_paths: list[Path] = []
        self.result: AnalysisResult | None = None
        self.result_queue: queue.Queue[tuple[str, object]] = queue.Queue()

        self._build_ui()
        self._set_busy(False)

    def _build_ui(self) -> None:
        root_frame = ttk.Frame(self.root, padding=12)
        root_frame.pack(fill=BOTH, expand=True)

        folder_frame = LabelFrame(root_frame, text="PDF Folder", padx=8, pady=8)
        folder_frame.pack(fill="x")

        self.folder_entry = Entry(folder_frame, textvariable=self.folder_var)
        self.folder_entry.pack(side=LEFT, fill="x", expand=True, padx=(0, 8))

        Button(folder_frame, text="Browse", command=self.choose_folder).pack(side=LEFT)
        Button(folder_frame, text="Refresh", command=self.refresh_pdf_list).pack(side=LEFT, padx=(8, 0))

        main_frame = ttk.Frame(root_frame)
        main_frame.pack(fill=BOTH, expand=True, pady=(12, 0))

        list_frame = LabelFrame(main_frame, text="PDF Files", padx=8, pady=8)
        list_frame.pack(side=LEFT, fill=BOTH, expand=False)
        list_frame.configure(width=340)

        self.pdf_listbox = Listbox(list_frame, selectmode=EXTENDED, width=42, height=22)
        list_scrollbar = Scrollbar(list_frame, orient=VERTICAL, command=self.pdf_listbox.yview)
        self.pdf_listbox.configure(yscrollcommand=list_scrollbar.set)
        self.pdf_listbox.pack(side=LEFT, fill=BOTH, expand=True)
        list_scrollbar.pack(side=RIGHT, fill="y")

        list_buttons = ttk.Frame(list_frame)
        list_buttons.pack(fill="x", pady=(8, 0))
        Button(list_buttons, text="Select All", command=self.select_all_pdfs).pack(side=LEFT)
        Button(list_buttons, text="Clear", command=self.clear_pdf_selection).pack(side=LEFT, padx=(8, 0))

        preview_frame = LabelFrame(main_frame, text="Report Preview", padx=8, pady=8)
        preview_frame.pack(side=LEFT, fill=BOTH, expand=True, padx=(12, 0))

        self.preview_text = Text(preview_frame, wrap="word", height=22)
        preview_scrollbar = Scrollbar(preview_frame, orient=VERTICAL, command=self.preview_text.yview)
        self.preview_text.configure(yscrollcommand=preview_scrollbar.set)
        self.preview_text.pack(side=LEFT, fill=BOTH, expand=True)
        preview_scrollbar.pack(side=RIGHT, fill="y")
        self._replace_preview("")

        output_frame = LabelFrame(root_frame, text="Output Folder", padx=8, pady=8)
        output_frame.pack(fill="x", pady=(12, 0))

        self.output_entry = Entry(output_frame, textvariable=self.output_folder_var)
        self.output_entry.pack(side=LEFT, fill="x", expand=True, padx=(0, 8))
        Button(output_frame, text="Browse", command=self.choose_output_folder).pack(side=LEFT)

        action_frame = ttk.Frame(root_frame)
        action_frame.pack(fill="x", pady=(12, 0))

        self.run_button = Button(action_frame, text="Analyze Selected PDFs", command=self.start_analysis)
        self.run_button.pack(side=LEFT)

        self.open_report_button = Button(
            action_frame,
            text="Open Report",
            command=self.open_report,
            state=DISABLED,
        )
        self.open_report_button.pack(side=LEFT, padx=(8, 0))

        self.progress = ttk.Progressbar(action_frame, mode="indeterminate", length=180)
        self.progress.pack(side=LEFT, padx=(12, 0))

        Label(action_frame, textvariable=self.status_var, anchor="w").pack(
            side=LEFT,
            fill="x",
            expand=True,
            padx=(12, 0),
        )

    def choose_folder(self) -> None:
        folder = filedialog.askdirectory(title="Choose PDF folder")
        if not folder:
            return
        self.folder_var.set(folder)
        self.output_folder_var.set(folder)
        self.refresh_pdf_list()

    def choose_output_folder(self) -> None:
        folder = filedialog.askdirectory(title="Choose output folder")
        if folder:
            self.output_folder_var.set(folder)

    def refresh_pdf_list(self) -> None:
        folder = Path(self.folder_var.get()).expanduser()
        self.pdf_listbox.delete(0, END)
        self.pdf_paths = []
        self.result = None
        self.open_report_button.configure(state=DISABLED)
        self._replace_preview("")

        if not folder.exists() or not folder.is_dir():
            self.status_var.set("Choose a valid folder.")
            return

        self.pdf_paths = sorted(folder.glob("*.pdf"), key=lambda path: path.name.lower())
        for path in self.pdf_paths:
            self.pdf_listbox.insert(END, path.name)

        if self.pdf_paths:
            self.select_all_pdfs()
            self.status_var.set(f"Found {len(self.pdf_paths)} PDF file(s).")
        else:
            self.status_var.set("No PDF files found in this folder.")

    def select_all_pdfs(self) -> None:
        self.pdf_listbox.selection_set(0, END)

    def clear_pdf_selection(self) -> None:
        self.pdf_listbox.selection_clear(0, END)

    def selected_pdf_paths(self) -> list[Path]:
        return [self.pdf_paths[index] for index in self.pdf_listbox.curselection()]

    def start_analysis(self) -> None:
        selected = self.selected_pdf_paths()
        if not selected:
            messagebox.showwarning(APP_TITLE, "Select at least one PDF file.")
            return

        output_folder = Path(self.output_folder_var.get()).expanduser()
        if not output_folder.exists() or not output_folder.is_dir():
            messagebox.showwarning(APP_TITLE, "Choose a valid output folder.")
            return

        report_path = output_folder / DEFAULT_REPORT_NAME
        json_path = output_folder / DEFAULT_JSON_NAME

        self._set_busy(True)
        self.status_var.set(f"Analyzing {len(selected)} PDF file(s)...")
        self._replace_preview("")

        worker = threading.Thread(
            target=self._analysis_worker,
            args=(selected, report_path, json_path),
            daemon=True,
        )
        worker.start()
        self.root.after(100, self._poll_result_queue)

    def _analysis_worker(self, pdfs: list[Path], report_path: Path, json_path: Path) -> None:
        try:
            result = run_analysis(pdfs, report_path, json_path)
        except Exception as exc:
            self.result_queue.put(("error", exc))
        else:
            self.result_queue.put(("success", result))

    def _poll_result_queue(self) -> None:
        try:
            kind, payload = self.result_queue.get_nowait()
        except queue.Empty:
            self.root.after(100, self._poll_result_queue)
            return

        self._set_busy(False)
        if kind == "error":
            self.result = None
            self.open_report_button.configure(state=DISABLED)
            self.status_var.set("Analysis failed.")
            messagebox.showerror(APP_TITLE, str(payload))
            return

        result = payload
        if not isinstance(result, AnalysisResult):
            self.status_var.set("Unexpected analysis result.")
            return

        self.result = result
        self.open_report_button.configure(state=NORMAL)
        self._replace_preview(result.report)
        self.status_var.set(
            "Done: "
            f"{len(result.documents)} document(s), "
            f"{len(result.questions)} question(s), "
            f"{len(result.summaries)} topic(s)."
        )

    def open_report(self) -> None:
        if not self.result:
            return
        webbrowser.open(self.result.output_path.resolve().as_uri())

    def _replace_preview(self, text: str) -> None:
        self.preview_text.configure(state=NORMAL)
        self.preview_text.delete("1.0", END)
        self.preview_text.insert("1.0", text)
        self.preview_text.configure(state=DISABLED)

    def _set_busy(self, busy: bool) -> None:
        state = DISABLED if busy else NORMAL
        self.run_button.configure(state=state)
        self.folder_entry.configure(state=state)
        self.output_entry.configure(state=state)
        self.pdf_listbox.configure(state=state)
        if busy:
            self.progress.start(10)
        else:
            self.progress.stop()


def main() -> None:
    root = Tk()
    app = PdfReviewApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
