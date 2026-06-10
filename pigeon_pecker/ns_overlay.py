"""네이티브 NSPanel 기반 오버레이.

Qt QWidget이 만든 NSPanel은 macOS occlusion 신호에 paint를 멈추는 문제가 있었음
(FUTURE_NATIVE_NSPANEL.md 참고). 직접 NSPanel을 만들고 NSWindowStyleMaskNonactivatingPanel을
설정하면 occlusion 사이클에서 완전히 제외되어 어떤 앱이 활성이어도 항상 떠 있음.
"""
from __future__ import annotations

import math
from typing import Callable, List, Optional

try:
    import objc
    from AppKit import (
        NSApplication,
        NSPanel,
        NSView,
        NSColor,
        NSBezierPath,
        NSScreen,
        NSWindowStyleMaskBorderless,
        NSWindowStyleMaskNonactivatingPanel,
        NSBackingStoreBuffered,
        NSFloatingWindowLevel,
        NSWindowCollectionBehaviorCanJoinAllSpaces,
        NSWindowCollectionBehaviorStationary,
        NSWindowCollectionBehaviorIgnoresCycle,
        NSWindowCollectionBehaviorFullScreenAuxiliary,
        NSGraphicsContext,
        NSImageInterpolationNone,
        NSCompositingOperationSourceOver,
        NSAffineTransform,
    )
    from Foundation import (
        NSObject,
        NSTimer,
        NSMakeRect,
        NSMakePoint,
        NSMakeSize,
        NSRunLoop,
        NSDefaultRunLoopMode,
    )
    # NSEventTrackingRunLoopMode은 AppKit에 있을 수도 있고 없을 수도. 없으면 문자열로 사용.
    try:
        from AppKit import NSEventTrackingRunLoopMode
    except ImportError:
        NSEventTrackingRunLoopMode = "NSEventTrackingRunLoopMode"
    APPKIT_AVAILABLE = True
except Exception as _e:
    APPKIT_AVAILABLE = False
    _IMPORT_ERROR = _e


# ────────────────────────────────────────────────────────────────────
# NSView: 비둘기 그리기
# ────────────────────────────────────────────────────────────────────

