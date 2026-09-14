#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCH = ROOT / "docs" / "architecture"
OUT = ROOT / "docs" / "screenshots"
DIAG = OUT / "diagrams"
UI = OUT / "ui"


def write_placeholder(path: Path, title: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="720">'
        f'<rect width="1200" height="720" fill="#0b1220"/>'
        f'<text x="60" y="360" fill="#3dd6c6" font-size="36" font-family="sans-serif">{title}</text>'
        f"</svg>",
        encoding="utf-8",
    )


def main() -> None:
    DIAG.mkdir(parents=True, exist_ok=True)
    UI.mkdir(parents=True, exist_ok=True)
    for mmd in ARCH.glob("*.mmd"):
        target = DIAG / f"{mmd.stem}.png"
        # Keep mermaid source next to rendered placeholder for Architecture Explorer.
        shutil.copyfile(mmd, DIAG / f"{mmd.stem}.mmd")
        write_placeholder(target.with_suffix(".svg"), mmd.stem)
        write_placeholder(target, mmd.stem)
    for name in [
        "workbench-desktop.png",
        "workbench-mobile.png",
        "observability-lab.png",
        "quality-lab.png",
        "architecture-langchain.png",
        "whatif.png",
        "login.png",
    ]:
        write_placeholder(UI / name, name)


if __name__ == "__main__":
    main()
