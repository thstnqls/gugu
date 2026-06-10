"""PyInstaller 진입점. 패키지를 모듈로 실행하지 않고 직접 main() 호출."""
from pigeon_pecker.main import main
import sys

if __name__ == "__main__":
    sys.exit(main())
