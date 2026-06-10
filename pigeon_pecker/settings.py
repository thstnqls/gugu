from dataclasses import dataclass


@dataclass
class Settings:
    click_through: bool = True  # 기본 ON — 안전. 클릭 푸드덕 원하면 트레이에서 OFF
    walk_speed: float = 220.0
    peck_interval_ms: int = 600
    pigeon_scale: int = 2
    fly_duration_ms: int = 1200
