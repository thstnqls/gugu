from __future__ import annotations

from typing import List

import os

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QMouseEvent, QPainter, QPen, QScreen
from PySide6.QtWidgets import QWidget

DEBUG_DRAW = os.environ.get("PIGEON_DEBUG_DRAW") == "1"

from .focus_keeper import remember_active_app, restore_previous_app
from .native_window import apply_occlusion_workaround, order_front_without_activating, raise_to_overlay_level, set_ignores_mouse_events
from .platform_support import IS_MAC
from .pigeon import Pigeon
from .settings import Settings
from .trackers.mouse import get_global_mouse_pos


class ScreenOverlay(QWidget):
    """단일 화면을 덮는 투명 오버레이. 비둘기는 글로벌 좌표 → 이 화면 로컬로 변환해서 그림."""

    def __init__(self, screen: QScreen, pigeons: List[Pigeon], settings: Settings) -> None:
        super().__init__(None)
        self._screen = screen
        self.pigeons = pigeons
        self.settings = settings
        self.sprites: dict[str, list] | None = None
        self.feed_manager = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.NoDropShadowWindowHint
            | Qt.WindowType.BypassWindowManagerHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        # 키보드 포커스 절대 안 받음 → 다른 앱 입력 안 뺏음
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._apply_click_through()
        self._fit_to_screen()

    def _fit_to_screen(self) -> None:
        g = self._screen.geometry()
        self.setGeometry(g)
        # 윈도우를 명시적으로 이 스크린에 배정 — 멀티모니터에서 중요
        win = self.windowHandle()
        if win is not None:
            win.setScreen(self._screen)

    def set_click_through(self, on: bool) -> None:
        self.settings.click_through = on
        self._apply_click_through()

    def _apply_click_through(self) -> None:
        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            self.settings.click_through,
        )
        # NSWindow 레벨에서도 동기화 — Qt 속성보다 더 강력
        set_ignores_mouse_events(self, self.settings.click_through)
        if self.isVisible():
            # hide/show 사이클 없이 NSWindow ignoresMouseEvents 토글만으로 즉시 반영됨
            raise_to_overlay_level(self)

    def show_on_screen(self) -> None:
        self.show()
        self._fit_to_screen()  # show() 후 다시 한 번 배정
        # 즉시 + 50ms 후 한 번 더 (NSWindow가 완전히 만들어진 후 확실하게)
        raise_to_overlay_level(self)
        apply_occlusion_workaround(self)
        set_ignores_mouse_events(self, self.settings.click_through)

        def _post_setup():
            raise_to_overlay_level(self)
            apply_occlusion_workaround(self)
            set_ignores_mouse_events(self, self.settings.click_through)
        QTimer.singleShot(50, _post_setup)
        QTimer.singleShot(300, _post_setup)

    def force_reshow(self) -> None:
        """occlusion으로 사라진 윈도우를 강제 재표시.
        ignoresMouseEvents=True 상태에선 orderFront만으론 부족할 수 있어,
        잠시 ignoresMouseEvents=False로 토글했다가 즉시 원복 — macOS가 윈도우를
        "사용자 가시 영역"으로 재분류하도록 강제."""
        print("[pigeon] force_reshow called", flush=True)
        # 1) 잠시 마우스 이벤트 받는 윈도우로 만듦 (occlusion 분류 갱신)
        set_ignores_mouse_events(self, False)
        # 2) hide/show 사이클 — 가장 강력한 재인식 트리거
        self.hide()
        self.show()
        self._fit_to_screen()
        # 3) 윈도우 레벨, occlusion 우회 재적용
        raise_to_overlay_level(self)
        apply_occlusion_workaround(self)
        order_front_without_activating(self)
        # 4) 즉시 원래 click-through 설정 복구
        set_ignores_mouse_events(self, self.settings.click_through)
        # 5) 우리가 활성화됐으면 직전 앱 복귀
        restore_previous_app()
        QTimer.singleShot(50, restore_previous_app)

    # ───── 페인트 ─────────────────────────────────────────────
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # Pixel art가 부드럽게 흐려지지 않도록
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        g = self._screen.geometry()
        # 모이 먼저 (비둘기 발 아래로 보이게)
        if self.feed_manager is not None and self.feed_manager.count() > 0:
            painter.save()
            painter.translate(-g.x(), -g.y())
            painter.setPen(QPen(QColor(180, 130, 0, 230), 1))
            painter.setBrush(QColor(255, 200, 40, 240))
            for seed in self.feed_manager.snapshot():
                if not g.contains(seed.toPoint()):
                    continue
                painter.drawEllipse(seed, 3.0, 3.0)
            painter.restore()
        for p in self.pigeons:
            br = p.bounding_rect()
            local_rect = QRectF(
                br.x() - g.x(), br.y() - g.y(), br.width(), br.height()
            )
            # 이 화면과 안 겹치면 스킵
            if local_rect.right() < 0 or local_rect.left() > self.width():
                continue
            if local_rect.bottom() < 0 or local_rect.top() > self.height():
                continue
            painter.save()
            painter.translate(-g.x(), -g.y())
            p.paint(painter, self.sprites)
            if DEBUG_DRAW:
                # bounding rect: 빨강
                painter.setPen(QPen(QColor(255, 0, 0, 200), 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(br)
                # 위치: 노란 십자
                painter.setPen(QPen(QColor(255, 240, 0, 230), 2))
                painter.drawLine(QPointF(br.center().x() - 10, p.pos.y()), QPointF(br.center().x() + 10, p.pos.y()))
                painter.drawLine(QPointF(br.center().x(), p.pos.y() - 10), QPointF(br.center().x(), p.pos.y() + 10))
            painter.restore()

    # ───── 클릭 → 푸드덕 ─────────────────────────────────────
    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        g = self._screen.geometry()
        global_pos = QPointF(event.position().x() + g.x(), event.position().y() + g.y())
        hit = False
        for p in self.pigeons:
            if p.hit_test(global_pos):
                p.startle()
                hit = True
                break
        # 클릭한 순간 macOS가 우리를 활성 앱으로 만듦 → 즉시 직전 앱으로 복귀
        restore_previous_app()
        if hit:
            event.accept()
        else:
            event.ignore()


class OverlayManager:
    """모든 화면을 덮는 오버레이 집합 + 매 프레임 업데이트 루프."""

    def __init__(self, pigeons: List[Pigeon], settings: Settings) -> None:
        self.pigeons = pigeons
        self.settings = settings
        self.sprites: dict[str, list] | None = None
        self.overlays: list[ScreenOverlay] = []

        for screen in QGuiApplication.screens():
            ov = ScreenOverlay(screen, pigeons, settings)
            self.overlays.append(ov)

        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)
        self._interval_ms = 1000 // 60

        # 마우스 정지 추적 — 멈춘 지 1초 지나면 비둘기 강제 재표시.
        # 단 한번 재표시한 뒤엔 다시 움직였다 멈출 때까지 대기 (깜빡임 방지)
        self._last_mouse_pos: QPointF | None = None
        self._mouse_still_ms = 0
        self._reshow_armed = True  # True면 다음 정지 시 재표시 허용

    def show(self) -> None:
        for ov in self.overlays:
            ov.sprites = self.sprites
            ov.show_on_screen()

    def start(self) -> None:
        """프레임 업데이트 루프 시작 (60fps)."""
        self._timer.start(self._interval_ms)

    def stop(self) -> None:
        self._timer.stop()

    def set_sprites(self, sprites: dict[str, list] | None) -> None:
        self.sprites = sprites
        for ov in self.overlays:
            ov.sprites = sprites

    def set_feed_manager(self, fm) -> None:
        for ov in self.overlays:
            ov.feed_manager = fm
        for p in self.pigeons:
            p.set_feed_manager(fm)

    def set_click_through(self, on: bool) -> None:
        for ov in self.overlays:
            ov.set_click_through(on)

    def _virtual_desktop_rect(self) -> QRectF:
        rect = self.overlays[0]._screen.geometry()
        for ov in self.overlays[1:]:
            rect = rect.united(ov._screen.geometry())
        return QRectF(rect)

    def virtual_desktop_rect(self) -> QRectF:
        return self._virtual_desktop_rect()

    def _tick(self) -> None:
        # 현재 활성 앱 기억 (우리가 아닐 때만 기록됨)
        remember_active_app()
        vdesk = self._virtual_desktop_rect()
        for p in self.pigeons:
            p.update(self._interval_ms, vdesk)

        # 마우스 정지 감지 → occlusion으로 사라진 비둘기 재표시
        self._check_mouse_still_and_reshow()

        for ov in self.overlays:
            ov.update()

    def _check_mouse_still_and_reshow(self) -> None:
        # 가려짐(occlusion)으로 오버레이가 사라지는 건 macOS 고유 문제다.
        # Windows/기타에선 항상-위 플래그로 유지되므로 강제 재표시(hide/show)를
        # 하지 않는다 — 매번 깜빡이고 포커스를 뺏을 수 있기 때문.
        if not IS_MAC:
            return
        cur = get_global_mouse_pos()
        if cur is None:
            return
        moved = False
        if self._last_mouse_pos is None:
            moved = True
        else:
            dx = cur.x() - self._last_mouse_pos.x()
            dy = cur.y() - self._last_mouse_pos.y()
            if abs(dx) > 1 or abs(dy) > 1:
                moved = True
        self._last_mouse_pos = cur

        if moved:
            self._mouse_still_ms = 0
            self._reshow_armed = True  # 다시 움직였으니 다음 정지 때 재표시 허용
            return

        self._mouse_still_ms += self._interval_ms
        # 1초 이상 가만히 + 아직 재표시 안 했으면 강제 재표시
        if self._reshow_armed and self._mouse_still_ms >= 1000:
            self._reshow_armed = False
            print(f"[pigeon] mouse still {self._mouse_still_ms}ms → reshow {len(self.overlays)} overlays", flush=True)
            for ov in self.overlays:
                ov.force_reshow()
