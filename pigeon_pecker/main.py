from __future__ import annotations

import os
import sys
from typing import Optional

from PySide6.QtCore import QMetaObject, QPointF, Qt
from PySide6.QtGui import QAction, QColor, QGuiApplication, QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from .hotkey import HotkeyListener
from .ns_overlay import NSOverlayManager
from .ns_sprites import load_ns_sprites
from .pigeon import Pigeon
from .settings import Settings
from .sprites import load_sprites  # 트레이 아이콘용
from .trackers.mouse import get_global_mouse_pos


def _make_tray_icon_from_sprites(sprites: dict[str, list] | None) -> QIcon:
    """walking 프레임 1개를 트레이 아이콘으로 변환."""
    if sprites and sprites.get("walk"):
        pix: QPixmap = sprites["walk"][0]
        return QIcon(pix.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation))
    pix = QPixmap(32, 32)
    pix.fill(Qt.GlobalColor.transparent)
    return QIcon(pix)


class App:
    def __init__(self) -> None:
        # 앱 이름을 GUGU로 설정 — 메뉴바, About 대화상자 등에 표시됨
        QApplication.setApplicationName("GUGU")
        QApplication.setApplicationDisplayName("GUGU")
        QApplication.setOrganizationName("GUGU")

        self.qapp = QApplication(sys.argv)
        self.qapp.setQuitOnLastWindowClosed(False)

        print("=" * 60, flush=True)
        print(f"[pigeon] PID: {os.getpid()}", flush=True)
        print("[pigeon] 종료 방법:", flush=True)
        print("[pigeon]   1) ⌃⌥⌘Q (Control+Option+Command+Q) 어디서나", flush=True)
        print("[pigeon]   2) 메뉴바 비둘기 아이콘 → 종료", flush=True)
        print(f"[pigeon]   3) 터미널: kill {os.getpid()}", flush=True)
        print("[pigeon]   4) 터미널: pkill -f pigeon_pecker.main", flush=True)
        print("=" * 60, flush=True)

        self.settings = Settings()

        sprites = load_sprites()
        print(f"[pigeon] sprites loaded: {list(sprites.keys()) if sprites else 'NONE'}", flush=True)

        app_icon = _make_tray_icon_from_sprites(sprites)
        self.qapp.setWindowIcon(app_icon)

        primary = QGuiApplication.primaryScreen().geometry()
        center = primary.center()
        start_mouse = QPointF(center.x(), center.y())

        def mouse_target() -> Optional[QPointF]:
            p = get_global_mouse_pos()
            if p is None:
                return None
            screen = QGuiApplication.screenAt(p.toPoint())
            if screen is None:
                screen = QGuiApplication.primaryScreen()
            g = screen.geometry()
            sprite_half = self.settings.pigeon_scale * 32 / 2
            off_x = 40
            off_y = 40
            if p.x() + off_x + sprite_half > g.right():
                off_x = -40
            if p.y() + off_y + sprite_half > g.bottom():
                off_y = -40
            return QPointF(p.x() + off_x, p.y() + off_y)

        mouse_pigeon = Pigeon(
            target_provider=mouse_target,
            name="mouse",
            speed=self.settings.walk_speed,
            peck_interval_ms=self.settings.peck_interval_ms,
            fly_duration_ms=self.settings.fly_duration_ms,
            scale=self.settings.pigeon_scale,
            body_color=QColor(120, 130, 150),
        )
        mouse_pigeon.pos = start_mouse

        # 네이티브 NSPanel 오버레이 — Qt QWidget의 occlusion 문제 회피
        ns_sprites = load_ns_sprites()
        self.overlays = NSOverlayManager([mouse_pigeon], self.settings)
        self.overlays.set_sprites(ns_sprites)
        self.overlays.show()
        self.overlays.start()

        print(f"[pigeon] NS overlays created for {len(self.overlays.panels)} screen(s)", flush=True)

        self._build_tray(app_icon)

        self.hotkey = HotkeyListener(self._emergency_quit)
        hk_ok = self.hotkey.start()
        print(f"[pigeon] global hotkey active: {hk_ok}", flush=True)
        if not hk_ok:
            print("[pigeon] WARNING: 글로벌 단축키 비활성. 시스템 설정 → 개인정보보호 → '입력 모니터링'에서 터미널/Python 허용 필요", flush=True)

        self.qapp.aboutToQuit.connect(self._cleanup)

    def _emergency_quit(self) -> None:
        QMetaObject.invokeMethod(self.qapp, "quit", Qt.ConnectionType.QueuedConnection)

    def _cleanup(self) -> None:
        if hasattr(self, "overlays"):
            try:
                self.overlays.stop()
            except Exception:
                pass
        if hasattr(self, "hotkey"):
            self.hotkey.stop()

    def _build_tray(self, icon: QIcon) -> None:
        self.tray = QSystemTrayIcon(icon, parent=self.qapp)
        self.tray.setToolTip("Pigeon Pecker")

        menu = QMenu()
        self.act_click_through = QAction("클릭 통과 (Click-through)", menu, checkable=True)
        self.act_click_through.setChecked(self.settings.click_through)
        self.act_click_through.toggled.connect(self.overlays.set_click_through)
        menu.addAction(self.act_click_through)

        menu.addSeparator()
        act_about = QAction("정보…", menu)
        act_about.triggered.connect(self._show_about)
        menu.addAction(act_about)

        act_quit = QAction("종료  (⌃⌥⌘Q)", menu)
        act_quit.triggered.connect(self.qapp.quit)
        menu.addAction(act_quit)

        self.tray.setContextMenu(menu)
        self.tray.show()

    def _show_about(self) -> None:
        QMessageBox.information(
            None,
            "Pigeon Pecker",
            "비둘기가 마우스 커서 옆에서 쪼아댑니다.\n"
            "클릭 통과를 끄면 비둘기를 클릭해 푸드덕 날릴 수 있습니다.\n"
            "강제 종료: ⌃⌥⌘Q (Control+Option+Command+Q)",
        )

    def run(self) -> int:
        return self.qapp.exec()


def main() -> int:
    return App().run()


if __name__ == "__main__":
    sys.exit(main())
