GUGU
====
화면에 비둘기가 마우스 커서를 따라다니며 쪼아대는 macOS 데스크탑 오버레이.


요구 사항
---------
* macOS 11 (Big Sur) 이상
* Apple Silicon Mac (M1/M2/M3/M4) — Intel Mac에서는 동작하지 않음


설치
----
1. GUGU-1.0-AppleSilicon.zip 압축 풀기 → GUGU.app
2. GUGU.app을 Applications 폴더로 드래그 (선택사항, 어디든 OK)
3. 첫 실행:
   - 그냥 더블클릭하면 "확인되지 않은 개발자" 경고가 뜸
     (Apple Developer Program 가입 안 한 앱이라 그래요)
   - 우회: GUGU.app을 우클릭 → "열기" → 다시 "열기" 누름
   - 또는 시스템 설정 → 개인정보 보호 및 보안 → "그래도 열기" 클릭
4. 한 번 허용하면 그 다음부터는 더블클릭으로 실행


사용법
------
* 실행하면 메뉴바(우측 상단)에 비둘기 아이콘이 뜸
* 마우스 커서 옆에서 비둘기가 따라다니며 멈추면 쪼아댐
* Dock에는 아이콘 없음 (메뉴바 트레이 앱)
* 다른 앱을 클릭해도 비둘기는 계속 화면에 떠 있음


종료 방법
---------
1. ⌃⌥⌘Q (Control+Option+Command+Q) — 글로벌 단축키, 어디서나 동작
   ※ 처음 실행 시 시스템 설정 → 개인정보 보호 및 보안 → "입력 모니터링"
     에서 GUGU 허용해야 단축키 동작
2. 메뉴바 비둘기 아이콘 → 종료
3. 터미널: pkill -f GUGU


설정 (메뉴바 트레이)
--------------------
* 클릭 통과 (Click-through): 기본 ON
  - ON: 비둘기 위로 마우스 클릭이 통과 → 작업 방해 없음
  - OFF: 비둘기를 클릭하면 푸드덕 날아오름


자동 업데이트
-------------
* 앱을 켤 때마다 GitHub Releases에서 최신 버전을 자동으로 확인합니다.
* 새 버전이 있으면 메뉴바 알림이 뜨고, 트레이 메뉴에 "업데이트 설치" 항목이 활성화됩니다.
* 클릭하면 자동으로 다운로드 → 설치 → 재시작됩니다. (Windows / macOS 모두 지원)


개발자: 새 버전 배포 방법
-------------------------
1. `pigeon_pecker/__version__.py` 에서 `__version__` 을 올린다. (예: `1.0.0` → `1.1.0`)
2. 커밋하고 푸시:
   ```
   git commit -am "bump: v1.1.0"
   git push
   ```
3. 태그를 푸시한다:
   ```
   git tag v1.1.0
   git push origin v1.1.0
   ```
4. GitHub Actions가 자동으로 Windows / macOS 빌드를 만들어 Releases 페이지에 첨부한다.
5. 끝. 사용자들의 앱은 다음 실행 시 알아서 업데이트를 가져온다.

※ 자산 이름 규칙: `GUGU-{버전}-Windows.zip`, `GUGU-{버전}-macOS.zip`
   (updater가 이 패턴으로 OS별 자산을 찾는다.)


라이선스
--------
스프라이트:
* pigeon_walking-Sheet.png, pigeon_eat-Sheet.png — Vlad Negară (itch.io)
  https://vlad-negara.itch.io/pigeon
* pigeon_fiy-Sheet.png — kangjung (itch.io)
  https://kangjung.itch.io/pigeon-pixel
