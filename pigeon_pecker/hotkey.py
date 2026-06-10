"""글로벌 키보드 단축키로 앱 강제 종료.

 - macOS  : CGEventTap 으로 ⌃⌥⌘Q (Control+Option+Command+Q). '입력 모니터링' 권한 필요할 수 있음.
 - Windows : RegisterHotKey 로 Ctrl+Alt+Q. 별도 권한 불필요.
 - 그 외   : 무동작 (트레이 메뉴 '종료'로 대체).

공개 인터페이스는 동일: HotkeyListener(callback).start() / .stop()
권한/지원이 없어도 트레이 메뉴 + 프로세스 종료로 대체 가능하다.

종료 단축키 표기는 hotkey_label() 로 가져온다 (UI 문구용).
"""
from __future__ import annotations

import threading
from typing import Callable, Optional

from .platform_support import IS_MAC, IS_WINDOWS


# ────────────────────────────────────────────────────────────────────
# macOS — CGEventTap
# ────────────────────────────────────────────────────────────────────
try:
    if IS_MAC:
        from Quartz import (
            CFRunLoopGetCurrent,
            CFRunLoopRun,
            CFRunLoopStop,
            CFRunLoopAddSource,
            CFMachPortCreateRunLoopSource,
            CGEventTapCreate,
            CGEventTapEnable,
            CGEventGetFlags,
            CGEventGetIntegerValueField,
            kCFAllocatorDefault,
            kCFRunLoopCommonModes,
            kCGEventKeyDown,
            kCGHeadInsertEventTap,
            kCGSessionEventTap,
            kCGEventTapOptionListenOnly,
            kCGKeyboardEventKeycode,
            kCGEventFlagMaskCommand,
            kCGEventFlagMaskControl,
            kCGEventFlagMaskAlternate,
        )
        QUARTZ_AVAILABLE = True
    else:
        QUARTZ_AVAILABLE = False
except Exception:
    QUARTZ_AVAILABLE = False


# US QWERTY 'q' = 12
KEY_Q = 12
REQUIRED_FLAGS = 0
if QUARTZ_AVAILABLE:
    REQUIRED_FLAGS = (
        kCGEventFlagMaskCommand
        | kCGEventFlagMaskControl
        | kCGEventFlagMaskAlternate
    )


class _MacHotkeyListener:
    """별도 스레드에서 글로벌 키 이벤트를 들음. ⌃⌥⌘Q 누르면 callback 호출."""

    def __init__(self, callback: Callable[[], None]) -> None:
        self.callback = callback
        self._thread: Optional[threading.Thread] = None
        self._runloop = None
        self._tap = None
        self._started_ok = False

    def start(self) -> bool:
        if not QUARTZ_AVAILABLE:
            print("[pigeon] hotkey: Quartz not available", flush=True)
            return False
        self._thread = threading.Thread(target=self._run, daemon=True, name="hotkey")
        self._thread.start()
        self._thread.join(timeout=0.5)
        return self._started_ok or self._thread.is_alive()

    def stop(self) -> None:
        if self._runloop is not None:
            try:
                CFRunLoopStop(self._runloop)
            except Exception:
                pass

    def _callback(self, proxy, event_type, event, refcon):
        try:
            if event_type == kCGEventKeyDown:
                keycode = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
                flags = CGEventGetFlags(event)
                masked = int(flags) & REQUIRED_FLAGS
                if keycode == KEY_Q and masked == REQUIRED_FLAGS:
                    print("[pigeon] hotkey fired: emergency quit", flush=True)
                    try:
                        self.callback()
                    except Exception as e:
                        print(f"[pigeon] hotkey callback error: {e}", flush=True)
        except Exception as e:
            print(f"[pigeon] hotkey handler error: {e}", flush=True)
        return event

    def _run(self) -> None:
        try:
            mask = (1 << kCGEventKeyDown)
            self._tap = CGEventTapCreate(
                kCGSessionEventTap,
                kCGHeadInsertEventTap,
                kCGEventTapOptionListenOnly,
                mask,
                self._callback,
                None,
            )
            if self._tap is None:
                print("[pigeon] hotkey: CGEventTapCreate returned None — '입력 모니터링' 권한이 필요합니다.", flush=True)
                return
            source = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, self._tap, 0)
            self._runloop = CFRunLoopGetCurrent()
            CFRunLoopAddSource(self._runloop, source, kCFRunLoopCommonModes)
            CGEventTapEnable(self._tap, True)
            self._started_ok = True
            print("[pigeon] hotkey listener started (⌃⌥⌘Q to quit)", flush=True)
            CFRunLoopRun()
        except Exception as e:
            print(f"[pigeon] hotkey thread error: {e}", flush=True)


