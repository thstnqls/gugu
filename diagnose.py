"""진단용: 오버레이가 화면에 뜨는지만 확인.
빨간 사각형 + 큰 노란 원이 화면 좌상단에 5초간 보여야 함.
"""
import sys

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QPainter
from PySide6.QtWidgets import QApplication, QWidget


class Diag(QWidget):
    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        screens = QGuiApplication.screens()
        rect = screens[0].geometry()
        for s in screens[1:]:
            rect = rect.united(s.geometry())
        print(f"virtual desktop: {rect}")
        self.setGeometry(rect)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # 좌상단 100x100 빨간 박스
        p.fillRect(QRect(50, 50, 200, 200), QColor(255, 0, 0, 220))
        # 중앙 노란 원
        c = self.rect().center()
        p.setBrush(QColor(255, 230, 0, 230))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(c, 80, 80)
        # 텍스트
        p.setPen(QColor(0, 0, 0))
        p.drawText(c, "PIGEON OVERLAY OK")


def main():
    app = QApplication(sys.argv)
    w = Diag()
    w.show()
    print("overlay shown. closing in 5s...")
    QTimer.singleShot(5000, app.quit)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
