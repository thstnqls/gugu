from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPointF
from PySide6.QtGui import QCursor


def get_global_mouse_pos() -> Optional[QPointF]:
    p = QCursor.pos()
    return QPointF(p.x(), p.y())
