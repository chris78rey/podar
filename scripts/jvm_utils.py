from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import jpype


def _candidate_jvm_paths(base: Path) -> list[Path]:
    return [
        base / "bin" / "server" / "jvm.dll",
        base / "jre" / "bin" / "server" / "jvm.dll",
        base / "lib" / "server" / "jvm.dll",
    ]


def _parse_java_home_from_command() -> Path | None:
    java = shutil.which("java")
    if not java:
        return None
    try:
        out = subprocess.check_output(
            [java, "-XshowSettings:properties", "-version"],
            stderr=subprocess.STDOUT,
            text=True,
        )
    except Exception:
        return None

    for line in out.splitlines():
        if "java.home =" not in line:
            continue
        home = line.split("=", 1)[1].strip()
        if home:
            return Path(home)
    return None


def resolve_jvm_path() -> str:
    override = os.environ.get("ORACLE_JVM_PATH") or os.environ.get("JPYPE_JVM")
    if override:
        override_path = Path(override).expanduser()
        if override_path.is_file():
            return str(override_path)
        for candidate in _candidate_jvm_paths(override_path):
            if candidate.is_file():
                return str(candidate)

    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        base = Path(java_home).expanduser()
        for candidate in _candidate_jvm_paths(base):
            if candidate.is_file():
                return str(candidate)

    detected_home = _parse_java_home_from_command()
    if detected_home is not None:
        for candidate in _candidate_jvm_paths(detected_home):
            if candidate.is_file():
                return str(candidate)

    return jpype.getDefaultJVMPath()


def start_jvm(classpath: list[str] | str | None = None) -> str:
    jvm_path = resolve_jvm_path()
    if not jpype.isJVMStarted():
        jpype.startJVM(jvm_path, classpath=classpath)
    return jvm_path


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def resolve_app_path(raw_path: str | Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path

    base = app_root()
    appdata = os.environ.get("APPDATA")
    if appdata:
        appdata_candidate = Path(appdata) / "PODA" / path
        if appdata_candidate.exists():
            return appdata_candidate

    localappdata = os.environ.get("LOCALAPPDATA")
    if localappdata:
        local_candidate = Path(localappdata) / "PODA" / path
        if local_candidate.exists():
            return local_candidate

    candidates = [
        base / path,
        base / "_internal" / path,
    ]

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / path)

    if not getattr(sys, "frozen", False):
        candidates.append(Path(__file__).resolve().parents[1] / path)

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[0]


def resolve_user_config_path(raw_path: str | Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path

    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "PODA" / path

    return app_root() / path
