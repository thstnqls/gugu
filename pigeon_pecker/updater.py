"""GitHub Releases 기반 자동 업데이트.

흐름:
  1) 백그라운드 스레드에서 GitHub Releases API 호출 → 최신 태그 확인
  2) 현재 버전보다 새 버전이면 update_available 시그널 발사
  3) 사용자가 설치를 승인하면 zip 다운로드 → 플랫폼별 설치 스크립트 실행 → 앱 재시작

플랫폼별 설치:
  - macOS  : 새 GUGU.app 으로 /Applications/GUGU.app 교체 → 재실행
  - Windows: 새 폴더 내용으로 현재 설치 폴더 교체(배치 스크립트) → 재실행
개발 모드(PyInstaller 번들 아님)에서는 다운로드만 하고 설치는 스킵.
"""
from __future__ import annotations

import json
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
import zipfile
from pathlib import Path
from typing import Optional
from urllib.request import Request, urlopen

from PySide6.QtCore import QObject, Signal

from .__version__ import GITHUB_REPO, __version__
from .platform_support import IS_MAC, IS_WINDOWS


_UA = f"GUGU-Updater/{__version__}"
_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def _parse_version(v: str) -> tuple[int, ...]:
    v = v.lstrip("vV").split("-", 1)[0]
    out = []
    for part in v.split("."):
        try:
            out.append(int(part))
        except ValueError:
            out.append(0)
    return tuple(out)


def _is_newer(latest: str, current: str) -> bool:
    return _parse_version(latest) > _parse_version(current)


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def _bundle_root() -> Optional[Path]:
    """현재 실행 중인 번들의 루트 경로.

    - macOS .app   : /Applications/GUGU.app
    - Windows onedir: ...\\GUGU\\  (GUGU.exe 가 있는 폴더)
    """
    if not _is_frozen():
        return None
    exe = Path(sys.executable).resolve()
    if IS_MAC:
        for p in exe.parents:
            if p.suffix == ".app":
                return p
        return None
    return exe.parent


class Updater(QObject):
    update_available = Signal(str)
    check_failed = Signal(str)
    download_progress = Signal(int)
    install_ready = Signal(str)
    install_failed = Signal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._latest_version: Optional[str] = None
        self._download_url: Optional[str] = None
        self._downloaded_zip: Optional[Path] = None
        self._lock = threading.Lock()

    @property
    def current_version(self) -> str:
        return __version__

    @property
    def latest_version(self) -> Optional[str]:
        return self._latest_version

    def check_async(self) -> None:
        threading.Thread(target=self._check, daemon=True, name="updater-check").start()

    def _check(self) -> None:
        try:
            req = Request(_API_URL, headers={"User-Agent": _UA, "Accept": "application/vnd.github+json"})
            ctx = ssl.create_default_context()
            with urlopen(req, timeout=10, context=ctx) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            self.check_failed.emit(f"업데이트 확인 실패: {exc}")
            return

        tag = data.get("tag_name") or ""
        if not tag:
            self.check_failed.emit("릴리스 정보를 찾을 수 없습니다.")
            return

        if not _is_newer(tag, __version__):
            self._latest_version = tag
            return

        asset_url = self._pick_asset(data.get("assets") or [])
        if not asset_url:
            self.check_failed.emit(f"{tag} 에 현재 OS용 자산이 없습니다.")
            return

        with self._lock:
            self._latest_version = tag
            self._download_url = asset_url

        self.update_available.emit(tag)

    def _pick_asset(self, assets: list[dict]) -> Optional[str]:
        if IS_MAC:
            needles = ("mac", "darwin", "osx")
        elif IS_WINDOWS:
            needles = ("win", "windows")
        else:
            needles = ("linux",)
        for a in assets:
            name = (a.get("name") or "").lower()
            if any(n in name for n in needles) and name.endswith(".zip"):
                return a.get("browser_download_url")
        return None

    def download_and_install_async(self) -> None:
        threading.Thread(target=self._download_and_install, daemon=True, name="updater-install").start()

    def _download_and_install(self) -> None:
        with self._lock:
            url = self._download_url
            version = self._latest_version
        if not url or not version:
            self.install_failed.emit("다운로드 URL이 없습니다. 먼저 업데이트를 확인하세요.")
            return

        try:
            zip_path = self._download(url, version)
        except Exception as exc:
            self.install_failed.emit(f"다운로드 실패: {exc}")
            return

        self._downloaded_zip = zip_path

        if not _is_frozen():
            self.install_ready.emit(str(zip_path))
            return

        try:
            self._install(zip_path)
        except Exception as exc:
            self.install_failed.emit(f"설치 실패: {exc}")

    def _download(self, url: str, version: str) -> Path:
        tmpdir = Path(tempfile.mkdtemp(prefix="gugu-update-"))
        target = tmpdir / f"gugu-{version}.zip"
        req = Request(url, headers={"User-Agent": _UA})
        ctx = ssl.create_default_context()
        with urlopen(req, timeout=60, context=ctx) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            last_pct = -1
            with open(target, "wb") as f:
                while True:
                    chunk = resp.read(64 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if total > 0:
                        pct = int(done * 100 / total)
                        if pct != last_pct:
                            last_pct = pct
                            self.download_progress.emit(pct)
        return target

    def _install(self, zip_path: Path) -> None:
        root = _bundle_root()
        if root is None:
            raise RuntimeError("번들 루트를 찾을 수 없습니다.")

        extract_dir = zip_path.parent / "extracted"
        extract_dir.mkdir(exist_ok=True)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract_dir)

        if IS_MAC:
            self._install_mac(extract_dir, root)
        elif IS_WINDOWS:
            self._install_windows(extract_dir, root)
        else:
            raise RuntimeError("지원하지 않는 플랫폼입니다.")

    def _install_mac(self, extract_dir: Path, current_app: Path) -> None:
        new_app = next((p for p in extract_dir.rglob("GUGU.app") if p.is_dir()), None)
        if new_app is None:
            raise RuntimeError("새 GUGU.app 을 찾을 수 없습니다.")

        target = current_app
        script = extract_dir / "install.sh"
        script.write_text(
            "#!/bin/bash\n"
            "set -e\n"
            "sleep 1\n"
            f'rm -rf "{target}"\n'
            f'cp -R "{new_app}" "{target}"\n'
            f'xattr -dr com.apple.quarantine "{target}" 2>/dev/null || true\n'
            f'open "{target}"\n'
        )
        script.chmod(0o755)

        subprocess.Popen(
            ["/bin/bash", str(script)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        os._exit(0)

    def _install_windows(self, extract_dir: Path, current_root: Path) -> None:
        new_root = next((p for p in extract_dir.iterdir() if p.is_dir() and (p / "GUGU.exe").exists()), None)
        if new_root is None:
            for p in extract_dir.rglob("GUGU.exe"):
                new_root = p.parent
                break
        if new_root is None:
            raise RuntimeError("새 GUGU.exe 를 찾을 수 없습니다.")

        target_exe = current_root / "GUGU.exe"
        bat = extract_dir / "install.bat"
        bat.write_text(
            "@echo off\r\n"
            "timeout /t 2 /nobreak >nul\r\n"
            f'xcopy /E /I /Y /Q "{new_root}\\*" "{current_root}\\" >nul\r\n'
            f'start "" "{target_exe}"\r\n'
            'del "%~f0"\r\n',
            encoding="cp949",
            errors="replace",
        )

        subprocess.Popen(
            ["cmd", "/c", str(bat)],
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "DETACHED_PROCESS", 0),
            close_fds=True,
        )
        os._exit(0)
