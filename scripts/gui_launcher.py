#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


ROOT = Path(__file__).resolve().parents[1]


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
        self.title("PODA Digitalización – Launcher")
        self.geometry("720x560")

        load_dotenv(ROOT / ".env")

        self.var_source = tk.StringVar()
        self.var_dest = tk.StringVar()
        self.var_periodo = tk.StringVar(value="202602")
        self.var_planillado = tk.StringVar(value="S")
        self.var_expediente = tk.StringVar()
        self.var_generacion = tk.StringVar()
        self.var_limit = tk.StringVar(value="25")
        self.var_dry = tk.BooleanVar(value=True)

        self._build_form()

    def _build_form(self):
        pad = {"padx": 8, "pady": 6}
        frm = ttk.Frame(self)
        frm.pack(fill=tk.BOTH, expand=True)

        # Source base
        ttk.Label(frm, text="Source base").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.var_source, width=70).grid(row=0, column=1, **pad)
        ttk.Button(frm, text="Elegir", command=self.pick_source).grid(row=0, column=2, **pad)

        # Dest base
        ttk.Label(frm, text="Dest base").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.var_dest, width=70).grid(row=1, column=1, **pad)
        ttk.Button(frm, text="Elegir", command=self.pick_dest).grid(row=1, column=2, **pad)

        # Periodo / Planillado
        ttk.Label(frm, text="FE_PLA_ANIOMES").grid(row=2, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.var_periodo, width=20).grid(row=2, column=1, sticky="w", **pad)

        ttk.Label(frm, text="DIG_PLANILLADO").grid(row=3, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.var_planillado, width=10).grid(row=3, column=1, sticky="w", **pad)

        # Optional filters
        ttk.Label(frm, text="Expediente (opcional)").grid(row=4, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.var_expediente, width=20).grid(row=4, column=1, sticky="w", **pad)

        ttk.Label(frm, text="DIG_ID_GENERACION (opcional)").grid(row=5, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.var_generacion, width=20).grid(row=5, column=1, sticky="w", **pad)

        ttk.Label(frm, text="Limit (opcional)").grid(row=6, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.var_limit, width=10).grid(row=6, column=1, sticky="w", **pad)

        ttk.Checkbutton(frm, text="Dry-run (no copia)", variable=self.var_dry).grid(row=7, column=1, sticky="w", **pad)

        # Actions
        btns = ttk.Frame(frm)
        btns.grid(row=8, column=0, columnspan=3, sticky="w", **pad)
        ttk.Button(btns, text="Probar Oracle", command=self.test_oracle).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Ejecutar", command=self.run_prune).pack(side=tk.LEFT, padx=4)

        # Output
        ttk.Label(frm, text="Salida").grid(row=9, column=0, sticky="nw", **pad)
        self.txt = tk.Text(frm, height=18)
        self.txt.grid(row=9, column=1, columnspan=2, sticky="nsew", **pad)

        frm.rowconfigure(9, weight=1)
        frm.columnconfigure(1, weight=1)

    def pick_source(self):
        path = filedialog.askdirectory(title="Seleccionar source base")
        if path:
            self.var_source.set(path)

    def pick_dest(self):
        path = filedialog.askdirectory(title="Seleccionar dest base")
        if path:
            self.var_dest.set(path)

    def append_out(self, text: str):
        self.txt.insert(tk.END, text + "\n")
        self.txt.see(tk.END)

    def _run_cmd(self, args):
        try:
            proc = subprocess.Popen(
                args,
                cwd=str(ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=os.environ.copy(),
            )
            for line in proc.stdout:  # type: ignore[attr-defined]
                self.append_out(line.rstrip())
            code = proc.wait()
            return code
        except FileNotFoundError as e:
            self.append_out(f"ERROR: {e}")
            return 1

    def test_oracle(self):
        self.append_out("== Probar Oracle ==")
        code = self._run_cmd([sys.executable, "scripts/test_oracle.py"])
        if code == 0:
            messagebox.showinfo("Oracle", "Conectividad verificada o diagnóstico mostrado.")
        else:
            messagebox.showwarning("Oracle", "Fallo en la prueba de conectividad. Revise la salida.")

    def run_prune(self):
        src = self.var_source.get().strip()
        dst = self.var_dest.get().strip()
        periodo = self.var_periodo.get().strip()
        plan = self.var_planillado.get().strip() or "S"
        expediente = self.var_expediente.get().strip()
        generacion = self.var_generacion.get().strip()
        limit = self.var_limit.get().strip()
        dry = self.var_dry.get()

        if not src or not dst or not periodo:
            messagebox.showerror("Campos requeridos", "Source, Dest y FE_PLA_ANIOMES son obligatorios")
            return

        args = [
            sys.executable,
            "scripts/prune_local_mirror_from_oracle.py",
            "--source-base",
            src,
            "--dest-base",
            dst,
            "--fe-pla-aniomes",
            periodo,
            "--dig-planillado",
            plan,
        ]

        if expediente:
            args += ["--expediente", expediente]
        if generacion:
            args += ["--dig-id-generacion", generacion]
        if limit:
            args += ["--limit", limit]
        if dry:
            args += ["--dry-run"]

        self.append_out("== Ejecutar poda ==")
        self.append_out("Comando: " + " ".join(args))
        code = self._run_cmd(args)
        if code == 0:
            messagebox.showinfo("Poda", "Proceso finalizado. Revise el manifest y la salida.")
        else:
            messagebox.showwarning("Poda", "El proceso terminó con errores. Revise la salida.")


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()

