"""Windows 전용: Qt 오버레이 창에 click-through / 최상위·비활성 스타일 적용.

macos_window.py 의 대응물. ctypes 로 user32 의 확장 윈도우 스타일(WS_EX_*)을 토글한다.
 - click-through : WS_EX_TRANSPARENT (마우스 이벤트가 아래 창으로 통과)
 - 항상 위 / 포커스 안 뺏김 : WS_EX_TOPMOST + WS_EX_NOACTIVATE + WS_EX_TOOLWINDOW
macOS 와 달리 occlusion(가려짐) 최적화 문제가 없으므로 별도 우회는 필요 없다.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes

try:
    _user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    WIN_AVAILABLE = True
except Exception:
    _user32 = None
    WIN_AVAILABLE = False


GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040

_LONG_PTR = ctypes.c_ssize_t

if WIN_AVAILABLE:
    # 64비트에서 포인터 폭을 보존하려면 ...PtrW 변형을 써야 함.
    _GetWindowLong = getattr(_user32, "GetWindowLongPtrW", None) or _user32.GetWindowLongW
    _SetWindowLong = getattr(_user32, "SetWindowLongPtrW", None) or _user32.SetWindowLongW
    _GetWindowLong.restype = _LONG_PTR
    _GetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int]
    _SetWindowLong.restype = _LONG_PTR
    _SetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int, _LONG_PTR]

    _SetWindowPos = _user32.SetWindowPos
    _SetWindowPos.restype = wintypes.BOOL
    _SetWindowPos.argtypes = [
        wintypes.HWND, wintypes.HWND,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.UINT,
    ]
    _HWND_TOPMOST = wintypes.HWND(-1)


def _hwnd(qwidget):
    """Qt 위젯의 네이티브 HWND 핸들. Windows 에서 winId() 는 HWND 이다."""
    if not WIN_AVAILABLE:
        return None
    try:
        win = qwidget.windowHandle()
        if win is None:
            return None
        return wintypes.HWND(int(win.winId()))
    except Exception:
        return None


def set_ignores_mouse_events(qwidget, ignore: bool) -> bool:
    """마우스 이벤트 통과(click-through) 설정. ignore=True 면 아래 창으로 클릭이 통과한다."""
    h = _hwnd(qwidget)
    if h is None:
        return False
    try:
        ex = _GetWindowLong(h, GWL_EXSTYLE)
        ex |= WS_EX_LAYERED  # 투명 합성 + 통과 동작에 필요
        if ignore:
            ex |= WS_EX_TRANSPARENT
        else:
            ex &= ~WS_EX_TRANSPARENT
        _SetWindowLong(h, GWL_EXSTYLE, ex)
        return True
    except Exception:
        return False


def raise_to_overlay_level(qwidget) -> bool:
    """항상 위 + 클릭해도 포커스를 뺏지 않는 도구창으로 만든다."""
    h = _hwnd(qwidget)
    if h is None:
        return False
    try:
        ex = _GetWindowLong(h, GWL_EXSTYLE)
        ex |= WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
        _SetWindowLong(h, GWL_EXSTYLE, ex)
        _SetWindowPos(
            h, _HWND_TOPMOST, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
        )
        return True
    except Exception:
        return False


def apply_occlusion_workaround(qwidget) -> bool:
    """Windows 엔 macOS 식 occlusion 문제가 없어 할 일 없음."""
    return True


def order_front_without_activating(qwidget) -> bool:
    """활성화 없이 앞으로 — 최상위 재설정으로 충분."""
    return raise_to_overlay_level(qwidget)
