# Development Guide

## 버전 관리

프로그램 버전의 단일 원천은 `app/version.py`입니다. `APP_NAME`, `__version__`, `VERSION_LABEL`, `get_display_name()`을 정의하며, UI 제목과 `--version` 출력은 이 값을 가져와 사용합니다. 다른 Python 파일에 버전 문자열을 직접 중복 작성하지 않습니다.

현재 프로그램 버전은 `0.0.03`, 사용자 표시 버전은 `v0.0.03`입니다. 초기 개발 단계에서는 `v0.0.01`, `v0.0.02` … `v0.0.10`처럼 증가시키고, 큰 기능 단계가 완성되면 `v0.1.0`, `v0.2.0`처럼 올릴 수 있습니다.

프로그램 버전과 프로젝트 파일의 `format_version`은 서로 독립적입니다. 앱 버전은 `0.0.03`을 유지하고 최신 파일 형식은 `format_version = 5`입니다. 형식 5는 Resource Composition, Layer, Track과 Keyframe을 저장합니다. 형식 1~4 파일은 기존 데이터를 유지하고 `resource_compositions = []`를 보완하며, 이후 사용자가 저장할 때 형식 5로 기록합니다. 미래 형식은 거부합니다.

## 구조와 주요 클래스

- `app.models.Project`: 캔버스, FPS, 레이어, 프레임을 소유하는 UI 독립 모델입니다.
- `app.models.Layer`: 모든 프레임에서 공유하는 레이어 메타데이터입니다.
- `app.models.Frame`: 레이어 ID별 NumPy RGBA 픽셀 버퍼를 보관합니다.
- `SourceAsset`: 외부 파일과 독립된 원본 RGBA 배열, 표시 이름, 피벗과 참고 경로를 보관합니다.
- `TransformEmitter` / `EffectInstance`: 생성 설정과 방출 시점·분포 위치를 분리합니다.
- `AnimationClipAsset`: 외부 파일과 독립된 RGBA 프레임, FPS, Pivot, 재생 모드를 보관합니다.
- `ParticleEmitter` / `ParticleInstance`: Clip 연결·범위 설정과 Seed로 확정된 개별 입자 값을 분리합니다.
- `ResourceComposition` / `CompositionLayer`: 독립 캔버스와 시간축, 원본 참조, 레이어 범위·피벗·표시 상태를 보관합니다.
- `AnimationTrack` / `Keyframe`: 등록된 속성의 기본값과 프레임별 값·easing을 보관합니다.
- `resource_composition_render_service`: Composition 프레임 선택, Transform, opacity, source-over 합성과 revision 캐시를 담당합니다.
- `app.ui.resource_editor_v2.ResourceEditorController`: 모델 복사 없이 현재 Asset/Composition/Layer ID와 프레임 선택을 관리합니다.
- `ResourceEditorMode`: EMPTY, ASSET_INSPECT, COMPOSITION, LAYER_EDIT 상태에 따라 서로 다른 Canvas·Inspector·Timeline을 표시합니다.
- `CompositionCanvas`: Layer bounding polygon, 직접 선택과 실제 Move/Rotate/Scale/Pivot Handle hit-test를 담당합니다.
- `particle_render_service`: 입자 생성, Clip 선택, 이동·회전·불투명도 합성과 원자적 Bake를 담당합니다.
- `particle_preview_service`: 250ms debounce, worker snapshot, 최신 revision 검증을 담당합니다.
- `source_import_service`: Pillow로 PNG를 검증하고 RGBA 원본 복사본을 만듭니다.
- `emitter_service`: distribution, lifetime, easing과 deterministic instance를 계산합니다.
- `effect_render_service`: 최근접 역매핑, source-over 합성, Generated Layer 원자적 교체를 담당합니다.
- `app.services.project_io`: JSON 저장/검증/불러오기를 담당합니다. 쓰기는 임시 파일 교체 방식으로 수행합니다.
- `app.services.export_service`: 모델이 합성한 RGBA 프레임을 Pillow로 PNG 저장합니다.
- `app.ui.MainWindow`: 사용자 동작을 모델과 서비스에 연결합니다.
- `app.ui.CanvasWidget`: 현재 합성 프레임을 정수 배율로 표시합니다.
- `TimelineWidget`: 레이어 행과 프레임 열을 표시하고 선택·편집 요청을 시그널로 전달합니다.
- `NewProjectDialog`: 새 프로젝트 입력과 범위 제한을 담당하고 `NewProjectSettings`를 반환합니다.
- `ProjectSettingsDialog`: 일반 설정, 캔버스 변경 방식과 읽기 전용 메타데이터를 표시합니다.
- `KeyboardShortcutsDialog`: 네 명령의 키 입력과 충돌 검증 UI를 제공합니다.
- `ShortcutSettingsService`: 프로젝트와 분리된 QSettings 단축키를 안전하게 저장하고 불러옵니다.
- `PlaybackShortcutController`: 재생 키 입력을 포커스·모달 상태에 맞춰 단일 경로로 처리합니다.
- `canvas_resize_service`: 모든 프레임·레이어를 원자적으로 resize 또는 scale합니다.
- `sample_project_service`: 일반 모델만 사용해 Playback Test Project를 생성합니다.

