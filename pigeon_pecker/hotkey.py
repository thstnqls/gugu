"""macOS 글로벌 키보드 단축키 — ⌃⌥⌘Q로 앱 강제 종료.

CGEventTap을 사용해 입력 모니터링 권한이 필요할 수 있음.
권한 없어도 메뉴바 트레이 메뉴 "종료" + `pkill` 으로 대체 가능.
"""
from __future__ import annotations

import threading
from typing import Callable, Optional

try:
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


class HotkeyListener:
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
        # 짧게 기다려서 시작됐는지 확인
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
                # 필요한 modifier 다 눌렸는지 (정확히 일치할 필요는 없고 포함만)
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
