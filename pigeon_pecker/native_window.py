"""OS별 창 헬퍼 디스패처.

overlay.py(Qt 오버레이)는 여기서 import 한다.
 - macOS  → macos_window.py (NSWindow 조작)
 - Windows → win_window.py  (user32 확장 스타일)
 - 그 외   → 무동작 스텁
모든 함수 시그니처는 동일: (qwidget, ...) -> bool
"""
from __future__ import annotations

from .platform_support import IS_MAC, IS_WINDOWS

if IS_MAC:
    from .macos_window import (  # noqa: F401
        apply_occlusion_workaround,
        order_front_without_activating,
        raise_to_overlay_level,
        set_ignores_mouse_events,
    )
elif IS_WINDOWS:
    from .win_window import (  # noqa: F401
        apply_occlusion_workaround,
        order_front_without_activating,
        raise_to_overlay_level,
        set_ignores_mouse_events,
    )
else:
    def apply_occlusion_workaround(qwidget) -> bool:  # noqa: D103
        return False

    def order_front_without_activating(qwidget) -> bool:  # noqa: D103
        return False

    def raise_to_overlay_level(qwidget) -> bool:  # noqa: D103
        return False

    def set_ignores_mouse_events(qwidget, ignore: bool) -> bool:  # noqa: D103
        return False
