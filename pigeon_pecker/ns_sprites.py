"""NSImage 기반 스프라이트 로더 — 네이티브 NSView 그리기용.

Qt sprites.py와 별개로, pyobjc로 PNG를 NSImage로 로드하고
프레임 단위로 잘라 NSImage 리스트로 반환.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

try:
    from AppKit import (
        NSImage,
        NSBitmapImageRep,
        NSGraphicsContext,
        NSImageInterpolationNone,
    )
    from Foundation import NSURL, NSMakeRect, NSMakeSize
    APPKIT_AVAILABLE = True
except Exception:
    APPKIT_AVAILABLE = False


ASSETS_DIR = Path(__file__).parent / "assets"

# (key, filename, frame_w) — Qt sprites.py와 동일한 매핑
SHEETS = {
    "walk": ("pigeon_walking-Sheet.png", 32),
    "peck": ("pigeon_eat-Sheet.png", 32),  # eat 시트를 쪼기로 사용
    "fly":  ("pigeon_fiy-Sheet.png", 32),
}


def _load_sheet(path: Path) -> Optional[NSImage]:
    if not APPKIT_AVAILABLE:
        return None
    url = NSURL.fileURLWithPath_(str(path))
    img = NSImage.alloc().initWithContentsOfURL_(url)
    return img if (img is not None and img.isValid()) else None


def _slice_frames(sheet: NSImage, frame_w: int) -> list[NSImage]:
    """시트를 가로 frame_w 단위로 잘라 NSImage 리스트로."""
    size = sheet.size()
    sheet_w = int(size.width)
    sheet_h = int(size.height)
    n = sheet_w // frame_w
    frames: list[NSImage] = []
    for i in range(n):
        frame = NSImage.alloc().initWithSize_(NSMakeSize(frame_w, sheet_h))
        frame.lockFocus()
        try:
            ctx = NSGraphicsContext.currentContext()
            if ctx is not None:
                ctx.setImageInterpolation_(NSImageInterpolationNone)
            # 소스 영역: 시트의 (i*frame_w, 0, frame_w, sheet_h)
            src_rect = NSMakeRect(i * frame_w, 0, frame_w, sheet_h)
            dst_rect = NSMakeRect(0, 0, frame_w, sheet_h)
            sheet.drawInRect_fromRect_operation_fraction_(
                dst_rect, src_rect, 2, 1.0  # NSCompositingOperationSourceOver = 2
            )
        finally:
            frame.unlockFocus()
        frames.append(frame)
    return frames


def load_ns_sprites() -> Optional[dict[str, list[NSImage]]]:
    if not APPKIT_AVAILABLE:
        return None
    sprites: dict[str, list[NSImage]] = {}
    for key, (fname, fw) in SHEETS.items():
        path = ASSETS_DIR / fname
        if not path.exists():
            continue
        sheet = _load_sheet(path)
        if sheet is None:
            continue
        frames = _slice_frames(sheet, fw)
        if frames:
            sprites[key] = frames
            print(f"[pigeon] NS loaded {key}: {len(frames)} frames from {fname}", flush=True)
    return sprites or None
