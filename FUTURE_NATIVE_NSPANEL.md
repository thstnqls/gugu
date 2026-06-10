# [미해결 이슈] 다른 앱 클릭 시 비둘기 사라짐

## 증상
- 비둘기 오버레이가 떠있는 상태에서 다른 앱(Cursor, Chrome 등)을 클릭하면 비둘기가 화면에서 사라짐
- 마우스를 움직여도 안 돌아옴
- 진단 로그상 윈도우 자체는 살아있음 (`visible=True`, `level=3`, `alpha=0.99`, `onActiveSpace=True`)
- 그런데 `occlusionState raw=0x2000` — macOS가 "그릴 수 없음" 상태로 마킹 → paint 호출 무시

## 시도했고 안 통한 것들
1. `NSScreenSaverWindowLevel(1000)` 설정 — visible은 됐지만 occlusion 해결 안 됨
2. `NSWindowCollectionBehavior` 모든 플래그 (CanJoinAllSpaces, Stationary, Auxiliary, CanJoinAllApplications, Transient, FullScreenAuxiliary, IgnoresCycle) — 안 통함
3. `CGShieldingWindowLevel(2147483628)` — 메뉴바도 가렸는데도 occlusion 해결 안 됨
4. `setAlphaValue:0.99` (occlusion 우회 트릭) — 안 통함
5. `update()` → `repaint()` 강제 즉시 그리기 — 안 통함
6. `NSWindowStyleMaskNonactivatingPanel` setStyleMask 추가 — 안 통함

## 원인 추정
**Qt가 만든 NSPanel(QNSPanel)은 일반 NSPanel과 다르게 동작.** Qt 자체의 윈도우 매니지먼트가 macOS occlusion 신호에 반응해서 paint 사이클을 멈춤. NSPanel 마스크/레벨/CollectionBehavior를 외부에서 바꿔도 Qt 내부 로직이 우선시됨.

## A 방안: Qt 버리고 네이티브 NSPanel로 오버레이 재작성

### 핵심 아이디어
- **`NSPanel` 직접 생성** + `NSWindowStyleMaskNonactivatingPanel`
- → 클릭/포커스 사이클에서 완전히 제외 → macOS occlusion 대상 자체에서 빠짐
- 이게 Bartender, Magnet, Rectangle, Hidden Bar, Stickies, Sticky Notes 같은
  메뉴바/오버레이 유틸이 항상 떠있는 원리

### 구조 변경
```
변경 없음 (Qt 유지):
- pigeon_pecker/main.py        — 진입점, 트레이, 핫키
- pigeon_pecker/pigeon.py      — 상태머신 + 그리기 좌표 계산
- pigeon_pecker/sprites.py     — 스프라이트 로드
- pigeon_pecker/hotkey.py      — ⌃⌥⌘Q
- pigeon_pecker/trackers/      — 마우스 위치
- pigeon_pecker/settings.py
- pigeon_pecker/focus_keeper.py

교체 (Qt → 네이티브):
- pigeon_pecker/overlay.py
  └ QWidget 기반 ScreenOverlay/OverlayManager
  → NSPanel + NSView 기반으로 재작성
```

### 핵심 구현 포인트

```python
import objc
from AppKit import (
    NSPanel, NSView, NSColor, NSBezierPath,
    NSWindowStyleMaskNonactivatingPanel,
    NSWindowStyleMaskBorderless,
    NSBackingStoreBuffered,
    NSFloatingWindowLevel,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorStationary,
    NSWindowCollectionBehaviorFullScreenAuxiliary,
    NSMakeRect,
)
from Foundation import NSObject, NSTimer

class PigeonView(NSView):
    def initWithFrame_(self, frame):
        self = super().initWithFrame_(frame)
        self._pigeons = []
        self._sprites = None
        return self

    def isOpaque(self):
        return False

    def drawRect_(self, rect):
        # 1. 배경 클리어
        NSColor.clearColor().set()
        NSBezierPath.fillRect_(rect)
        # 2. 각 비둘기 그리기 (현재 _paint_sprite와 동일 로직)
        #    macOS 좌표계는 좌하단=원점 → y 뒤집어야 함
        for p in self._pigeons:
            ...  # NSImage.drawAtPoint or NSBezierPath

def create_overlay_panel(screen_rect):
    style = NSWindowStyleMaskNonactivatingPanel | NSWindowStyleMaskBorderless
    panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(*screen_rect), style, NSBackingStoreBuffered, False,
    )
    panel.setLevel_(NSFloatingWindowLevel)
    panel.setBackgroundColor_(NSColor.clearColor())
    panel.setOpaque_(False)
    panel.setHasShadow_(False)
    panel.setIgnoresMouseEvents_(True)  # click-through 기본
    panel.setCollectionBehavior_(
        NSWindowCollectionBehaviorCanJoinAllSpaces
        | NSWindowCollectionBehaviorStationary
        | NSWindowCollectionBehaviorFullScreenAuxiliary
    )
    view = PigeonView.alloc().initWithFrame_(panel.contentView().frame())
    panel.setContentView_(view)
    panel.orderFrontRegardless()  # makeKeyAndOrderFront 아님 — 활성화 안 시킴
    return panel, view
```

### 마이그레이션 작업 양
- `overlay.py` 전체 재작성 (~150줄)
- `pigeon.py`의 paint 좌표를 NSView 좌표계(좌하단 원점)로 변환
- QPixmap → NSImage 변환 (스프라이트 로드 시 한 번)
- 60fps 타이머: `QTimer` → `NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_`
- 마우스 클릭(푸드덕)이 필요하면 `setIgnoresMouseEvents_:False`로 토글
  - 단 클릭 시 활성화는 nonactivating mask가 막아줌

### 예상 작업 시간
1-2시간 (디버깅 포함)

### 주의사항
- pyobjc의 NSTimer 콜백은 selector 문자열 매칭 (`"tick:"`) — 메서드명 정확히
- `objc.IBOutlet`, `objc.signature` 같은 데코레이터 필요할 수 있음
- 멀티모니터 대응: 화면별로 NSPanel 1개씩 만들고 비둘기는 글로벌 좌표로 관리 (현 구조와 동일)
- ⌃⌥⌘Q 핫키, 트레이 메뉴는 그대로 Qt 사용 가능 (메인 이벤트 루프 충돌 없음 — Qt가 NSRunLoop 위에서 돌기 때문)

## 임시 대응 (현재 코드 상태)
- 비둘기가 사라지면 마우스를 화면 가장자리로 휙 움직이거나 다른 화면으로 옮기면 가끔 재등장
- 가장 확실한 우회: 트레이 메뉴 → "클릭 통과" 토글하면 hide/show 사이클로 재표시됨
- 그래도 안 보이면 ⌃⌥⌘Q로 종료 후 재실행
