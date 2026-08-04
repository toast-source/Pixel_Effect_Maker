# Pixel Effect Maker v0.0.04

릴리즈 날짜: 2026-08-04

## 요약

v0.0.04는 누적 개발된 Resource Composition Editor V2를 첫 알파 체크포인트로 정리한 릴리즈입니다. PNG/GIF/Aseprite 에셋을 가져와 타임라인 기반 리소스를 만들고, 키프레임 애니메이션을 Particle 리소스로 사용하는 수직 흐름을 제공합니다.

## 핵심 사용자 흐름

- 일반 실행 → Startup Dialog에서 새 프로젝트 설정 또는 기존 프로젝트 열기 → Effect Editor
- Resource Editor 빈 상태 → 에셋 가져오기 또는 빈 리소스 만들기
- 에셋 검사 → Resource Composition 생성 → Layer 속성·키프레임 편집 → Particle에서 사용
- Effect/Resource Timeline에서 마우스를 누른 채 좌우 이동 → 재생 정지와 실시간 프레임 스크러빙

## 주요 추가·변경·수정

- Resource Composition 모델, Editor V2, Composition Canvas·Timeline·Inspector
- PNG/GIF/Aseprite 가져오기, Drag and Drop, Animation Clip과 Particle 연동
- Position/Rotation/Scale/Opacity 키프레임, easing, Full Rotation
- 공통 Timeline Frame Width, 클릭 드래그 스크러빙, Undo/Redo와 축 제한 기즈모
- Project Resize 시 Preview 수명 관리 및 비동기 revision 검사
- Windows 네이티브 SpinBox 버튼, Inspector 잘림, 보이지 않는 Asset 항목, 선택 복원 회귀 수정
- 한국어/영어 런타임 현지화와 Resource/Startup 시작 흐름

## 데이터 호환성

- 애플리케이션 버전: `0.0.04`
- 프로젝트 형식: `FORMAT_VERSION = 5`
- 형식 1~4 프로젝트를 읽어 형식 5 모델로 마이그레이션하며, 형식 5 저장·불러오기를 지원합니다.

## 검증

- 자동 테스트 결과: `216 passed in 11.60s`
- `python -m app.main --version`: `Pixel Effect Maker v0.0.04`
- `python -m app.main --check`, `run_app.bat --check`: 모두 종료 코드 0
- 실제 Windows GUI: 한국어 Startup Dialog 표시, 64×64·12 FPS·초기 12프레임·Loop 프로젝트 생성, Effect Timeline 1→12 스크러빙 후 Frame 12 유지, 빈 Resource 64×64·12 FPS·12프레임 생성, Effect↔Resource 왕복 후 Resource 유지 확인

## 미확인 수동 항목

- Explorer에서 실제 파일 Drag and Drop과 ASE/Aseprite 부분 성공
- 125%/150% DPI에서 SpinBox와 기즈모 hit-test
- Preview 활성 상태의 600×600 Project Resize 전 흐름
- Resource Length Frames/Seconds와 선택 복원 전체 조합
- Startup의 프로젝트 열기·취소·재실행과 레이어가 있는 Resource Timeline 수동 스크러빙
- Timeline Frame Width 20/36/64/96px별 실제 Windows 드래그 (QTest 자동 검증은 통과)

## 알려진 제한 사항

- Keyframe/Layer 순서 Drag, Graph Editor, Composition 중첩은 지원하지 않습니다.
- Tilt/Perspective 전용 기즈모, Mesh Deform, Aseprite 내부 Layer 편집은 지원하지 않습니다.
- 최근 프로젝트 목록은 이번 Startup Dialog에 포함하지 않았습니다.
- Resource 시작 흐름은 반복 Popup 대신 항상 접근 가능한 Empty State Panel로 제공합니다.

Build, EXE, ZIP 및 GitHub Release는 생성하지 않았습니다.
