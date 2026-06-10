"""Qt 윈도우의 underlying NSWindow에 macOS 전용 설정 적용."""
from __future__ import annotations

try:
    import objc
    from AppKit import (
        NSWindow,
        NSFloatingWindowLevel,
        NSScreenSaverWindowLevel,
        NSStatusWindowLevel,
        NSWindowCollectionBehaviorCanJoinAllSpaces,
        NSWindowCollectionBehaviorStationary,
        NSWindowCollectionBehaviorIgnoresCycle,
        NSWindowCollectionBehaviorFullScreenAuxiliary,
        NSWindowCollectionBehaviorAuxiliary,
        NSWindowCollectionBehaviorCanJoinAllApplications,
        NSWindowCollectionBehaviorTransient,
        NSWindowStyleMaskNonactivatingPanel,
    )
    from Quartz import CGShieldingWindowLevel
    APPKIT_AVAILABLE = True
except Exception:
    APPKIT_AVAILABLE = False


def _get_ns_window(qwidget):
    if not APPKIT_AVAILABLE:
        return None
    try:
        win = qwidget.windowHandle()
        if win is None:
            return None
        from ctypes import c_void_p
        view = objc.objc_object(c_void_p=int(win.winId()))
        return view.window()
    except Exception:
        return None


def diagnose_window(qwidget, label: str = "") -> None:
    """현재 NSWindow 상태를 로그로 출력 — 사라짐 디버깅용."""
    ns = _get_ns_window(qwidget)
    if ns is None:
        print(f"[pigeon][diag {label}] NSWindow not available", flush=True)
        return
    try:
        occ_state = int(ns.occlusionState())
        # NSWindowOcclusionStateVisible = 1 << 1 = 2
        is_visible_occlusion = bool(occ_state & 0x2)
        shield = CGShieldingWindowLevel()
        print(
            f"[pigeon][diag {label}] "
            f"visible={ns.isVisible()} level={ns.level()}/{shield} alpha={ns.alphaValue():.2f} "
            f"onActiveSpace={ns.isOnActiveSpace()} "
            f"occlusion_visible={is_visible_occlusion} (raw=0x{occ_state:x})",
            flush=True,
        )
    except Exception as e:
        print(f"[pigeon][diag {label}] error: {e}", flush=True)


def apply_occlusion_workaround(qwidget) -> bool:
    """macOS occlusion 최적화 우회: alpha를 0.99로 살짝 낮춰서 macOS가 paint 스킵 안 하게.
    체감상 완전 불투명과 차이 없음."""
    ns = _get_ns_window(qwidget)
    if ns is None:
        return False
    try:
        ns.setAlphaValue_(0.99)
        return True
    except Exception:
        return False


def order_front_without_activating(qwidget) -> bool:
    """우리 앱을 활성화시키지 않고 윈도우만 위로 올림 (활성 앱 포커스 유지)."""
    ns = _get_ns_window(qwidget)
    if ns is None:
        return False
    try:
        # orderFrontRegardless: 다른 앱이 활성이어도 윈도우를 보이게 함. 활성화는 안 시킴.
        ns.orderFrontRegardless()
        return True
    except Exception:
        return False


def set_ignores_mouse_events(qwidget, ignore: bool) -> bool:
    """NSWindow 레벨에서 마우스 이벤트 무시 설정.
    Qt의 WA_TransparentForMouseEvents보다 더 강력 — 윈도우 시스템이 이벤트를 우리 윈도우에
    아예 전달 안 함 → 진짜 click-through. floating level이어도 클릭이 밑 윈도우로 통과."""
    ns = _get_ns_window(qwidget)
    if ns is None:
        return False
    try:
        ns.setIgnoresMouseEvents_(ignore)
        return True
    except Exception:
        return False


def raise_to_overlay_level(qwidget) -> bool:
    """오버레이가 모든 일반 앱 + 메뉴바 위에 항상 떠 있게.
    또한 모든 Space(데스크탑)에 동시에 나타나도록 설정."""
    if not APPKIT_AVAILABLE:
        return False
    try:
        win = qwidget.windowHandle()
        if win is None:
            return False
        ns_view_ptr = win.winId()
        # winId()는 NSView*. 그 superview로 올라가 NSWindow를 얻음.
        from ctypes import c_void_p
        view = objc.objc_object(c_void_p=int(ns_view_ptr))
        ns_window = view.window()
        if ns_window is None:
            return False
        # Nonactivating panel mask: 이 윈도우는 클릭해도 key window/main window가 되지 않음.
        # → 다른 앱이 활성화되어도 우리 윈도우는 활성화 사이클에서 제외 → occlusion 면제
        # (이게 메뉴바 유틸/스티커 앱들이 항상 떠 있는 진짜 비결)
        try:
            current_mask = int(ns_window.styleMask())
            ns_window.setStyleMask_(current_mask | NSWindowStyleMaskNonactivatingPanel)
        except Exception:
            pass
        # FloatingLevel(3)이면 충분 — nonactivating mask가 핵심이라 레벨은 낮아도 OK.
        # 메뉴바도 안 가림.
        ns_window.setLevel_(NSFloatingWindowLevel)
        # 모든 Space + 모든 앱 활성 상태에서 보이게 + 보조 윈도우로 표시
        # (Auxiliary + CanJoinAllApplications가 핵심: 다른 앱 활성 시에도 occlusion 무시)
        behavior = (
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorStationary
            | NSWindowCollectionBehaviorIgnoresCycle
            | NSWindowCollectionBehaviorFullScreenAuxiliary
            | NSWindowCollectionBehaviorAuxiliary
            | NSWindowCollectionBehaviorCanJoinAllApplications
            | NSWindowCollectionBehaviorTransient
        )
        ns_window.setCollectionBehavior_(behavior)
        # 그림자 없애기 (투명 윈도우에서 그림자 잔상 방지)
        ns_window.setHasShadow_(False)
        # 키 윈도우/메인 윈도우 안 되게 — 다른 앱 포커스 안 뺏기게
        # (이건 Qt 레벨에서 FramelessWindowHint + Tool로도 어느 정도 됨)
        return True
    except Exception as e:
        print(f"[pigeon] raise_to_overlay_level failed: {e}", flush=True)
        return False
