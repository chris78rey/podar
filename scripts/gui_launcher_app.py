#!/usr/bin/env python3
import os
import threading
import traceback
from pathlib import Path
from queue import Empty, Queue
from contextlib import redirect_stdout, redirect_stderr
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    from .oracle_defaults import (
        DEFAULT_ORACLE_JDBC_JAR,
        DEFAULT_ORACLE_OWNER,
        DEFAULT_ORACLE_SOURCE_TABLE,
        DEFAULT_ORACLE_TARGETS,
        DEFAULT_ORACLE_USER,
    )
    from .prune_local_mirror_from_oracle import main as prune_main
    from .test_oracle import main as test_oracle_main
    from .jvm_utils import resolve_app_path, resolve_user_config_path
except ImportError:  # pragma: no cover - direct script execution fallback
    from oracle_defaults import (
        DEFAULT_ORACLE_JDBC_JAR,
        DEFAULT_ORACLE_OWNER,
        DEFAULT_ORACLE_SOURCE_TABLE,
        DEFAULT_ORACLE_TARGETS,
        DEFAULT_ORACLE_USER,
    )
    from prune_local_mirror_from_oracle import main as prune_main
    from test_oracle import main as test_oracle_main
    from jvm_utils import resolve_app_path, resolve_user_config_path


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        return


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PODA Digitalizacion - Launcher")
        self.geometry("860x800")

        load_dotenv(resolve_app_path(".env"))
        env = os.environ

        self.var_source = tk.StringVar()
        self.var_dest = tk.StringVar()
        self.var_periodo = tk.StringVar(value="202602")
        self.var_planillado = tk.StringVar(value="S")
        self.var_generacion = tk.StringVar()
        self.var_output_folder = tk.StringVar()
        self.var_oracle_user = tk.StringVar(value=env.get("ORACLE_USER", DEFAULT_ORACLE_USER))
        self.var_oracle_password = tk.StringVar(value=env.get("ORACLE_PASSWORD", ""))
        self.var_oracle_targets = tk.StringVar(value=env.get("ORACLE_TARGETS", DEFAULT_ORACLE_TARGETS))
        self.var_oracle_jar = tk.StringVar(value=env.get("ORACLE_JDBC_JAR", DEFAULT_ORACLE_JDBC_JAR))
        self.var_oracle_owner = tk.StringVar(value=env.get("ORACLE_OWNER", DEFAULT_ORACLE_OWNER))
        self.var_oracle_source_table = tk.StringVar(value=env.get("ORACLE_SOURCE_TABLE", DEFAULT_ORACLE_SOURCE_TABLE))

        self._output_queue: Queue[tuple[str, object]] = Queue()
        self._task_running = False
        self._done_ok_text = ""
        self._done_fail_text = ""

        self.btn_test: ttk.Button | None = None
        self.btn_run: ttk.Button | None = None
        self.btn_save: ttk.Button | None = None

        self._build_form()
        self.after(100, self._drain_output_queue)

    def _build_form(self):
        pad = {"padx": 8, "pady": 6}
        frm = ttk.Frame(self)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="Source base").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.var_source, width=70).grid(row=0, column=1, **pad)
        ttk.Button(frm, text="Elegir", command=self.pick_source).grid(row=0, column=2, **pad)

        ttk.Label(frm, text="Dest base (parent)").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.var_dest, width=70).grid(row=1, column=1, **pad)
        ttk.Button(frm, text="Elegir", command=self.pick_dest).grid(row=1, column=2, **pad)

        ttk.Label(frm, text="FE_PLA_ANIOMES").grid(row=2, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.var_periodo, width=20).grid(row=2, column=1, sticky="w", **pad)

        ttk.Label(frm, text="DIG_PLANILLADO").grid(row=3, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.var_planillado, width=10).grid(row=3, column=1, sticky="w", **pad)

        ttk.Label(frm, text="ID de generacion (filtro DIG_ID_GENERACION, ej. 122369)").grid(row=4, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.var_generacion, width=20).grid(row=4, column=1, sticky="w", **pad)

        ttk.Label(frm, text="Numero de tramite ISSFA / carpeta de salida").grid(row=5, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.var_output_folder, width=20).grid(row=5, column=1, sticky="w", **pad)

        ttk.Label(frm, text="Oracle user").grid(row=6, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.var_oracle_user, width=30).grid(row=6, column=1, sticky="w", **pad)

        ttk.Label(frm, text="Oracle password").grid(row=7, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.var_oracle_password, width=30, show="*").grid(row=7, column=1, sticky="w", **pad)

        ttk.Label(frm, text="Oracle targets").grid(row=8, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.var_oracle_targets, width=70).grid(row=8, column=1, columnspan=2, sticky="we", **pad)

        ttk.Label(frm, text="Oracle JDBC jar").grid(row=9, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.var_oracle_jar, width=40).grid(row=9, column=1, sticky="w", **pad)

        ttk.Label(frm, text="Oracle owner").grid(row=10, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.var_oracle_owner, width=30).grid(row=10, column=1, sticky="w", **pad)

        ttk.Label(frm, text="Oracle source table").grid(row=11, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.var_oracle_source_table, width=30).grid(row=11, column=1, sticky="w", **pad)

        btns = ttk.Frame(frm)
        btns.grid(row=12, column=0, columnspan=3, sticky="w", **pad)
        self.btn_test = ttk.Button(btns, text="Probar Oracle", command=self.test_oracle)
        self.btn_test.pack(side=tk.LEFT, padx=4)
        self.btn_save = ttk.Button(btns, text="Guardar config", command=self.save_oracle_config)
        self.btn_save.pack(side=tk.LEFT, padx=4)
        self.btn_run = ttk.Button(btns, text="Ejecutar", command=self.run_prune)
        self.btn_run.pack(side=tk.LEFT, padx=4)

        ttk.Label(frm, text="Salida").grid(row=13, column=0, sticky="nw", **pad)
        self.txt = tk.Text(frm, height=18)
        self.txt.grid(row=13, column=1, columnspan=2, sticky="nsew", **pad)

        frm.rowconfigure(13, weight=1)
        frm.columnconfigure(1, weight=1)

    def pick_source(self):
        path = filedialog.askdirectory(title="Select source base")
        if path:
            self.var_source.set(path)

    def pick_dest(self):
        path = filedialog.askdirectory(title="Select dest base")
        if path:
            self.var_dest.set(path)

    def append_out(self, text: str):
        self.txt.insert(tk.END, text + "\n")
        self.txt.see(tk.END)

    def _queue_text(self, text: str):
        for line in text.splitlines():
            if line.strip():
                self._output_queue.put(("line", line.rstrip()))

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

    def _set_task_state(self, running: bool):
        self._task_running = running
        state = tk.DISABLED if running else tk.NORMAL
        if self.btn_test is not None:
            self.btn_test.configure(state=state)
        if self.btn_run is not None:
            self.btn_run.configure(state=state)
        self.configure(cursor="watch" if running else "")
        self.update_idletasks()

    def _start_job(self, runner, ok_text: str, fail_text: str, title: str, summary: list[str] | None = None):
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

    def _drain_output_queue(self):
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

    def test_oracle(self):
        os.environ["ORACLE_USER"] = self.var_oracle_user.get().strip() or DEFAULT_ORACLE_USER
        os.environ["ORACLE_PASSWORD"] = self.var_oracle_password.get()
        os.environ["ORACLE_TARGETS"] = self.var_oracle_targets.get().strip() or DEFAULT_ORACLE_TARGETS
        os.environ["ORACLE_JDBC_JAR"] = self.var_oracle_jar.get().strip() or DEFAULT_ORACLE_JDBC_JAR
        os.environ["ORACLE_OWNER"] = self.var_oracle_owner.get().strip() or DEFAULT_ORACLE_OWNER
        os.environ["ORACLE_SOURCE_TABLE"] = self.var_oracle_source_table.get().strip() or DEFAULT_ORACLE_SOURCE_TABLE
        self._start_job(
            test_oracle_main,
            "Conectividad verificada o diagnostico mostrado.",
            "Fallo en la prueba de conectividad. Revise la salida.",
            "Probar Oracle",
        )

    def save_oracle_config(self):
        config_path = resolve_user_config_path(".env")
        config_path.parent.mkdir(parents=True, exist_ok=True)
        content = (
            "# Oracle credentials and connection\n"
            f"ORACLE_USER={self.var_oracle_user.get().strip() or DEFAULT_ORACLE_USER}\n"
            f"ORACLE_PASSWORD={self.var_oracle_password.get()}\n"
            f"ORACLE_TARGETS={self.var_oracle_targets.get().strip() or DEFAULT_ORACLE_TARGETS}\n"
            f"ORACLE_JDBC_JAR={self.var_oracle_jar.get().strip() or DEFAULT_ORACLE_JDBC_JAR}\n\n"
            "# Optional schema/table overrides\n"
            f"ORACLE_OWNER={self.var_oracle_owner.get().strip() or DEFAULT_ORACLE_OWNER}\n"
            f"ORACLE_SOURCE_TABLE={self.var_oracle_source_table.get().strip() or DEFAULT_ORACLE_SOURCE_TABLE}\n"
        )
        config_path.write_text(content, encoding="utf-8")
        self.append_out(f"Configuracion guardada en: {config_path}")
        messagebox.showinfo("Configuracion guardada", f"Se guardo la configuracion en:\n{config_path}")

    def run_prune(self):
        src = self.var_source.get().strip()
        dst = self.var_dest.get().strip()
        periodo = self.var_periodo.get().strip()
        plan = self.var_planillado.get().strip() or "S"
        generacion = self.var_generacion.get().strip()
        output_folder_name = self.var_output_folder.get().strip() or generacion
        oracle_user = self.var_oracle_user.get().strip() or DEFAULT_ORACLE_USER
        oracle_password = self.var_oracle_password.get()
        oracle_targets = self.var_oracle_targets.get().strip() or DEFAULT_ORACLE_TARGETS
        oracle_jar = self.var_oracle_jar.get().strip() or DEFAULT_ORACLE_JDBC_JAR
        oracle_owner = self.var_oracle_owner.get().strip() or DEFAULT_ORACLE_OWNER
        oracle_source_table = self.var_oracle_source_table.get().strip() or DEFAULT_ORACLE_SOURCE_TABLE

        if not src or not dst or not periodo or not generacion:
            messagebox.showerror("Campos requeridos", "Source, Dest, FE_PLA_ANIOMES e ID de generacion son obligatorios")
            return

        args = [
            "--source-base",
            src,
            "--dest-base",
            dst,
            "--fe-pla-aniomes",
            periodo,
            "--dig-planillado",
            plan,
            "--dig-id-generacion",
            generacion,
            "--numero-tramite-issfa",
            output_folder_name,
            "--user",
            oracle_user,
            "--password",
            oracle_password,
            "--targets",
            oracle_targets,
            "--jar",
            oracle_jar,
            "--owner",
            oracle_owner,
            "--source-table",
            oracle_source_table,
        ]

        def runner():
            return prune_main(args)

        self._start_job(
            runner,
            "Proceso finalizado. Revise el manifest y la salida.",
            "El proceso termino con errores. Revise la salida.",
            "Ejecutar poda",
            summary=[
                "Parametros:",
                f"source_base={src}",
                f"dest_base={dst}",
                f"fe_pla_aniomes={periodo}",
                f"dig_planillado={plan}",
                f"dig_id_generacion={generacion}",
                f"numero_tramite_issfa={output_folder_name}",
                f"oracle_user={oracle_user}",
                f"oracle_targets={oracle_targets}",
                f"oracle_jar={oracle_jar}",
                f"oracle_owner={oracle_owner}",
                f"oracle_source_table={oracle_source_table}",
            ],
        )


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
