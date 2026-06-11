from __future__ import annotations

import math
import random
from enum import Enum, auto
from typing import Callable, Optional

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap


class State(Enum):
    IDLE = auto()
    WALK = auto()
    PECK = auto()
    FLY = auto()
    EAT = auto()  # 모이 위에서 쪼아 먹는 중


class Pigeon:
    """비둘기 한 마리. 타겟 좌표를 추적하며 걷기/쪼기/푸드덕 상태머신을 돈다."""

    def __init__(
        self,
        target_provider: Callable[[], Optional[QPointF]],
        *,
        name: str = "pigeon",
        speed: float = 220.0,
        peck_interval_ms: int = 600,
        fly_duration_ms: int = 1200,
        scale: int = 3,
        body_color: QColor | None = None,
    ) -> None:
        self.name = name
        self.target_provider = target_provider
        self.speed = speed
        self.peck_interval_ms = peck_interval_ms
        self.fly_duration_ms = fly_duration_ms
        self.scale = scale
        self.body_color = body_color or QColor(110, 120, 140)

        self.pos = QPointF(400.0, 400.0)
        self.facing = 1  # 1: right, -1: left
        self.state = State.IDLE
        self._state_time_ms = 0
        self._anim_time_ms = 0
        self._fly_target: Optional[QPointF] = None
        # 모이 시스템 — main.py에서 set_feed_manager 로 주입
        self._feed_manager = None
        self._eat_target: Optional[QPointF] = None
        self._eat_duration_ms = 1500  # 모이 한 알 먹는 데 걸리는 시간

    # 화면 위 비둘기가 차지하는 사각형 (충돌/클릭 판정용) — 32x32 프레임 기준
    def bounding_rect(self) -> QRectF:
        w = 32 * self.scale
        h = 32 * self.scale
        return QRectF(self.pos.x() - w / 2, self.pos.y() - h, w, h)

    def hit_test(self, point: QPointF) -> bool:
        return self.bounding_rect().contains(point)

    # ───── 상태 전환 ──────────────────────────────────────────
    def startle(self) -> None:
        """클릭당했을 때: 푸드덕 날아오름."""
        self.state = State.FLY
        self._state_time_ms = 0
        self._anim_time_ms = 0
        # 랜덤한 방향으로 적당히 짧게 도망
        angle = random.uniform(-math.pi, 0)  # 위쪽 반원
        dist = random.uniform(180, 320)
        self._fly_target = QPointF(
            self.pos.x() + math.cos(angle) * dist,
            self.pos.y() + math.sin(angle) * dist,
        )

    def set_feed_manager(self, fm) -> None:
        self._feed_manager = fm

    # ───── 매 프레임 업데이트 ──────────────────────────────────
    def update(self, dt_ms: int, screen_rect: QRectF) -> None:
        self._state_time_ms += dt_ms
        self._anim_time_ms += dt_ms

        if self.state == State.FLY:
            self._update_fly(dt_ms, screen_rect)
            return

        # 모이가 있으면 그쪽으로 우선 이동 / 도착하면 먹기
        if self._feed_manager is not None and self._feed_manager.count() > 0:
            self._update_feed(dt_ms, screen_rect)
            return
        # 모이 다 먹었으면 EAT 상태 해제
        if self.state == State.EAT:
            self.state = State.IDLE
            self._eat_target = None

        target = self.target_provider()
        if target is None:
            self.state = State.IDLE
            return

        dx = target.x() - self.pos.x()
        dy = target.y() - self.pos.y()
        dist = math.hypot(dx, dy)
        arrive_radius = 24.0

        if dist > arrive_radius:
            if self.state != State.WALK:
                self.state = State.WALK
                self._state_time_ms = 0
            self.facing = 1 if dx >= 0 else -1
            step = self.speed * (dt_ms / 1000.0)
            step = min(step, dist)
            self.pos.setX(self.pos.x() + dx / dist * step)
            self.pos.setY(self.pos.y() + dy / dist * step)
        else:
            if self.state != State.PECK:
                self.state = State.PECK
                self._state_time_ms = 0

        # 가상 데스크탑 밖으로 나가지 않게 클램프 (32x32 스프라이트 기준)
        margin = 32 * self.scale
        self.pos.setX(max(screen_rect.left() + margin / 2, min(screen_rect.right() - margin / 2, self.pos.x())))
        self.pos.setY(max(screen_rect.top() + margin, min(screen_rect.bottom() - 4, self.pos.y())))

    def _update_feed(self, dt_ms: int, screen_rect: QRectF) -> None:
        """모이 추적 + 도착 시 먹기. _feed_manager 있고 모이 1개 이상일 때만 호출.

        도착 위치는 모이 좌표 그대로가 아니라 facing 방향으로 부리 길이만큼 떨어진
        위치 — 비둘기 발이 모이를 밟지 않고 부리로 정확히 쪼는 그림이 되도록 한다.
        """
        fm = self._feed_manager
        # 현재 타겟이 없거나 사라졌으면 가장 가까운 모이로 재타겟
        if self._eat_target is None:
            self._eat_target = fm.nearest(self.pos)
            if self._eat_target is None:
                self.state = State.IDLE
                return
            self.state = State.WALK
            self._state_time_ms = 0

        target = self._eat_target
        # 비둘기 facing: 모이가 오른쪽이면 +1, 왼쪽이면 -1.
        # 비둘기 발은 모이의 (facing 반대쪽으로 beak_offset px) 위치에 멈춰야
        # 부리(머리)가 모이 위에 정확히 온다.
        beak_offset = 10 * self.scale  # 부리가 머리에서 facing 방향으로 튀어나간 거리
        side = 1 if target.x() >= self.pos.x() else -1
        stand_x = target.x() - side * beak_offset
        stand_y = target.y()
        dx = stand_x - self.pos.x()
        dy = stand_y - self.pos.y()
        dist = math.hypot(dx, dy)
        arrive_radius = 6.0

        if dist > arrive_radius:
            # 모이 옆 정지점으로 이동
            if self.state != State.WALK:
                self.state = State.WALK
                self._state_time_ms = 0
            self.facing = 1 if dx >= 0 else -1
            step = self.speed * (dt_ms / 1000.0)
            step = min(step, dist)
            self.pos.setX(self.pos.x() + dx / dist * step)
            self.pos.setY(self.pos.y() + dy / dist * step)
        else:
            # 도착 → facing을 모이 쪽으로 확정 후 먹기
            self.facing = side
            if self.state != State.EAT:
                self.state = State.EAT
                self._state_time_ms = 0
            if self._state_time_ms >= self._eat_duration_ms:
                fm.eat_at(target)
                self._eat_target = None  # 다음 tick에 새 타겟 잡음
                self._state_time_ms = 0

        # 화면 클램프
        margin = 32 * self.scale
        self.pos.setX(max(screen_rect.left() + margin / 2, min(screen_rect.right() - margin / 2, self.pos.x())))
        self.pos.setY(max(screen_rect.top() + margin, min(screen_rect.bottom() - 4, self.pos.y())))

    def _update_fly(self, dt_ms: int, screen_rect: QRectF) -> None:
        if self._fly_target is None:
            self.state = State.IDLE
            return
        dx = self._fly_target.x() - self.pos.x()
        dy = self._fly_target.y() - self.pos.y()
        dist = math.hypot(dx, dy)
        fly_speed = self.speed * 2.5
        step = fly_speed * (dt_ms / 1000.0)
        self.facing = 1 if dx >= 0 else -1
        if dist <= step or self._state_time_ms >= self.fly_duration_ms:
            self._fly_target = None
            self.state = State.IDLE
            return
        self.pos.setX(self.pos.x() + dx / dist * step)
        self.pos.setY(self.pos.y() + dy / dist * step)

    # ───── 렌더링 (스프라이트 없을 때의 자리표시자) ──────────────
    def paint(self, painter: QPainter, sprites: dict[str, list[QPixmap]] | None = None) -> None:
        if sprites:
            self._paint_sprite(painter, sprites)
        else:
            self._paint_placeholder(painter)

    def _paint_sprite(self, painter: QPainter, sprites: dict[str, list[QPixmap]]) -> None:
        key = {
            State.IDLE: "walk",
            State.WALK: "walk",
            State.PECK: "peck",
            State.EAT: "peck",
            State.FLY: "fly",
        }[self.state]
        frames = sprites.get(key) or sprites.get("walk")
        if not frames:
            self._paint_placeholder(painter)
            return
        if self.state == State.FLY:
            fps = 14
        elif self.state in (State.PECK, State.EAT):
            fps = max(4, min(20, int(8 * (600 / max(1, self.peck_interval_ms)))))
        else:
            fps = max(4, min(24, int(8 * (self.speed / 220.0))))
        frame_idx = int(self._anim_time_ms / (1000 / fps)) % len(frames)
        pix = frames[frame_idx]
        w = pix.width() * self.scale
        h = pix.height() * self.scale
        painter.save()
        painter.translate(self.pos.x(), self.pos.y() - h)
        # Painter에 scale을 직접 걸고 픽맵은 원본 크기 그대로 그림 (DPR/source-rect 이슈 회피)
        sx = -self.scale if self.facing < 0 else self.scale
        painter.scale(sx, self.scale)
        # 원점이 (pos.x, pos.y - h)이고 scale=2면 픽맵의 0,0 ~ 32,32가 화면상 0,0 ~ 64,64.
        # 중심을 비둘기 위치에 맞추기 위해 픽맵을 가로로 -16 (= -pix.width()/2) 이동해서 그림.
        painter.drawPixmap(QPoint(-pix.width() // 2, 0), pix)
        painter.restore()

    def _paint_placeholder(self, painter: QPainter) -> None:
        s = self.scale
        body_w = 14 * s
        body_h = 10 * s
        cx = self.pos.x()
        cy = self.pos.y() - body_h / 2

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # 몸통
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.body_color)
        painter.drawEllipse(QPointF(cx, cy), body_w / 2, body_h / 2)

        # 머리
        head_r = 4 * s
        head_cx = cx + self.facing * (body_w / 2 - 2 * s)
        head_cy = cy - body_h / 2 - head_r / 2
        # 쪼기 상태면 머리를 아래로 흔듦
        if self.state == State.PECK:
            peck_phase = (self._anim_time_ms % self.peck_interval_ms) / self.peck_interval_ms
            head_cy += math.sin(peck_phase * math.pi) * 8 * s / 2
        painter.setBrush(self.body_color.darker(115))
        painter.drawEllipse(QPointF(head_cx, head_cy), head_r, head_r)

        # 부리
        painter.setBrush(QColor(230, 180, 70))
        beak_tip_x = head_cx + self.facing * (head_r + 3 * s)
        painter.drawPolygon([
            QPointF(head_cx + self.facing * head_r * 0.6, head_cy - 1 * s),
            QPointF(head_cx + self.facing * head_r * 0.6, head_cy + 1 * s),
            QPointF(beak_tip_x, head_cy),
        ])

        # 눈
        painter.setBrush(QColor(20, 20, 20))
        painter.drawEllipse(
            QPointF(head_cx + self.facing * head_r * 0.3, head_cy - head_r * 0.2),
            max(1.0, 0.6 * s),
            max(1.0, 0.6 * s),
        )

        # 다리 (걸을 때 흔들림)
        if self.state != State.FLY:
            walk_phase = math.sin(self._anim_time_ms / 100.0) if self.state == State.WALK else 0
            leg_y = cy + body_h / 2
            painter.setPen(QColor(230, 130, 60))
            for i, off in enumerate((-2 * s, 2 * s)):
                wobble = walk_phase * (2 * s if i == 0 else -2 * s)
                painter.drawLine(
                    QPointF(cx + off, leg_y),
                    QPointF(cx + off + wobble, leg_y + 4 * s),
                )

        # 날 때는 날개 표시
        if self.state == State.FLY:
            wing_phase = math.sin(self._anim_time_ms / 60.0)
            wing_y_off = wing_phase * 6 * s
            painter.setBrush(self.body_color.lighter(115))
            painter.drawEllipse(
                QPointF(cx - 4 * s, cy - 2 * s + wing_y_off),
                4 * s, 2 * s,
            )
            painter.drawEllipse(
                QPointF(cx + 4 * s, cy - 2 * s + wing_y_off),
                4 * s, 2 * s,
            )

        painter.restore()