# ────────────────────────────────────────────────────────────────────
# Windows — RegisterHotKey (Ctrl+Alt+Q)
# ────────────────────────────────────────────────────────────────────
class _WindowsHotkeyListener:
    """별도 스레드에서 메시지 루프를 돌며 Ctrl+Alt+Q 핫키를 받는다."""

    _HOTKEY_ID = 1
    _MOD_ALT = 0x0001
    _MOD_CONTROL = 0x0002
    _MOD_NOREPEAT = 0x4000
    _VK_Q = 0x51
    _WM_HOTKEY = 0x0312
    _WM_QUIT = 0x0012

    def __init__(self, callback: Callable[[], None]) -> None:
        self.callback = callback
        self._thread: Optional[threading.Thread] = None
        self._thread_id: Optional[int] = None
        self._started_ok = False
        self._ready = threading.Event()

    def start(self) -> bool:
        self._thread = threading.Thread(target=self._run, daemon=True, name="hotkey")
        self._thread.start()
        self._ready.wait(timeout=0.5)
        return self._started_ok

    def stop(self) -> None:
        if self._thread_id is not None:
            try:
                import ctypes
                ctypes.windll.user32.PostThreadMessageW(  # type: ignore[attr-defined]
                    self._thread_id, self._WM_QUIT, 0, 0
                )
            except Exception:
                pass

    def _run(self) -> None:
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32  # type: ignore[attr-defined]
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

            self._thread_id = kernel32.GetCurrentThreadId()

            ok = user32.RegisterHotKey(
                None,
                self._HOTKEY_ID,
                self._MOD_CONTROL | self._MOD_ALT | self._MOD_NOREPEAT,
                self._VK_Q,
            )
            if not ok:
                print("[pigeon] hotkey: RegisterHotKey 실패 (이미 사용 중인 조합일 수 있음)", flush=True)
                self._ready.set()
                return

            self._started_ok = True
            self._ready.set()
            print("[pigeon] hotkey listener started (Ctrl+Alt+Q to quit)", flush=True)

            msg = wintypes.MSG()
            # GetMessageW: 새 메시지를 받을 때까지 블록. WM_QUIT 받으면 0 반환 → 종료.
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                if msg.message == self._WM_HOTKEY and msg.wParam == self._HOTKEY_ID:
                    print("[pigeon] hotkey fired: emergency quit", flush=True)
                    try:
                        self.callback()
                    except Exception as e:
                        print(f"[pigeon] hotkey callback error: {e}", flush=True)

            user32.UnregisterHotKey(None, self._HOTKEY_ID)
        except Exception as e:
            print(f"[pigeon] hotkey thread error: {e}", flush=True)
            self._ready.set()


# ────────────────────────────────────────────────────────────────────
# 미지원 플랫폼 — 무동작
# ────────────────────────────────────────────────────────────────────
class _NullHotkeyListener:
    def __init__(self, callback: Callable[[], None]) -> None:
        self.callback = callback

    def start(self) -> bool:
        print("[pigeon] hotkey: 이 플랫폼에선 글로벌 단축키 미지원 — 트레이 메뉴로 종료하세요", flush=True)
        return False

    def stop(self) -> None:
        pass


# 플랫폼에 맞는 구현 선택
if IS_MAC:
    HotkeyListener = _MacHotkeyListener
elif IS_WINDOWS:
    HotkeyListener = _WindowsHotkeyListener
else:
    HotkeyListener = _NullHotkeyListener


def hotkey_label() -> str:
    """UI 표기용 종료 단축키 문자열."""
    if IS_MAC:
        return "⌃⌥⌘Q"
    if IS_WINDOWS:
        return "Ctrl+Alt+Q"
    return ""