## 데이터 흐름

Resource Editor의 Assets 영역은 `Project.source_assets` 및 `Project.animation_clips`를 원본 그대로 검사합니다. Compositions 영역은 `Project.resource_compositions`를 편집하고, 전용 렌더 서비스가 현재 프레임을 계산합니다. Composition Preview와 원본 duration Timeline은 Effect 프로젝트 Frame을 수정하지 않습니다. Particle만 Composition을 공통 frame source로 소비하며 Bake 시에만 Effect Frame을 변경합니다.

V2 UI는 `app/ui/resource_editor_v2/` 아래에서 Browser, Asset Inspector, Composition Canvas, Inspector, Timeline, Dialog, Controller와 State를 분리합니다. 기존 `app/ui/resource_editor_widget.py`는 Legacy 호환 파일로 남지만 MainWindow에서 import하지 않습니다.

사용자 입력 → `MainWindow` → `Project` 변경 → 패널/캔버스 갱신 순서입니다. 저장 시 `Project.to_dict()` 결과가 `project_io`를 통해 JSON이 되고, 불러올 때는 검증을 거쳐 새 `Project`가 됩니다. PNG 내보내기는 `Project.compose_frame()`의 결과만 사용합니다.

각 `Frame`은 `layer_id → RGBA 픽셀 버퍼` 매핑을 가집니다. 통합 타임라인은 이 기존 구조를 레이어 행과 프레임 열로 투영할 뿐 저장 구조를 추가하지 않습니다. 셀 선택은 `(layer_index, frame_index)`를 `MainWindow`에 전달하며, 메인 창이 캔버스와 상태 표시를 함께 갱신합니다.

`MainWindow`의 편집 행은 저장 가능한 QSplitter로 Effect Library, 캔버스, Effect Properties를 배치하고 통합 타임라인은 아래에 유지합니다. Source 선택은 원본 썸네일만 갱신하며 프로젝트 프레임에 오버레이하지 않습니다. Generator 선택은 Properties를 채우고, Apply/Bake 요청만 서비스 렌더링 결과를 프로젝트에 확정합니다.

프레임의 `name` 필드는 기존 `.peffect.json` 호환을 위해 유지합니다. UI 프레임 번호는 저장된 이름이 아니라 `Project.frames`의 현재 인덱스에서 계산합니다. 복제본은 원본 다음에 삽입하고 픽셀 배열은 `copy()`로 분리합니다.

레이어 자동 이름은 `Project.next_layer_name()`이 사용 중이 아닌 첫 `Layer N`을 선택합니다. 사용자가 지정한 레이어 이름은 자동으로 변경하지 않습니다.

## UI와 모델 분리

`app.models`는 PySide6를 import하지 않습니다. UI 위젯은 파일 형식이나 픽셀 합성 규칙을 직접 구현하지 않습니다. 자동 생성 효과, 브러시 명령, 실행 취소가 추가될 때도 모델 또는 별도 서비스에 구현하고 UI는 명령만 전달합니다.

`MainWindow`는 `app.version.get_display_name()`으로 앱 이름과 버전을 가져옵니다. CLI는 `--version`을 먼저 처리한 뒤에만 PySide6와 `MainWindow`를 import하므로 버전 조회는 GUI를 생성하지 않습니다.

새 기능은 현재의 UI·모델·서비스 경계를 유지하면서 해당 계층에 작게 추가합니다. 정상 동작하는 구조를 기능 단위 근거 없이 교체하거나, UI 위젯에 저장·합성 로직을 넣지 않습니다.