class PigeonView(NSView):
    """오버레이 내용물. 비둘기 리스트를 받아 글로벌 좌표 → NSView 로컬 좌표로 변환해 그림.

    macOS NSView 좌표계: 좌하단 = (0, 0), y가 위로 증가.
    Cocoa 화면 좌표계도 좌하단 = (0, 0).
    우리 비둘기 글로벌 좌표는 'top-left 기준'(Quartz CGEvent 좌표)이므로 y 변환 필요.
    """

    def initWithFrame_screenFrame_pigeons_sprites_scale_(
        self, frame, screen_frame, pigeons, sprites, scale,
    ):
        self = objc.super(PigeonView, self).initWithFrame_(frame)
        if self is None:
            return None
        self._screen_frame = screen_frame  # Cocoa 좌표 (좌하단 기준)
        self._pigeons = pigeons
        self._sprites = sprites
        self._scale = scale
        return self

    def isOpaque(self):
        return False

    def acceptsFirstMouse_(self, event):
        # True여야 비활성 윈도우에서도 첫 클릭부터 받음 (활성화는 nonactivating mask가 막아줌)
        return True

    def mouseDown_(self, event):
        """비둘기 클릭 → 푸드덕. click_through OFF일 때만 호출됨
        (ON이면 NSWindow.setIgnoresMouseEvents가 막아서 여기 안 옴)."""
        try:
            loc = event.locationInWindow()  # NSView 로컬 좌표 (Cocoa bottom-left)
            # NSView 좌표 → 글로벌 Cocoa 좌표
            global_cocoa_x = loc.x + self._screen_frame.origin.x
            global_cocoa_y = loc.y + self._screen_frame.origin.y
            # → 비둘기는 top-left 좌표계로 살고 있음
            # cocoa_y가 큰 값일수록 위. top-left y는 작은 값일수록 위.
            # 글로벌 top = max(origin.y + height) = manager._global_screen_top_y
            top = getattr(self, "_global_top_y_cache", None)
            if top is None:
                # 폴백: 메인 화면 기준
                from AppKit import NSScreen
                top = max(s.frame().origin.y + s.frame().size.height for s in NSScreen.screens())
                self._global_top_y_cache = top
            top_left_y = top - global_cocoa_y
            from PySide6.QtCore import QPointF
            click_global = QPointF(global_cocoa_x, top_left_y)
            for p in self._pigeons:
                if p.hit_test(click_global):
                    p.startle()
                    break
        except Exception as e:
            print(f"[pigeon] mouseDown error: {e}", flush=True)
        # 우리 앱이 활성화됐을 수 있으니 직전 앱으로 복귀
        try:
            from .focus_keeper import restore_previous_app
            restore_previous_app()
        except Exception:
            pass

    def drawRect_(self, dirty_rect):
        # 배경 투명
        NSColor.clearColor().set()
        NSBezierPath.fillRect_(self.bounds())

        ctx = NSGraphicsContext.currentContext()
        if ctx is None:
            return
        ctx.setImageInterpolation_(NSImageInterpolationNone)  # 픽셀아트 보존

        screen_x = self._screen_frame.origin.x
        screen_y = self._screen_frame.origin.y
        screen_h = self._screen_frame.size.height
        scale = self._scale

        for p in self._pigeons:
            self._draw_pigeon(p, ctx, screen_x, screen_y, screen_h, scale)

    def _draw_pigeon(self, pigeon, ctx, screen_x, screen_y, screen_h, scale):
        """비둘기 1마리 그리기. pigeon.pos는 글로벌 top-left 좌표."""
        sprites = self._sprites
        if sprites is None:
            return

        # 상태 → 시트 키
        from .pigeon import State
        key = {
            State.IDLE: "walk",
            State.WALK: "walk",
            State.PECK: "peck",
            State.FLY: "fly",
        }.get(pigeon.state, "walk")
        frames = sprites.get(key) or sprites.get("walk")
        if not frames:
            return

        fps = 8 if pigeon.state != State.FLY else 14
        frame_idx = int(pigeon._anim_time_ms / (1000 / fps)) % len(frames)
        img = frames[frame_idx]
        img_size = img.size()
        fw = int(img_size.width)
        fh = int(img_size.height)
        draw_w = fw * scale
        draw_h = fh * scale

        # 비둘기 글로벌 top-left 좌표(우리 컨벤션) →
        # NSView 로컬 Cocoa 좌표(좌하단 기준)로 변환.
        #  - 글로벌 X(top-left) == 글로벌 X(Cocoa) 동일
        #  - Cocoa Y = screen_h - (top-left Y - screen_y_top)
        #    screen_y_top = (전체 화면 높이) - (스크린 frame y bottom-left) - (스크린 높이)
        #    여기서는 NSScreen.frame()이 Cocoa 좌표라 screen_y는 bottom-left y.
        #    pigeon.pos는 top-left 좌표계 (Y가 위에서 아래로 증가).
        #    → 전체 가상 데스크탑 변환은 manager가 처리. 여기는 단순화:
        #    "글로벌 top-left Y" → "Cocoa 글로벌 Y" 변환은 manager에서 미리 함.
        # 따라서 여기서는 pigeon.pos가 이미 'Cocoa 글로벌 좌표 (bottom-left)' 라고 가정.

        gx = pigeon.pos.x()
        # Manager가 매 tick마다 _cocoa_y를 세팅 (top-left → Cocoa bottom-left 변환)
        gy = getattr(pigeon, "_cocoa_y", pigeon.pos.y())

        # NSView 로컬 좌표
        lx = gx - screen_x
        ly = gy - screen_y

        # 화면 클립 — 안 겹치면 스킵
        if lx + draw_w / 2 < 0 or lx - draw_w / 2 > self.bounds().size.width:
            return
        if ly + draw_h < 0 or ly > self.bounds().size.height:
            return

        # 그릴 영역: 발 밑(ly) 기준으로 위로 draw_h만큼.
        # NSView 좌표는 y가 위로 증가하므로 dst_rect의 y는 ly (발 밑) 그대로 OK.
        dst_x = lx - draw_w / 2
        dst_y = ly  # 발이 ly에 닿고 머리는 ly + draw_h
        dst_rect = NSMakeRect(dst_x, dst_y, draw_w, draw_h)
        src_rect = NSMakeRect(0, 0, fw, fh)

        if pigeon.facing < 0:
            # 좌우 반전: AffineTransform으로 X축 미러링
            ctx.saveGraphicsState()
            try:
                t = NSAffineTransform.transform()
                t.translateXBy_yBy_(dst_x + draw_w, 0)
                t.scaleXBy_yBy_(-1, 1)
                t.concat()
                mirror_rect = NSMakeRect(0, dst_y, draw_w, draw_h)
                img.drawInRect_fromRect_operation_fraction_(
                    mirror_rect, src_rect, NSCompositingOperationSourceOver, 1.0
                )
            finally:
                ctx.restoreGraphicsState()
        else:
            img.drawInRect_fromRect_operation_fraction_(
                dst_rect, src_rect, NSCompositingOperationSourceOver, 1.0
            )


