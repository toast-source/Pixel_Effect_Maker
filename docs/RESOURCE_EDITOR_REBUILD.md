# Resource Editor V2 재건축 감사

## 작업 전 상태

- 앱 버전: `0.0.03`
- 프로젝트 형식: `FORMAT_VERSION = 5`
- 기준 자동 테스트: `162 passed`
- 작업 트리: 장기간 누적된 tracked modified 및 untracked 파일이 있으며 모두 보존한다.

## 기존 UI의 확인된 구조적 문제

기존 `resource_editor_widget.py` 한 클래스가 에셋 검사, Composition 생성, Layer Inspector, Property Stack, 두 종류의 Timeline, 재생과 기즈모 상태를 동시에 보유했다. Asset과 Composition이 같은 `QTableWidget`, Pivot 입력과 재생 타이머를 공유하고, 상태에 맞지 않는 위젯도 비활성 상태로 남았다. Canvas는 선택 경계나 실제 Handle hit-test 없이 선택 레이어가 존재하면 빈 영역 Drag도 Transform으로 해석했다. UI 테스트도 내부 메서드를 직접 호출해 실제 클릭 흐름을 보장하지 못했다.

## 구조 분류

### REUSE

- `SourceAsset`, `AnimationClipAsset`
- `ResourceComposition`, `CompositionLayer`, `AnimationTrack`, `Keyframe`
- PNG/GIF/Aseprite Import와 Reimport 서비스
- Resource Composition Renderer와 최근접 Transform 합성 코어
- Particle Renderer, Bake, PNG Sequence Export
- 프로젝트 저장과 v1~v5 마이그레이션
- `LocalizationService`, 단축키 Controller, Focus-wheel 입력 위젯

### ADAPT

- Particle의 Composition 시간 매핑: particle age를 Effect Project FPS 기준 초로 변환한다.
- `MainWindow`: 기본 Resource Workspace를 V2로 교체하고 기존 signal 계약을 연결한다.
- Property Registry: V2 검색 Dialog와 Inspector가 기존 네 Composition 속성만 사용한다.
- 기존 Canvas 좌표/기즈모 수학: 모델 값과 최근접 규칙은 재사용하되 실제 Handle hit-test를 추가한다.

### REPLACE

- Resource Editor 메인 화면
- 명시적 편집기 상태와 선택 Controller
- Asset Preview와 Composition Timeline 공유 구조
- Composition Canvas의 레이어 직접 선택, 선택 경계와 기즈모 입력
- 상태별 Asset/Composition/Layer Inspector

### LEGACY ONLY

- 기존 `app/ui/resource_editor_widget.py` 클래스
- Transform Clip Generator와 기존 Generated Animation Clip 제작 흐름

### REMOVE FROM ACTIVE UI

- 새 프로젝트에서 Transform Generator 생성 버튼
- Asset 검사 상태의 Composition 기즈모·Timeline·Particle 생성 버튼
- 일반 메뉴의 Legacy Resource Editor 접근 경로

## V2 상태 모델

```text
EMPTY → ASSET_INSPECT → LAYER_EDIT
              ↘ COMPOSITION → LAYER_EDIT
```

- `EMPTY`: Import 안내만 표시한다.
- `ASSET_INSPECT`: 원본 Preview/정보/Reimport/Create Resource만 표시한다.
- `COMPOSITION`: Composition Canvas/Inspector/Timeline을 표시하고 Layer UI는 숨긴다.
- `LAYER_EDIT`: 선택 경계, Handle 기즈모, Layer Inspector, Property와 빠른 회전을 표시한다.

Project 모델이 유일한 데이터 원천이다. Controller는 ID와 현재 프레임 같은 선택 상태만 가지며 Drag 시작 전 값만 Canvas의 transient state로 둔다.

## 핵심 사용자 흐름

