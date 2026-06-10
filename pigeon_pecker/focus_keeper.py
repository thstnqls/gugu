"""macOS에서 비둘기 클릭 시 직전 활성 앱으로 포커스를 돌려주는 헬퍼."""
from __future__ import annotations

from typing import Optional

try:
    from AppKit import NSWorkspace, NSRunningApplication, NSApplicationActivateIgnoringOtherApps
    APPKIT_AVAILABLE = True
except Exception:
    APPKIT_AVAILABLE = False


_last_active_pid: Optional[int] = None
_our_pid: Optional[int] = None


def _get_our_pid() -> int:
    global _our_pid
    if _our_pid is None:
        import os
        _our_pid = os.getpid()
    return _our_pid


def remember_active_app() -> None:
    """현재 활성 앱이 우리가 아니면 그 PID를 기억."""
    global _last_active_pid
    if not APPKIT_AVAILABLE:
        return
    try:
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        if app is None:
            return
        pid = int(app.processIdentifier())
        if pid != _get_our_pid():
            _last_active_pid = pid
    except Exception:
        pass


def restore_previous_app() -> None:
    """기억해둔 직전 활성 앱으로 포커스 복귀."""
    if not APPKIT_AVAILABLE or _last_active_pid is None:
        return
    try:
        target = NSRunningApplication.runningApplicationWithProcessIdentifier_(_last_active_pid)
        if target is not None:
            target.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
    except Exception:
        pass
