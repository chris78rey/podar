from __future__ import annotations

import threading
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from queue import Empty, Queue
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from .organiza_planillas import main as organiza_main
    from .organiza_planillas_core import (
        build_destination_expediente_map,
        normalize_code,
        read_rows_from_excel,
        select_rows_with_highest_expediente,
    )
except ImportError:  # pragma: no cover - direct script execution fallback
    from organiza_planillas import main as organiza_main
    from organiza_planillas_core import (
        build_destination_expediente_map,
        normalize_code,
        read_rows_from_excel,
        select_rows_with_highest_expediente,
    )


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("OrganizaPlanillas")
        self.geometry("900x720")

        self.var_source = tk.StringVar()
        self.var_dest = tk.StringVar()
        self.var_excel = tk.StringVar()
        self.var_include_id_tramite = tk.BooleanVar(value=True)
        self.var_filter_one = tk.BooleanVar(value=False)
        self.var_dig_id_tramite = tk.StringVar()
        self.var_dry_run = tk.BooleanVar(value=False)

        self._output_queue: Queue[tuple[str, object]] = Queue()
        self._task_running = False
        self._done_ok_text = ""
        self._done_fail_text = ""

        self.btn_run: ttk.Button | None = None
        self.btn_test: ttk.Button | None = None

        self._build_form()
        self.after(100, self._drain_output_queue)

    def _build_form(self) -> None:
        pad = {"padx": 8, "pady": 6}
        frm = ttk.Frame(self)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="Source base").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.var_source, width=75).grid(row=0, column=1, **pad)
        ttk.Button(frm, text="Elegir", command=self.pick_source).grid(row=0, column=2, **pad)

        ttk.Label(frm, text="Dest base").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.var_dest, width=75).grid(row=1, column=1, **pad)
        ttk.Button(frm, text="Elegir", command=self.pick_dest).grid(row=1, column=2, **pad)

        ttk.Label(frm, text="Archivo Excel").grid(row=2, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.var_excel, width=75).grid(row=2, column=1, **pad)
        ttk.Button(frm, text="Elegir", command=self.pick_excel).grid(row=2, column=2, **pad)

        ttk.Checkbutton(
            frm,
            text="Procesar solo un dig_id_tramite",
            variable=self.var_filter_one,
            command=self._toggle_filter_state,
        ).grid(row=3, column=1, sticky="w", **pad)

        self.ent_dig_id_tramite = ttk.Entry(frm, textvariable=self.var_dig_id_tramite, width=20)
        self.ent_dig_id_tramite.grid(row=4, column=1, sticky="w", **pad)
        self.ent_dig_id_tramite.configure(state=tk.DISABLED)
        ttk.Label(frm, text="dig_id_tramite").grid(row=4, column=0, sticky="w", **pad)

        ttk.Checkbutton(
            frm,
            text="Incluir dig_id_tramite en la ruta",
            variable=self.var_include_id_tramite,
        ).grid(row=5, column=1, sticky="w", **pad)

        ttk.Checkbutton(
            frm,
            text="Dry-run",
            variable=self.var_dry_run,
        ).grid(row=6, column=1, sticky="w", **pad)

        btns = ttk.Frame(frm)
        btns.grid(row=7, column=0, columnspan=3, sticky="w", **pad)
        self.btn_test = ttk.Button(btns, text="Validar Excel", command=self.validate_excel)
        self.btn_test.pack(side=tk.LEFT, padx=4)
        self.btn_run = ttk.Button(btns, text="Ejecutar", command=self.run_organize)
        self.btn_run.pack(side=tk.LEFT, padx=4)

        ttk.Label(frm, text="Salida").grid(row=8, column=0, sticky="nw", **pad)
        self.txt = tk.Text(frm, height=24)
        self.txt.grid(row=8, column=1, columnspan=2, sticky="nsew", **pad)

        frm.rowconfigure(8, weight=1)
        frm.columnconfigure(1, weight=1)

    def _toggle_filter_state(self) -> None:
        state = tk.NORMAL if self.var_filter_one.get() else tk.DISABLED
        self.ent_dig_id_tramite.configure(state=state)

    def pick_source(self) -> None:
        path = filedialog.askdirectory(title="Select source base")
        if path:
            self.var_source.set(path)

    def pick_dest(self) -> None:
        path = filedialog.askdirectory(title="Select dest base")
        if path:
            self.var_dest.set(path)

    def pick_excel(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Excel file",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
        )
        if path:
            self.var_excel.set(path)

    def append_out(self, text: str) -> None:
        self.txt.insert(tk.END, text + "\n")
        self.txt.see(tk.END)

    class _QueueWriter:
        def __init__(self, queue: Queue):
            self.queue = queue
            self._buffer = ""

        def write(self, data: str):
            if not data:
                return 0
            self._buffer += data
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                if line or self._buffer:
                    self.queue.put(("line", line.rstrip("\r")))
            return len(data)

        def flush(self):
            if self._buffer:
                self.queue.put(("line", self._buffer.rstrip("\r")))
                self._buffer = ""

    def _set_task_state(self, running: bool) -> None:
        self._task_running = running
        state = tk.DISABLED if running else tk.NORMAL
        if self.btn_test is not None:
            self.btn_test.configure(state=state)
        if self.btn_run is not None:
            self.btn_run.configure(state=state)
        self.configure(cursor="watch" if running else "")
        self.update_idletasks()

    def _queue_text(self, text: str) -> None:
        for line in text.splitlines():
            if line.strip():
                self._output_queue.put(("line", line.rstrip()))

    def _start_job(self, runner, ok_text: str, fail_text: str, title: str, summary: list[str] | None = None) -> None:
        if self._task_running:
            messagebox.showinfo("En curso", "Ya hay una tarea en ejecucion.")
            return

        self.append_out(f"== {title} ==")
        if summary:
            for line in summary:
                self.append_out(line)
        self._done_ok_text = ok_text
        self._done_fail_text = fail_text
        self._set_task_state(True)

        def worker():
            writer = self._QueueWriter(self._output_queue)
            try:
                with redirect_stdout(writer), redirect_stderr(writer):
                    code = runner()
                if code is None:
                    code = 0
                self._output_queue.put(("done", int(code)))
            except Exception:
                self._queue_text(traceback.format_exc())
                self._output_queue.put(("done", 1))
            finally:
                writer.flush()

        threading.Thread(target=worker, daemon=True).start()

    def _drain_output_queue(self) -> None:
        if not self.winfo_exists():
            return
        try:
            while True:
                kind, payload = self._output_queue.get_nowait()
                if kind == "line":
                    self.append_out(str(payload))
                elif kind == "done":
                    code = int(payload)
                    self._set_task_state(False)
                    if code == 0:
                        messagebox.showinfo("Tarea completada", self._done_ok_text)
                    else:
                        messagebox.showwarning("Tarea fallida", self._done_fail_text)
        except Empty:
            pass
        finally:
            if self.winfo_exists():
                self.after(100, self._drain_output_queue)

    def _build_args(self) -> list[str]:
        src = self.var_source.get().strip()
        dst = self.var_dest.get().strip()
        excel = self.var_excel.get().strip()
        if not src or not dst or not excel:
            raise ValueError("Source base, dest base y archivo Excel son obligatorios")

        args = [
            "--source-base",
            src,
            "--dest-base",
            dst,
            "--excel",
            excel,
        ]
        if self.var_filter_one.get():
            dig_id_tramite = self.var_dig_id_tramite.get().strip()
            if not dig_id_tramite:
                raise ValueError("Marca el filtro de dig_id_tramite y escribe un valor")
            args.extend(["--dig-id-tramite", dig_id_tramite])
        if not self.var_include_id_tramite.get():
            args.append("--omit-dig-id-tramite")
        if self.var_dry_run.get():
            args.append("--dry-run")
        return args

    def validate_excel(self) -> None:
        excel = self.var_excel.get().strip()
        if not excel:
            messagebox.showerror("Archivo requerido", "Selecciona un archivo Excel primero.")
            return

        def runner():
            rows = read_rows_from_excel(Path(excel))
            if self.var_filter_one.get():
                target = normalize_code(self.var_dig_id_tramite.get().strip())
                rows = [row for row in rows if normalize_code(row.dig_id_tramite) == target]
            rows, discarded = select_rows_with_highest_expediente(rows)
            destination_map = build_destination_expediente_map(rows)
            print(f"Filas detectadas: {len(rows)}")
            print(f"Filas descartadas por expediente menor: {len(discarded)}")
            if rows:
                tramites = sorted({normalize_code(row.dig_id_tramite) for row in rows if normalize_code(row.dig_id_tramite)})
                sample = tramites[0] if tramites else ""
                if sample:
                    print(f"Expediente de destino para {sample}: {destination_map.get(sample, '<sin valor>')}")
            if rows:
                first = rows[0]
                print(
                    "Primera fila: "
                    f"{first.dig_anio}/{first.dig_expediente}/"
                    f"{first.dig_id_tramite}/{first.dig_tramite}"
                )
            return 0

        self._start_job(
            runner,
            "Validacion completada.",
            "La validacion del Excel fallo. Revise la salida.",
            "Validar Excel",
            summary=[
                f"excel={excel}",
                f"dig_id_tramite={'<todos>' if not self.var_filter_one.get() else self.var_dig_id_tramite.get().strip()}",
            ],
        )

    def run_organize(self) -> None:
        try:
            args = self._build_args()
        except ValueError as exc:
            messagebox.showerror("Campos requeridos", str(exc))
            return

        def runner():
            return organiza_main(args)

        self._start_job(
            runner,
            "Proceso finalizado. Revise el manifest y el reporte.",
            "El proceso termino con errores. Revise la salida.",
            "Ejecutar OrganizaPlanillas",
            summary=[
                "Parametros:",
                f"source_base={self.var_source.get().strip()}",
                f"dest_base={self.var_dest.get().strip()}",
                f"excel={self.var_excel.get().strip()}",
                f"dig_id_tramite={'<todos>' if not self.var_filter_one.get() else self.var_dig_id_tramite.get().strip()}",
                f"include_id_tramite={self.var_include_id_tramite.get()}",
                f"dry_run={self.var_dry_run.get()}",
            ],
        )


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