## 기능 추가 위치

- 브러시/지우개 및 히스토리: `app/services/`에 픽셀 편집 명령 계층 추가
- 캔버스 입력: `CanvasWidget`의 마우스 이벤트에서 편집 명령 호출
- 레이어 재정렬/속성: `Project` 연산과 `TimelineWidget` UI 확장
- 통합 타임라인 고급 편집: 현재 `TimelineWidget`에 드래그, 다중 선택, 셀 복사 기능을 단계적으로 추가
- 자동 이펙트 확장: 현재 emitter/render 서비스에 distribution 또는 deformation 전략을 추가
- 새 파일 형식: `project_io`에 `format_version` 마이그레이션 추가
- 내보내기 대상: `export_service` 주변에 형식별 서비스 추가

## 픽셀 렌더링 규칙

- 좌표와 캔버스 크기는 정수입니다.
- RGBA 버퍼는 `(height, width, 4)` 형태의 `uint8` NumPy 배열입니다.
- 확대/축소는 1–32의 정수 배율이며 부드러운 변환을 끕니다.
- 투명 영역은 UI에서 체커보드로 표현하되 모델 픽셀에는 포함하지 않습니다.
- 레이어는 목록 앞에서 뒤 순서로 합성하고 가시성과 불투명도를 반영합니다.
- Source 변형은 목적지 사각형의 역방향 projective mapping과 정수 반올림으로 원본 픽셀을 최근접 샘플링합니다.
- Bilinear/Bicubic은 사용하지 않습니다. Opacity는 원본 alpha에 곱하고 겹침은 straight-alpha source-over로 합성합니다.
- Pseudo-3D는 실제 3D 메시가 아니라 네 모서리의 배치를 바꾸는 픽셀용 사각형 변형입니다.

## Effect 생성 파이프라인

`SourceAsset → TransformEmitterSettings → EffectInstance 목록 → lifetime transform → RGBA frame buffers → Generated Layer` 순서입니다. Source 원본이나 이전 생성 결과를 다음 생성의 입력으로 사용하지 않습니다. 먼저 전체 출력 버퍼 계산을 끝낸 뒤 필요한 프레임을 확장하고 해당 생성기 레이어만 교체합니다. 렌더 계산이 실패하면 이전 settings와 Generated Layer를 유지합니다.

현재 실제 distribution은 Point, Line, Circle이며 Circle의 시작/끝 각도로 호 배치도 가능합니다. Position, Rotation Z, signed Scale X/Y, Horizontal/Vertical Tilt, Perspective, Opacity에 Linear/Ease In/Ease Out 공통 easing을 적용합니다. Seed와 deformation `none` 확장 지점은 저장하지만 랜덤 변화 UI와 Bend/Twist/Mesh 렌더링은 아직 구현하지 않습니다.

## Draft와 Live Preview

`PreviewManager`는 Generator별 `GeneratorDraft`와 `PreviewSession`을 메모리에 유지합니다. Generator 선택 시 committed settings를 `deepcopy`한 Draft를 만들며 Properties 변경은 Draft revision만 증가시킵니다. 실제 Generator settings, Generated Layer, 프로젝트 frame/layer 목록과 dirty 상태는 Apply 전까지 변경하지 않습니다.

Auto Preview는 250ms single-shot QTimer로 연속 입력을 마지막 요청 하나로 합칩니다. QRunnable worker에는 캔버스 크기, 기존 프레임 수, Source RGBA 복사본, Draft settings와 revision만 전달합니다. worker는 thread-safe 결과 큐에만 기록하고 메인 스레드 QTimer가 결과를 수거합니다. 완료 revision이 현재 Draft와 다르거나 프로젝트 context가 교체된 경우 폐기합니다. 종료 시 manager를 닫아 후속 결과가 UI에 접근하지 못하게 합니다.

Canvas는 선택 Generator의 실제 Generated Layer만 Preview buffer로 표시 단계에서 대체합니다. 다른 레이어는 실제 프로젝트 배열을 읽기 전용으로 합성하며 Preview가 더 길면 가상 프레임을, 더 짧으면 Preview frame count만 탐색합니다. Save와 Export는 계속 실제 Project만 사용합니다.

