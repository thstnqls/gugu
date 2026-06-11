"""모이(seed) 관리.

비둘기는 모이가 있으면 가장 가까운 것부터 먹으러 가고, 다 먹으면 마우스 추적으로 복귀한다.

좌표는 모두 top-left 글로벌 좌표계 (pigeon.pos 와 동일).
스레드 안전 — 전역 후크 스레드에서도 호출 가능하다.
"""
from __future__ import annotations

import math
import random
import threading
from typing import List, Optional

from PySide6.QtCore import QPointF, QRectF


# 트레이 "모이 주기" 한 번에 뿌리는 모이 개수 범위
SCATTER_COUNT_MIN = 10
SCATTER_COUNT_MAX = 15


class FeedManager:
    def __init__(self) -> None:
        self._seeds: List[QPointF] = []
        self._lock = threading.Lock()

    def add(self, point: QPointF) -> None:
        with self._lock:
            self._seeds.append(QPointF(point))

    def scatter(self, rect: QRectF, count: Optional[int] = None) -> int:
        """주어진 사각형(보통 한 모니터) 안에 모이를 랜덤 분산. 추가된 개수 반환.

        rect 가장자리에 모이가 너무 붙지 않도록 내부 안전 마진을 한 번 더 적용한다.
        호출자에서 이미 큰 padding을 줬더라도 안전 — 마진은 사각형 짧은 변의 5%로
        자동 제한된다.
        """
        if count is None:
            count = random.randint(SCATTER_COUNT_MIN, SCATTER_COUNT_MAX)
        short_side = min(rect.width(), rect.height())
        if short_side <= 0:
            return 0
        margin = min(40.0, short_side * 0.05)
        x0 = rect.left() + margin
        x1 = rect.right() - margin
        y0 = rect.top() + margin
        y1 = rect.bottom() - margin
        if x1 <= x0 or y1 <= y0:
            return 0
        with self._lock:
            for _ in range(count):
                self._seeds.append(QPointF(random.uniform(x0, x1), random.uniform(y0, y1)))
        return count

    def clear(self) -> None:
        with self._lock:
            self._seeds.clear()

    def snapshot(self) -> List[QPointF]:
        with self._lock:
            return [QPointF(p) for p in self._seeds]

    def count(self) -> int:
        with self._lock:
            return len(self._seeds)

    def nearest(self, point: QPointF) -> Optional[QPointF]:
        with self._lock:
            if not self._seeds:
                return None
            best = self._seeds[0]
            best_d = _dist2(point, best)
            for s in self._seeds[1:]:
                d = _dist2(point, s)
                if d < best_d:
                    best_d = d
                    best = s
            return QPointF(best)

    def eat_at(self, point: QPointF, radius: float = 16.0) -> bool:
        """주어진 좌표 근처의 모이 하나 제거. 제거 성공 시 True."""
        r2 = radius * radius
        with self._lock:
            for i, s in enumerate(self._seeds):
                if _dist2(point, s) <= r2:
                    del self._seeds[i]
                    return True
            return False


def _dist2(a: QPointF, b: QPointF) -> float:
    dx = a.x() - b.x()
    dy = a.y() - b.y()
    return dx * dx + dy * dy
