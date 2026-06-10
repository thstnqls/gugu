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

    # ───── 매 프레임 업데이트 ──────────────────────────────────
    def update(self, dt_ms: int, screen_rect: QRectF) -> None:
        self._state_time_ms += dt_ms
        self._anim_time_ms += dt_ms

        if self.state == State.FLY:
            self._update_fly(dt_ms, screen_rect)
            return

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
            State.FLY: "fly",
        }[self.state]
        frames = sprites.get(key) or sprites.get("walk")
        if not frames:
            self._paint_placeholder(painter)
            return
        fps = 8 if self.state != State.FLY else 14
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
