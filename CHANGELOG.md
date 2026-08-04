# Changelog

## Unreleased

## v0.0.04 - 2026-08-04

### Fixed

- Resource Editor V2의 PNG/GIF/ASE/Aseprite 공통 Drag and Drop Import 경로 복원
- Project Canvas 크기 변경 전 Effect·Particle Preview 무효화와 비동기 Context revision 검사 추가
- Canvas가 현재 Project와 Shape가 다른 오래된 Preview를 합성하다 예외를 내던 문제 수정
- Asset/Resource 및 Workspace 왕복 시 Composition별 Layer·Frame·Gizmo 선택 상태가 사라지던 문제 수정
- 새 Resource Dialog의 Duration·Frames 이중 입력을 Length + Frames/Seconds 단위 입력으로 통합
- Windows 네이티브 SpinBox 화살표 Mouse Press 중 Focus StyleSheet 재적용으로 SubControl 상태가 재생성되던 문제 수정
- Focus-Wheel 공통 위젯을 포커스된 Wheel 입력 제한에만 사용하고 Qt 기본 Up/Down·Mouse·Focus 처리를 복원
- 새 Resource의 FPS·Duration·Frames 신호 재진입과 표시 반올림으로 반복 Step이 되돌아가던 문제 수정
- 활성 Particle 속성, 메뉴, Tooltip의 한국어/영어 런타임 전환 누락 수정
- Resource Editor V2 Asset List의 숨겨진 빈 compatibility 항목과 실제 항목 밖 Hover 영역 제거
- Layer Inspector 속성을 반응형 세로 Property Card로 재배치해 한국어/영어 UI의 가로 잘림 제거
- 1024×720~1600×900에서 Asset Browser·Canvas·Inspector 최소 폭과 Timeline 높이 유지
- 투명 여백이 큰 에셋의 선택 경계와 Handle을 alpha union bounds에 맞춤

### Changed

- `ui/timeline_frame_width` 기반 20~96px 공통 Timeline 폭과 Interface Settings 추가
- Project Settings를 Edit로 이동하고 중복 Export 항목을 전용 Export 메뉴로 정리
- 전역 QUndoStack과 Resource/Effect/Particle 핵심 Command, 600ms 연속 변경 병합 추가
- Move X/Y, Scale X/Y·균등, Shift 15° Rotate 화면 고정 Handle 추가

- Resource Editor V2를 설정 저장형 Horizontal/Vertical Splitter 구조로 변경
- Layer Inspector를 세로 Scroll 전용으로 변경하고 기즈모 선택 버튼을 2×2 Grid로 배치

### Added

- Effect Timeline과 Resource Composition Timeline 공통 클릭 드래그 스크러빙
- 일반 실행용 새 프로젝트 설정·기존 프로젝트 열기 Startup Dialog
- 빈 Resource Editor의 에셋 가져오기·빈 Resource 만들기 시작 패널

- EMPTY/ASSET_INSPECT/COMPOSITION/LAYER_EDIT 상태와 단일 선택 Controller를 사용하는 Resource Editor V2
- 원본 이름·크기·재생 시간 기반 `Create Resource from This Asset` 원자적 생성 흐름
- Canvas 레이어 직접 선택, 선택 경계와 실제 Move/Rotate/Scale/Pivot Handle hit-test
- Asset Frame Strip과 분리된 Composition 전용 Layer × Time Timeline
- QTest 실제 클릭 기반 PNG→Resource→Full Rotation→재생→Particle Preview 회귀 테스트

- 타임라인 기반 Resource Composition, Composition Layer, Animation Track, Keyframe 모델
- Position/Rotation/Scale/Opacity 속성 검색·등록과 Linear/Ease In/Ease Out/Ease In/Out 평가
- 최근접 이웃 Composition Renderer, 레이어 범위·표시·피벗·source-over 합성 및 revision 캐시
- Composition Canvas의 Move/Rotate/Scale/Pivot 기즈모와 한 바퀴 회전 빠른 명령
- Resource Composition을 직접 사용하는 Particle Preview, Bake와 PNG Sequence Export 흐름
- 프로젝트 형식 5와 형식 4 Resource 데이터 보존 마이그레이션

- MainWindow의 기본 Resource Workspace를 모듈화된 Resource Editor V2로 교체
- Particle Composition 시간 계산을 Effect Project FPS 기준 초→Composition FPS 순서로 수정
- 새 프로젝트에서는 Legacy Transform Generator 생성 UI를 숨기고 기존 Generator가 있을 때만 호환 영역 표시

- Resource Editor를 Assets 검사와 Compositions 제작을 함께 제공하는 Resource Composition Editor로 재구성
- Transform Clip Generator를 새 프로젝트의 중심 개념에서 `Legacy Clip Generators` 호환 영역으로 이동

- Effect Editor와 Resource Editor Workspace 전환
- 통합 Resource Library, 다중 Drag and Drop과 공통 Import 명령
- Checkerboard/Nearest Resource Preview, 프레임 duration Timeline과 Workspace 단축키 라우팅
- Pivot 수치·캔버스 Gizmo·Center Pivot 및 Preview invalidation
- External Tools Aseprite Browse/Auto Detect/Validate/Clear 설정
- Resource Reimport, 참조 보호 삭제, Resource에서 Particle Emitter 생성
- 정적 Source와 Animated Clip을 함께 표시하는 Particle Resource Picker