Apply는 동일 revision의 정상 Preview가 있으면 buffer를 재사용하고, 없으면 현재 Draft snapshot을 최종 렌더링합니다. 전체 buffer 검증 후 전용 Generated Layer를 교체하고 committed settings를 갱신합니다. Revert는 Draft와 Preview만 폐기합니다. Generator별 Draft는 같은 프로그램 실행 중 선택을 바꿔도 유지합니다.

## 편집기 단축키

QSettings 단축키 값은 명령당 최대 두 PortableText 문자열 목록입니다. 기존 단일 문자열은 `[문자열]`로 마이그레이션하며 기존 값은 초기화하지 않습니다. Previous Frame 기본값은 `Left`, `<(Shift+,)`, Next Frame은 `Right`, `>(Shift+.)`입니다. `FrameShortcutController` 하나만 키 입력을 처리하고 QAction/keyPressEvent와 중복 경로를 만들지 않습니다.

프레임 이동 컨트롤러는 Canvas와 일반 Timeline 셀에서는 허용하지만 텍스트·숫자·단축키 입력, 일반 item view/list 탐색, scrollbar, menu popup과 modal dialog에서는 차단합니다. 이동 전 재생을 정지하고 범위 끝에서 clamp합니다. Preview 활성 중에는 Preview frame index를 이동합니다.

## Localization

`LocalizationService`가 중앙 Python dictionary catalog와 영어 fallback을 제공합니다. 시스템 locale이 한국어면 `ko`, 그 외에는 `en`이 기본이며 `ui/language` QSettings 사용자 값이 우선합니다. `language_changed` 하나로 MainWindow, Effect Library/Properties, Timeline과 주요 대화상자가 즉시 retranslate됩니다. 프로젝트·Source·Generator·Layer 등 사용자 데이터 이름은 언어 전환으로 변경하지 않습니다.

## 새 프로젝트 검증

`NewProjectDialog`는 이름 앞뒤 공백을 제거하고 빈 이름일 때 생성 버튼을 비활성화합니다. `QSpinBox` 범위로 잘못된 정수 입력을 차단합니다. 캔버스는 모델의 기존 제한인 `1–1024`, FPS는 `1–120`을 사용합니다. 대화상자가 취소되면 `MainWindow.project`를 교체하지 않습니다.

## 단축키와 사용자 설정

단축키 명령, 표시 이름, 기본값의 단일 원천은 `app/shortcuts.py`입니다. 일반 편집 명령은 QAction shortcut을 사용합니다. 재생 명령만 `PlaybackShortcutController`가 관리하며 내부의 checkable QAction에는 shortcut을 지정하지 않습니다. `Animation` 메뉴에도 이 QAction을 넣지 않으므로 QAction과 QShortcut이 같은 키를 중복 처리하지 않습니다. 타임라인 버튼과 컨트롤러는 모두 내부 QAction을 거쳐 `MainWindow.set_playing()` 한 곳에서 상태를 변경합니다.

기본 문자열 `Enter`는 Qt에서 메인 키보드의 `Qt.Key_Return`과 숫자 키패드의 `Qt.Key_Enter`가 서로 다른 키로 전달되므로 두 개의 window-context QShortcut으로 명시적으로 바인딩합니다. 두 바인딩은 서로 다른 실제 키만 담당하고 같은 callback을 호출해 한 입력당 한 번만 실행됩니다. 사용자가 다른 키를 지정하면 이 두 기본 바인딩을 제거하고 사용자 키 하나만 만듭니다. 설정을 다시 적용할 때는 기존 QShortcut을 disable하고 부모에서 분리한 뒤 새 바인딩을 생성하므로 연결이 누적되지 않습니다.

컨트롤러는 활성 modal widget이나 popup이 있으면 실행하지 않습니다. 포커스가 QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox, QKeySequenceEdit, 편집 가능한 QComboBox, QAbstractButton 또는 편집 중인 QAbstractItemView 안에 있을 때도 실행하지 않습니다. 따라서 대화상자 기본 버튼, 입력 확정, 메뉴 탐색, 셀 편집이 Enter를 우선 사용하며, 캔버스나 일반 선택 상태의 타임라인에서는 재생 키가 동작합니다.

재생 상태의 단일 진실 공급원은 `MainWindow.play_timer.isActive()`입니다. `set_playing()`이 타이머, 내부 QAction checked 상태와 타임라인 버튼을 동기화하고, `_refresh_playback_status()`가 타이머 상태·현재 frame index·전체 프레임 수·project FPS를 타임라인에 전달합니다. 프로젝트/프레임/FPS 갱신과 타이머 tick도 같은 refresh 경로를 사용합니다.

