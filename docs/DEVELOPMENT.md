# Development Guide

## 버전 관리

프로그램 버전의 단일 원천은 `app/version.py`입니다. `APP_NAME`, `__version__`, `VERSION_LABEL`, `get_display_name()`을 정의하며, UI 제목과 `--version` 출력은 이 값을 가져와 사용합니다. 다른 Python 파일에 버전 문자열을 직접 중복 작성하지 않습니다.

현재 프로그램 버전은 `0.0.02`, 사용자 표시 버전은 `v0.0.02`입니다. 초기 개발 단계에서는 `v0.0.01`, `v0.0.02` … `v0.0.10`처럼 증가시키고, 큰 기능 단계가 완성되면 `v0.1.0`, `v0.2.0`처럼 올릴 수 있습니다.

프로그램 버전과 프로젝트 파일의 `format_version`은 서로 독립적입니다. `format_version = 1`은 `.peffect.json` 구조의 호환성 버전이며 앱 릴리즈 번호가 바뀌어도 함께 변경하지 않습니다. 파일 구조가 실제로 변경되고 마이그레이션 정책이 준비될 때만 갱신합니다.

## 구조와 주요 클래스

- `app.models.Project`: 캔버스, FPS, 레이어, 프레임을 소유하는 UI 독립 모델입니다.
- `app.models.Layer`: 모든 프레임에서 공유하는 레이어 메타데이터입니다.
- `app.models.Frame`: 레이어 ID별 NumPy RGBA 픽셀 버퍼를 보관합니다.
- `app.services.project_io`: JSON 저장/검증/불러오기를 담당합니다. 쓰기는 임시 파일 교체 방식으로 수행합니다.
- `app.services.export_service`: 모델이 합성한 RGBA 프레임을 Pillow로 PNG 저장합니다.
- `app.ui.MainWindow`: 사용자 동작을 모델과 서비스에 연결합니다.
- `app.ui.CanvasWidget`: 현재 합성 프레임을 정수 배율로 표시합니다.
- `TimelineWidget`: 레이어 행과 프레임 열을 표시하고 선택·편집 요청을 시그널로 전달합니다.
- `NewProjectDialog`: 새 프로젝트 입력과 범위 제한을 담당하고 `NewProjectSettings`를 반환합니다.
- `ProjectSettingsDialog`: 일반 설정, 캔버스 변경 방식과 읽기 전용 메타데이터를 표시합니다.
- `KeyboardShortcutsDialog`: 세 명령의 키 입력과 충돌 검증 UI를 제공합니다.
- `ShortcutSettingsService`: 프로젝트와 분리된 QSettings 단축키를 안전하게 저장하고 불러옵니다.
- `canvas_resize_service`: 모든 프레임·레이어를 원자적으로 resize 또는 scale합니다.
- `sample_project_service`: 일반 모델만 사용해 Playback Test Project를 생성합니다.

## 데이터 흐름

사용자 입력 → `MainWindow` → `Project` 변경 → 패널/캔버스 갱신 순서입니다. 저장 시 `Project.to_dict()` 결과가 `project_io`를 통해 JSON이 되고, 불러올 때는 검증을 거쳐 새 `Project`가 됩니다. PNG 내보내기는 `Project.compose_frame()`의 결과만 사용합니다.

각 `Frame`은 `layer_id → RGBA 픽셀 버퍼` 매핑을 가집니다. 통합 타임라인은 이 기존 구조를 레이어 행과 프레임 열로 투영할 뿐 저장 구조를 추가하지 않습니다. 셀 선택은 `(layer_index, frame_index)`를 `MainWindow`에 전달하며, 메인 창이 캔버스와 상태 표시를 함께 갱신합니다.

별도 `LayerPanel`과 상시 프로젝트 정보 패널은 제거했습니다. `MainWindow`의 중앙 레이아웃은 캔버스와 통합 타임라인만 생성합니다. 향후 왼쪽 도크는 `Effect Library`, 오른쪽 도크는 `Effect Properties`와 생성기 파라미터용으로 예약하되, 실제 기능이 준비되기 전에는 빈 도크를 기본 생성하지 않습니다.

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
- 자동 이펙트: UI와 독립된 `app/services/effects/` 모듈 추가
- 새 파일 형식: `project_io`에 `format_version` 마이그레이션 추가
- 내보내기 대상: `export_service` 주변에 형식별 서비스 추가

## 픽셀 렌더링 규칙

- 좌표와 캔버스 크기는 정수입니다.
- RGBA 버퍼는 `(height, width, 4)` 형태의 `uint8` NumPy 배열입니다.
- 확대/축소는 1–32의 정수 배율이며 부드러운 변환을 끕니다.
- 투명 영역은 UI에서 체커보드로 표현하되 모델 픽셀에는 포함하지 않습니다.
- 레이어는 목록 앞에서 뒤 순서로 합성하고 가시성과 불투명도를 반영합니다.

## 새 프로젝트 검증

`NewProjectDialog`는 이름 앞뒤 공백을 제거하고 빈 이름일 때 생성 버튼을 비활성화합니다. `QSpinBox` 범위로 잘못된 정수 입력을 차단합니다. 캔버스는 모델의 기존 제한인 `1–1024`, FPS는 `1–120`을 사용합니다. 대화상자가 취소되면 `MainWindow.project`를 교체하지 않습니다.

## 단축키와 사용자 설정

단축키 명령, 표시 이름, 기본값의 단일 원천은 `app/shortcuts.py`입니다. `MainWindow`는 각 명령에 QAction 하나만 만들고, 메뉴·키 입력·타임라인 버튼이 동일한 편집 메서드를 사용합니다. 별도 QShortcut을 만들지 않습니다.

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