- PNG/GIF 공통 Resource import와 프레임별 duration 보존
- Aseprite 탐색·검증 및 격리된 CLI import adapter
- 정적 Source와 Animation Clip의 Particle 공통 참조
- 한·영 태그 기반 Property Registry 검색 기반
- 타임라인 레이어 헤더를 통한 실제 Layer Visibility 변경
- 프로젝트 형식 4와 v1·v2·v3 마이그레이션

- 프로젝트 내부 독립 Animation Clip과 결정적 Particle Emitter 전체 흐름
- Burst/Over Time, Point/Line/Circle/Box, Fixed/Radial 방향과 Seed 기반 랜덤 범위
- Once/Loop/Hold Animated Particle Preview, 전용 Bake와 PNG Preview Sequence 출력
- Clip Generator Move/Rotate/Scale/Distribution 캔버스 기즈모
- 프로젝트 형식 3 및 형식 1·2 마이그레이션

- 임의 PNG를 프로젝트 내부 RGBA Source Asset으로 가져오는 비파괴 소스 관리
- Effect Library와 Transform Emitter용 Effect Properties 패널
- Point, Line, Circle distribution과 deterministic instance emission
- Position, Rotation, Scale X/Y, Opacity 및 세 가지 easing 렌더링
- Horizontal Tilt, Vertical Tilt, Perspective 최근접 사각형 변형
- 생성기별 전용 Generated Layer와 원자적 재생성
- 프로젝트 형식 2 Source/Generator 직렬화 및 형식 1 마이그레이션
- Generator Draft와 프로젝트 데이터를 분리한 비파괴 Live Preview
- 250ms Auto Preview, 수동 Refresh와 최신 revision 결과만 표시하는 비동기 렌더링
- 이전·다음 프레임 Primary/Alternate 단축키
- 한국어·English 런타임 전환과 언어 설정 유지
- Effect Properties 단위, Tooltip, Start → End 행과 접이식 섹션

- 메인 편집 영역을 저장·복원 가능한 3분할 QSplitter로 변경
- 우측 Properties를 최소 360px의 세로 스크롤 패널로 조정
- Wheel 값 변경은 입력을 실제 클릭해 포커스를 얻은 동안에만 허용

- Generate 버튼을 Apply to Frames로 명확화
- Reset Settings를 Revert Changes와 Reset to Defaults로 분리
- 숫자 및 ComboBox가 포커스 없이 Wheel 값 변경을 소비하지 않도록 개선

## v0.0.03 - 2026-08-03

### Fixed

- Enter 재생 단축키가 실제 메인 편집 화면에서 작동하지 않던 문제
- 재생 단축키가 입력 위젯 및 모달 대화상자와 충돌할 수 있던 문제

### Changed

- Animation 메뉴에서 불필요한 Play / Stop Animation 항목 제거
- 빈 캔버스에서도 재생 상태와 현재 프레임을 확인할 수 있도록 표시 개선

## v0.0.02 - 2026-08-03

### Added

- 편집 가능한 Project Settings 대화상자
- 캔버스 전용 크기 변경과 이미지 포함 스케일 변경
- 캔버스 전용 변경을 위한 9개 Anchor
- Enter 기반 애니메이션 재생·정지 단축키
- 재생 확인용 8프레임 Playback Test Project

### Changed

- Project Info를 Project Settings로 교체
- FPS와 Loop를 프로젝트 생성 후 변경 가능하도록 개선
- Scale 변환을 픽셀아트용 최근접 이웃으로 고정
- 타임라인의 `Layer × Frame Timeline` 제목과 여백 제거

## v0.0.01 - 2026-08-03

### Added

- PySide6 기반 기본 편집기 화면
- 정수 배율 픽셀 캔버스와 투명 체커보드
- 레이어 추가와 삭제
- 프레임 추가, 복제, 삭제
- 프로젝트 JSON 저장 및 불러오기
- 애니메이션 재생과 FPS 설정
- 투명 PNG 프레임 내보내기
- 초기 모델, 파일 입출력, PNG 내보내기 테스트
- 중앙 버전 정보와 `--version` 명령
- Aseprite 기준 `Shift+N`, `Alt+N`, `Alt+B` 기본 단축키
- QSettings 기반 사용자 단축키 설정, 충돌 검사, 기본값 복원
- 읽기 전용 프로젝트 정보 대화상자

### Fixed

- 프레임을 반복 복제할 때 이름에 `Copy`가 누적되던 문제
- 프레임 표시를 현재 순서 기반의 연속 번호로 정리
- 레이어 삭제 후 새 기본 레이어 이름이 기존 이름과 충돌할 수 있던 문제
- 새 프로젝트 설정이 여러 대화상자로 나뉘어 있던 문제

### Changed

- 레이어와 프레임을 교차 셀로 확인하고 선택하는 통합 타임라인 기초 UI 추가
- 새 프로젝트 이름, 캔버스 크기, FPS, 반복 재생을 한 대화상자에서 설정
- 중복된 별도 레이어 패널을 제거하고 통합 타임라인을 레이어 관리 중심으로 변경
- 상시 프로젝트 정보 패널을 `File > Project Info…` 대화상자로 이동
- 제거된 좌우 패널 공간을 중앙 캔버스에 반환