# ────────────────────────────────────────────────────────────────────
# 메인 매니저
# ────────────────────────────────────────────────────────────────────

class _TickHandler(NSObject):
    """NSTimer 콜백 호스트 — pyobjc는 메서드 이름이 selector라 클래스 메서드여야 함."""

    def initWithCallback_(self, cb):
        self = objc.super(_TickHandler, self).init()
        if self is None:
            return None
        self._cb = cb
        return self

    def tick_(self, timer):
        try:
            self._cb()
        except Exception as e:
            print(f"[pigeon] tick error: {e}", flush=True)


class NSOverlayManager:
    """모든 화면에 NSPanel 오버레이를 띄우고 매 프레임 업데이트."""

    def __init__(self, pigeons: List, settings) -> None:
        if not APPKIT_AVAILABLE:
            raise RuntimeError(f"AppKit not available: {globals().get('_IMPORT_ERROR')}")
        self.pigeons = pigeons
        self.settings = settings
        self.sprites = None
        self.panels: list = []
        self.views: list = []
        self._screens_snapshot = []  # NSScreen frame snapshots

        # NSScreen 정보 캐시
        for screen in NSScreen.screens():
            f = screen.frame()
            self._screens_snapshot.append(f)
            panel, view = self._create_panel_for_screen(f)
            self.panels.append(panel)
            self.views.append(view)

        self._timer = None
        self._handler = None
        self._interval = 1.0 / 60.0  # 60fps

        # 글로벌 좌표계 변환을 위한 화면 높이 (가장 위에 있는 화면 기준)
        self._global_screen_top_y = self._compute_global_top_y()
        # view들에 글로벌 top y 캐시 — mouseDown 좌표 변환용
        for v in self.views:
            v._global_top_y_cache = self._global_screen_top_y

    # ─ panel 생성 ───────────────────────────────────────────────
    def _create_panel_for_screen(self, screen_frame):
        style = (
            NSWindowStyleMaskBorderless
            | NSWindowStyleMaskNonactivatingPanel  # 핵심: 활성화 사이클 제외
        )
        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            screen_frame, style, NSBackingStoreBuffered, False,
        )
        panel.setLevel_(NSFloatingWindowLevel)
        panel.setBackgroundColor_(NSColor.clearColor())
        panel.setOpaque_(False)
        panel.setHasShadow_(False)
        panel.setIgnoresMouseEvents_(True)  # 진짜 click-through (NSWindow 레벨)
        panel.setHidesOnDeactivate_(False)
        panel.setBecomesKeyOnlyIfNeeded_(True)
        panel.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorStationary
            | NSWindowCollectionBehaviorIgnoresCycle
            | NSWindowCollectionBehaviorFullScreenAuxiliary
        )
        panel.setMovableByWindowBackground_(False)
        panel.setAlphaValue_(1.0)

        view = PigeonView.alloc().initWithFrame_screenFrame_pigeons_sprites_scale_(
            NSMakeRect(0, 0, screen_frame.size.width, screen_frame.size.height),
            screen_frame,
            self.pigeons,
            None,
            self.settings.pigeon_scale,
        )
        # 클릭 좌표 변환에 쓰일 글로벌 top-left 기준 y — manager가 다 만든 후 세팅 (아래)
        panel.setContentView_(view)
        # orderFrontRegardless: 활성화하지 않고 위로
        panel.orderFrontRegardless()
        return panel, view

    def _compute_global_top_y(self) -> float:
        """가상 데스크탑의 최상단 Cocoa Y (가장 큰 (origin.y + size.height))."""
        top = 0.0
        for f in self._screens_snapshot:
            t = f.origin.y + f.size.height
            if t > top:
                top = t
        return top

    # ─ 외부 API ──────────────────────────────────────────────────
    def set_sprites(self, sprites):
        self.sprites = sprites
        for v in self.views:
            v._sprites = sprites

    def show(self):
        for p in self.panels:
            p.orderFrontRegardless()

    def set_click_through(self, on: bool):
        self.settings.click_through = on
        for p in self.panels:
            p.setIgnoresMouseEvents_(on)

    def virtual_desktop_rect(self):
        """가상 데스크탑 영역을 'top-left 기준' QRectF로 반환 (pigeon.update용)."""
        from PySide6.QtCore import QRectF
        # 가장 좌측 x, 가장 위쪽(top-left 기준 y는 0)
        min_x = min(f.origin.x for f in self._screens_snapshot)
        max_x = max(f.origin.x + f.size.width for f in self._screens_snapshot)
        # top-left 좌표계: y=0이 화면 최상단. height = (top - bottom)
        max_top = self._global_screen_top_y
        min_bottom = min(f.origin.y for f in self._screens_snapshot)
        height = max_top - min_bottom
        return QRectF(min_x, 0, max_x - min_x, height)

    def start(self):
        """60fps 타이머 시작 — 비둘기 업데이트 + 뷰 갱신."""
        self._handler = _TickHandler.alloc().initWithCallback_(self._tick)
        self._timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            self._interval, self._handler, "tick:", None, True,
        )
        # event tracking 모드에서도 동작 (메뉴 띄울 때도 멈춤 없게)
        NSRunLoop.currentRunLoop().addTimer_forMode_(self._timer, NSEventTrackingRunLoopMode)

    def stop(self):
        if self._timer is not None:
            self._timer.invalidate()
            self._timer = None

    # ─ 매 프레임 ──────────────────────────────────────────────────
    def _tick(self):
        # 비둘기 업데이트 — pigeon은 top-left 좌표계로 사용 중
        vdesk = self.virtual_desktop_rect()
        dt_ms = int(self._interval * 1000)
        for pig in self.pigeons:
            pig.update(dt_ms, vdesk)

        # NSView 그리기 — pigeon.pos(top-left) → cocoa global Y 변환
        # cocoa_y = global_top_y - top_left_y
        # 각 뷰는 자기 화면의 cocoa origin/size 기준으로 다시 변환.
        # 여기서는 pigeon에 임시 'cocoa_pos' 속성을 세팅해서 view가 읽도록 함.
        for pig in self.pigeons:
            pig._cocoa_y = self._global_screen_top_y - pig.pos.y()

        # 각 뷰에 그리기 명령
        for view in self.views:
            view.setNeedsDisplay_(True)


# ────────────────────────────────────────────────────────────────────
# pigeon.pos 좌표계가 'top-left' 인데 NSView는 cocoa(bottom-left).
# PigeonView._draw_pigeon에서 pigeon.pos.y()는 top-left Y. 변환:
#   cocoa_y = global_top - top_left_y  → 그러나 manager에서 _cocoa_y 세팅함.
# PigeonView가 pig._cocoa_y를 사용하도록 수정 — 별도 파일에서 monkey patch보다는
# View 코드 자체를 cocoa 좌표 가정하도록 했으니, 위에서 _cocoa_y를 그냥 새 좌표로 보고
# pig.pos.x(), pig._cocoa_y 사용하면 됨.
# ────────────────────────────────────────────────────────────────────