```text
PNG 선택
→ Create Resource from This Asset
→ 원본 이름·크기 기반 Dialog 확인
→ Create
→ Composition과 Layer 자동 생성·선택
→ Full Rotation
→ Enter 재생
→ Use This Resource in Effect
```

## Legacy 처리와 제한

Legacy 모델과 기존 UI 파일은 데이터·테스트 호환을 위해 삭제하지 않는다. MainWindow는 V2만 사용한다. 자동 Legacy 변환, Composition 중첩, Graph Editor, Keyframe Drag와 다중 선택은 이번 범위가 아니다.

## V2 레이아웃 안정화

- Asset List에 테스트 호환용으로 넣었던 숨김·빈 `QListWidgetItem`을 완전히 제거했다. 목록 행 수는 실제 Asset 수와 항상 같다.
- Position/Rotation/Scale/Opacity의 단일 가로 행을 Property Card로 교체했다. Card는 제목·삭제 헤더, X/Y 또는 값 Form, easing·Keyframe Footer를 세로로 배치한다.
- Layer Inspector는 가로 Scroll을 사용하지 않고 content 폭을 viewport에 동기화한다. 기즈모 버튼은 2×2 Grid이며 `Use This Resource in Effect`은 viewport 폭을 채운다.
- Horizontal Splitter는 Asset Browser 180~320px, Canvas 최소 320px, Inspector 최소 300px을 보장한다. Vertical Splitter에서 Timeline 기본 높이는 약 190px이며 Asset Inspect 상태에서는 완전히 숨긴다.
- Splitter 위치는 `ui/resource_editor_v2_horizontal_splitter`, `ui/resource_editor_v2_vertical_splitter`에 별도로 저장하며 잘못된 값은 비례 기본값으로 복구한다.
- 기존 선택 polygon이 전체 Asset 폭·높이를 사용하던 것을 불투명 픽셀의 alpha bounds로 변경했다. Animated Asset은 안정적인 전체 프레임 union bounds를 사용하고 완전 투명 Asset은 전체 크기로 fallback한다. Renderer, Pivot과 원본 픽셀은 변경하지 않는다.

오프스크린 테스트는 1024×720, 1280×800, 1600×900의 한국어·영어 조합에서 Property Card 내부 위젯 geometry와 가로 Scroll 범위를 확인한다. 실제 Windows DPI 100/125/150%는 수동 확인 대상이다.

## V2 회귀 복구 정책

- Resource Editor 루트와 Asset List·Preview·Composition Canvas는 하나의 Drop 필터를 공유한다. Local URL에서 `.png`, `.gif`, `.ase`, `.aseprite`를 대소문자 구분 없이 추려 기존 `MainWindow.import_resources()`에 순서대로 전달한다.
- Controller가 선택의 단일 원천이다. Composition별 마지막 Layer ID, Frame, Gizmo Mode는 UI 세션에만 보관하고 프로젝트 파일에는 기록하지 않는다.
- Asset 선택이나 Workspace 전환은 Composition 모델을 변경하지 않는다. 같은 Resource 재클릭도 명시적 선택 요청으로 처리하며 `refresh()`는 유효한 선택을 복원한다.
- 새 Resource의 총 길이는 정수 `frame_count`가 내부 기준이다. Dialog에는 Length 한 행만 표시하고 Frames 모드는 FPS 변경 시 frame count, Seconds 모드는 초 길이를 유지한다.

## 기본 상호작용 안정화

- Resource 수치, Keyframe, Full Rotation, Layer/Asset/Output Pivot, Layer 메타데이터·가시성과 기즈모 Drag를 전역 Undo Stack에 연결했다.
- Move는 Free/X/Y, Scale은 균등/X/Y, Rotate는 자유 회전과 Shift 15° 스냅을 제공한다. Handle은 Canvas zoom과 무관한 화면 픽셀 크기를 사용한다.
- Effect와 Composition Timeline은 `ui/timeline_frame_width`의 20~96px 값을 공유한다.
