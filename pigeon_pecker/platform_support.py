"""실행 중인 OS 판별 — 플랫폼별 분기에 사용."""
from __future__ import annotations

import sys

IS_MAC = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")
