from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QRect
from PySide6.QtGui import QPixmap

ASSETS_DIR = Path(__file__).parent / "assets"

# (파일명, 프레임 가로 크기) — 모든 시트가 32x32 프레임
# 쪼기 모션은 eat 시트를 사용 (peck 시트보다 깔끔)
SHEETS = {
    "walk": ("pigeon_walking-Sheet.png", 32),
    "peck": ("pigeon_eat-Sheet.png", 32),
    "fly":  ("pigeon_fiy-Sheet.png", 32),
}


def _slice_sheet(path: Path, frame_w: int) -> list[QPixmap]:
    sheet = QPixmap(str(path))
    if sheet.isNull():
        return []
    h = sheet.height()
    n = sheet.width() // frame_w
    frames: list[QPixmap] = []
    for i in range(n):
        frames.append(sheet.copy(QRect(i * frame_w, 0, frame_w, h)))
    return frames


def load_sprites() -> Optional[dict[str, list[QPixmap]]]:
    """assets 폴더에서 스프라이트 시트를 로드해 {state: [frames...]} 형태로 반환.
    파일 없거나 못 읽으면 None.
    """
    sprites: dict[str, list[QPixmap]] = {}
    for key, (fname, fw) in SHEETS.items():
        p = ASSETS_DIR / fname
        if not p.exists():
            continue
        frames = _slice_sheet(p, fw)
        if frames:
            sprites[key] = frames
            print(f"[pigeon] loaded {key}: {len(frames)} frames from {fname}", flush=True)
    return sprites or None
