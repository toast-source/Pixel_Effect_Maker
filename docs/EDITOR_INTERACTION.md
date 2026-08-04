# Editor Interaction Policy

## 감사 결과와 입력 동기화

기존 `NewResourceDialog`는 FPS 변경을 Duration 변경으로 처리하고, 소수점 3자리로 표시된 Duration을 다시 Frames 계산에 사용했다. `valueChanged → 다른 SpinBox 변경 → 반올림된 값 재입력` 경로가 반복 Step을 덮어썼다. 현재는 `_duration_seconds`와 `_syncing`을 사용하고 `QSignalBlocker`로 재진입을 막는다. Frames 변경은 `duration=frames/fps`, FPS 변경은 이전 Duration을 보존한 새 Frames, Duration 완료는 `frames=round(duration×fps)`로 정규화한다. Duration의 최소값과 Step은 항상 한 프레임이며 4자리로 표시한다.

현재 Dialog는 Duration과 Frames를 동시에 노출하지 않고 `Length + Unit`으로 통합한다. Frames 단위에서는 FPS 변경 시 정수 frame count를 유지하고, Seconds 단위에서는 입력 초를 유지한 채 `max(1, round(seconds × fps))`로 frame count를 다시 계산한다. 단위 왕복은 항상 정수 frame count를 기준으로 정규화한다.

Project Canvas 크기가 바뀔 때는 재생을 멈추고 Effect·Particle Preview Manager의 Context revision을 올린 뒤 Canvas Preview를 지운다. 이전 Context에서 완료된 Worker 결과는 거부한다. Canvas 합성도 source와 destination의 높이·폭이 다르면 오래된 Preview를 표시하지 않고 적용된 Project Frame으로 fallback한다.

## Windows Native SpinBox

`_FocusWheelMixin.focusInEvent()`가 Mouse Focus 시 `setStyleSheet()`로 전체 SpinBox를 다시 polish하고 있었다. Windows 네이티브 Up/Down SubControl을 누르는 도중 스타일과 geometry가 재생성되어 Mouse Press/Release가 같은 SubControl에서 끝나지 않을 수 있는 구조였다. 포커스 StyleSheet, 내부 LineEdit event filter, Mouse Press override를 제거했다. Up/Down 버튼, 키보드, 텍스트 선택과 포커스 표시는 Qt 기본 구현이 담당한다.

공통 클래스의 유일한 추가 책임은 SpinBox 또는 내부 editor가 포커스됐을 때만 Wheel을 기본 구현으로 전달하고, 포커스가 없으면 `event.ignore()`로 상위 ScrollArea에 넘기는 것이다. `QStyle.subControlRect()` 기반 테스트는 첫 클릭, 반복·빠른 클릭, 선택 텍스트, Down, 키보드, Wheel, 위젯 identity와 Auto Repeat를 검사한다. Windows 플랫폼 자동 테스트와 실제 96 DPI GUI에서 다섯 SpinBox를 확인했으며 120/144 DPI는 별도 수동 대상이다.

## UI 설정과 메뉴

`ui/timeline_frame_width`는 프로젝트가 아닌 QSettings에 저장하며 20~96, 기본 36으로 Clamp한다. Effect와 Resource Composition Timeline이 같은 값을 즉시 적용한다. File은 프로젝트·가져오기, Edit는 Undo/Redo·Project Settings·Shortcuts, View는 표시, Export는 실제 출력, Settings는 언어·Interface·External Tools 역할을 갖는다.

## Localization과 Tooltip

활성 MainWindow, Timeline, Particle Panel, Resource Editor와 Interface Settings의 고정 문자열은 `LocalizationService`를 사용한다. FPS, PNG, GIF, Aseprite, X/Y, RGBA와 사용자 입력 이름은 번역하지 않는다. 아이콘·기호 버튼과 Undo/Redo에는 결과와 단축키를 설명하는 한국어·영어 Tooltip을 둔다.

## Undo/Redo

MainWindow의 단일 `application_undo_stack`을 모든 Workspace가 공유한다. 새 프로젝트와 열기에서 Clear하고 저장 성공에서 Clean으로 표시한다. `EditorValueCommand`는 대상 ID·필드·이전값·새값만 보관하며 같은 Editor 변경을 600ms까지 병합한다. Gizmo는 Drag 중 모델을 실시간 갱신하고 Release에서 Command 하나를 만들며 Escape는 시작값을 복원한다.

지원 범위는 Resource Position/Rotation/Scale/Opacity, Keyframe 추가·삭제, Full Rotation, Layer 이름·범위·가시성·Pivot, Asset/Output Pivot과 Gizmo, Effect Frame 추가·복제·삭제, Layer 추가·삭제·가시성, Particle Draft Settings다. Import, 프로젝트 열기, Bake, Export, Composition 생성·삭제와 Transform Generator Draft는 의도적으로 Undo 대상이 아니다.

## Gizmo

Move의 이미지/중앙 영역은 Free, 빨간 X Handle은 X만, 초록 Y Handle은 Y만 정수 픽셀로 변경한다. Scale 모서리는 균등, X/Y Handle은 해당 축만 변경하며 최소 0.01이다. Rotate는 2D Z 회전만 제공하고 Shift는 15°로 스냅한다. Pivot→Rotate→Scale→Axis Move→Free Area 순으로 Hit-test하며 Handle 크기는 zoom과 무관한 화면 기준 픽셀이다.