`ShortcutSettingsService`는 `SOUTHPAW GAMES / Pixel Effect Maker` QSettings에 값을 저장합니다. 빈 단축키는 해당 명령의 키 입력을 비활성화하며, 중복된 비어 있지 않은 단축키는 거부합니다. 손상되거나 충돌하는 저장값은 기본값으로 복구합니다. 테스트는 임시 INI QSettings를 주입해 실제 사용자 설정을 변경하지 않습니다.

## 캔버스 크기 변경

`Resize canvas only`는 픽셀 크기를 유지하고 투명 공간 추가 또는 crop만 수행합니다. Anchor 오프셋은 각 축에서 시작 `0`, 끝 `new-old`, 중앙 `(new-old)//2`로 계산합니다. 홀수 확장 차이의 추가 픽셀은 오른쪽·아래쪽에 배치되고, 홀수 축소 차이의 추가 crop은 왼쪽·위쪽에서 발생합니다.

`Scale image and canvas`는 NumPy 정수 인덱스를 이용한 최근접 이웃만 사용합니다. Bilinear/Bicubic 보간을 사용하지 않으므로 원본에 없던 중간 RGB나 alpha 값을 만들지 않습니다.

두 변환 모두 먼저 모든 프레임과 레이어 배열의 shape와 `uint8` dtype을 검증하고, 새 배열 전체를 메모리에서 완성한 후 각 프레임과 프로젝트 크기를 교체합니다. 변환 중 검증 또는 메모리 생성이 실패하면 기존 프로젝트에 부분 변경이 남지 않습니다.

## Project Settings

`File > Project Settings…`는 이름, FPS, Loop, 캔버스 크기, resize mode와 anchor를 편집합니다. 저장 경로, 프레임·레이어 수, 형식 버전, 앱 버전은 작은 읽기 전용 영역에 표시합니다. Apply는 창을 유지하고 OK는 적용 후 닫으며, 아직 적용하지 않은 값은 Cancel 시 폐기합니다. 축소, Scale, 또는 dirty 픽셀 데이터의 크기 변경은 되돌릴 수 없음 경고를 거칩니다.

## Playback Test Project

`sample_project_service.create_playback_test_project()`는 64×64, 12 FPS, loop 활성, 1레이어, 8프레임의 일반 `Project`를 반환합니다. 각 프레임은 서로 독립된 배열에 8×8 불투명 사각형을 정수 좌표로 이동시킵니다. 특수 저장 필드를 사용하지 않으며 기존 JSON 및 PNG 서비스로 처리합니다.

## QSettings 마이그레이션

단축키 서비스는 명령별 키 존재 여부를 확인합니다. 기존 세 단축키가 저장되어 있고 새 `play_stop_animation` 키만 없는 경우 기존 값은 유지하고 `Enter` 기본값만 보완해 저장합니다. 충돌하거나 손상된 설정만 전체 기본값으로 안전하게 복구합니다.

## Editor Interaction

입력 동기화, 공통 Timeline 폭, 메뉴 역할, Tooltip, Undo Command와 축 기즈모의 구현 규칙은 [EDITOR_INTERACTION.md](EDITOR_INTERACTION.md)를 따른다. Undo Command는 전체 Project나 RGBA Asset을 복제하지 않고 변경 대상의 작은 값 또는 프레임·레이어 작업에 필요한 항목만 보관한다.

`TimelineScrubController`는 Effect와 Resource Composition 테이블 viewport의 실제 mouse press/move/release를 공통 처리한다. 열이 바뀔 때만 프레임을 선택하며 양쪽 바깥 이동은 첫/마지막 열로 clamp한다. 스크러빙 시작 신호는 재생만 정지하고 모델이나 Undo Stack을 변경하지 않는다.

일반 앱 진입은 MainWindow를 표시하기 전에 `StartupDialog`에서 새 프로젝트 설정 또는 기존 프로젝트 열기를 결정한다. `--version`, `--check`, 명시적 프로젝트 경로 및 테스트에서 직접 생성하는 MainWindow는 이 대화상자를 거치지 않는다. Resource Editor의 빈 시작 상태는 자동 Popup이 아니라 반복 노출 문제가 없는 Empty State Panel로 제공한다.
