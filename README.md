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


라이선스
--------
스프라이트:
* pigeon_walking-Sheet.png, pigeon_eat-Sheet.png — Vlad Negară (itch.io)
  https://vlad-negara.itch.io/pigeon
* pigeon_fiy-Sheet.png — kangjung (itch.io)
  https://kangjung.itch.io/pigeon-pixel
