"""Fail a public-release check when likely medical data is present."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_SUFFIXES = {
    ".dcm", ".dicom", ".ima", ".img", ".nii", ".nrrd", ".mha", ".mhd"
}
SKIP_PARTS = {".git", ".venv", "venv", "__pycache__", "build", "dist", "logs"}


def tracked_files() -> list[Path]:
    try:
        output = subprocess.check_output(
            ["git", "ls-files", "-co", "--exclude-standard"],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
        )
    except (OSError, subprocess.CalledProcessError):
        return [
            path.relative_to(ROOT)
            for path in ROOT.rglob("*")
            if path.is_file() and not set(path.relative_to(ROOT).parts) & SKIP_PARTS
        ]
    return [Path(line) for line in output.splitlines() if line.strip()]


def looks_like_dicom(path: Path) -> bool:
    try:
        with path.open("rb") as stream:
            header = stream.read(132)
    except OSError:
        return False
    return len(header) >= 132 and header[128:132] == b"DICM"


def main() -> int:
    problems: list[str] = []
    checked = 0
    for relative in tracked_files():
        if set(relative.parts) & SKIP_PARTS:
            continue
        absolute = ROOT / relative
        if not absolute.is_file():
            continue
        checked += 1
        lower_name = relative.name.lower()
        suffix = relative.suffix.lower()
        if suffix in FORBIDDEN_SUFFIXES or lower_name == "dicomdir" or lower_name.endswith(".nii.gz"):
            problems.append(f"медицинский формат: {relative}")
            continue
        if looks_like_dicom(absolute):
            problems.append(f"DICOM-сигнатура в файле без расширения: {relative}")

    if problems:
        print("Проверка приватности НЕ пройдена:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        print("Не публикуйте эти файлы до профессионального обезличивания.", file=sys.stderr)
        return 1

    print(f"Проверка приватности пройдена: проверено файлов — {checked}; DICOM/медицинские данные не найдены.")
    print("Скрипт не заменяет ручную проверку скриншотов, логов и истории Git.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

