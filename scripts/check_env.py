#!/usr/bin/env python3
import os
import shutil
import subprocess
import sys
from pathlib import Path


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def check_python():
    ok = sys.version_info >= (3, 11)
    return ok, f"Python {sys.version.split()[0]} (>=3.11 required)"


def check_java():
    java = shutil.which("java")
    if not java:
        return False, "java not found in PATH"
    try:
        out = subprocess.check_output([java, "-version"], stderr=subprocess.STDOUT, text=True)
        line = out.splitlines()[0] if out else "java -version ran"
        return True, line
    except Exception as e:
        return False, f"java -version error: {e}"


def check_packages():
    missing = []
    try:
        import jaydebeapi  # noqa: F401
    except Exception:
        missing.append("jaydebeapi")
    try:
        import jpype  # noqa: F401
    except Exception:
        missing.append("JPype1")
    if missing:
        return False, "missing packages: " + ", ".join(missing)
    return True, "python packages OK"


def check_env_vars():
    required = ["ORACLE_USER", "ORACLE_PASSWORD", "ORACLE_TARGETS", "ORACLE_JDBC_JAR"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        return False, "missing env vars: " + ", ".join(missing)
    jar = Path(os.environ["ORACLE_JDBC_JAR"]).expanduser()
    return (jar.exists(), f"JDBC jar: {jar}")


def main(argv=None):
    load_dotenv(Path(".env"))
    checks = [
        ("Python",) + check_python(),
        ("Java",) + check_java(),
        ("Packages",) + check_packages(),
        ("Env/JAR",) + check_env_vars(),
    ]
    exit_code = 0
    print("Environment checks:")
    for name, ok, info in checks:
        status = "OK" if ok else "FAIL"
        print(f"- {name:8s}: {status} - {info}")
        if not ok:
            exit_code = 1
    if exit_code != 0:
        print("\nHints:")
        print("- Create venv and install: pip install -r requirements.txt")
        print("- Ensure Java (JRE/JDK) is installed and in PATH")
        print("- Copy jdbc/ojdbc8.jar and set ORACLE_JDBC_JAR in .env")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

