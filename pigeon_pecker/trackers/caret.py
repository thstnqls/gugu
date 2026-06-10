from __future__ import annotations

import threading
import time
from typing import Optional

from PySide6.QtCore import QObject, QPointF, QThread, Signal

try:
    from ApplicationServices import (
        AXIsProcessTrustedWithOptions,
        AXUIElementCopyAttributeValue,
        AXUIElementCreateSystemWide,
        AXValueGetValue,
        kAXFocusedUIElementAttribute,
        kAXSelectedTextRangeAttribute,
        kAXBoundsForRangeParameterizedAttribute,
        kAXValueCGRectType,
    )
    AX_AVAILABLE = True
except Exception:
    AX_AVAILABLE = False

try:
    from ApplicationServices import AXUIElementCopyParameterizedAttributeValue
except Exception:
    AXUIElementCopyParameterizedAttributeValue = None


_system_wide = None
_sw_lock = threading.Lock()


def _get_system_wide():
    global _system_wide
    with _sw_lock:
        if _system_wide is None and AX_AVAILABLE:
            _system_wide = AXUIElementCreateSystemWide()
        return _system_wide


def request_accessibility_permission(prompt: bool = True) -> bool:
    if not AX_AVAILABLE:
        return False
    try:
        from ApplicationServices import kAXTrustedCheckOptionPrompt
        options = {kAXTrustedCheckOptionPrompt: prompt}
        return bool(AXIsProcessTrustedWithOptions(options))
    except Exception:
        return False


def _query_caret_once() -> Optional[QPointF]:
    """단일 동기 호출 — 절대 메인 스레드에서 부르지 말 것."""
    if not AX_AVAILABLE or AXUIElementCopyParameterizedAttributeValue is None:
        return None
    sw = _get_system_wide()
    if sw is None:
        return None
    try:
        err, focused = AXUIElementCopyAttributeValue(sw, kAXFocusedUIElementAttribute, None)
        if err != 0 or focused is None:
            return None
        err, sel_range = AXUIElementCopyAttributeValue(focused, kAXSelectedTextRangeAttribute, None)
        if err != 0 or sel_range is None:
            return None
        err, bounds_value = AXUIElementCopyParameterizedAttributeValue(
            focused, kAXBoundsForRangeParameterizedAttribute, sel_range, None
        )
        if err != 0 or bounds_value is None:
            return None
        ok, rect = AXValueGetValue(bounds_value, kAXValueCGRectType, None)
        if not ok:
            return None
        x = float(rect.origin.x)
        y = float(rect.origin.y)
        h = float(rect.size.height)
        return QPointF(x, y + h)
    except Exception:
        return None


class CaretWorker(QThread):
    """백그라운드에서 캐럿 좌표를 폴링하고 캐시. 메인 스레드는 cached_pos()만 읽음."""

    caret_changed = Signal(object)  # QPointF | None

    def __init__(self, interval_ms: int = 200, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.interval_ms = interval_ms
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._cached: Optional[QPointF] = None

    def cached_pos(self) -> Optional[QPointF]:
        with self._lock:
            return self._cached

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:  # noqa: D401
        while not self._stop.is_set():
            pos = _query_caret_once()
            if pos is not None:
                with self._lock:
                    self._cached = pos
                self.caret_changed.emit(pos)
            # interval_ms 동안 대기 (stop 신호 오면 즉시 탈출)
            self._stop.wait(self.interval_ms / 1000.0)
