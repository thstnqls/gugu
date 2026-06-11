from dataclasses import dataclass

from PySide6.QtCore import QSettings


# 속도 프리셋: (key, 표시 이름, walk_speed, peck_interval_ms)
SPEED_PRESETS = [
    ("slow", "느림", 120.0, 900),
    ("normal", "보통", 220.0, 600),
    ("fast", "빠름", 380.0, 400),
    ("very_fast", "매우 빠름", 600.0, 280),
]

DEFAULT_SPEED_KEY = "normal"


def preset_by_key(key: str) -> tuple[str, str, float, int]:
    for p in SPEED_PRESETS:
        if p[0] == key:
            return p
    return SPEED_PRESETS[1]


@dataclass
class Settings:
    click_through: bool = True  # 기본 ON — 안전. 클릭 푸드덕 원하면 트레이에서 OFF
    walk_speed: float = 220.0
    peck_interval_ms: int = 600
    pigeon_scale: int = 2
    fly_duration_ms: int = 1200
    speed_key: str = DEFAULT_SPEED_KEY

    def __post_init__(self) -> None:
        self._qs = QSettings("GUGU", "GUGU")
        saved_key = self._qs.value("speed_key", DEFAULT_SPEED_KEY, type=str)
        self.apply_speed_preset(saved_key, persist=False)
        saved_ct = self._qs.value("click_through", self.click_through, type=bool)
        self.click_through = bool(saved_ct)

    def apply_speed_preset(self, key: str, persist: bool = True) -> None:
        _, _, speed, peck = preset_by_key(key)
        self.speed_key = key
        self.walk_speed = speed
        self.peck_interval_ms = peck
        if persist and hasattr(self, "_qs"):
            self._qs.setValue("speed_key", key)
            self._qs.sync()

    def save_click_through(self, value: bool) -> None:
        self.click_through = bool(value)
        if hasattr(self, "_qs"):
            self._qs.setValue("click_through", self.click_through)
            self._qs.sync()
