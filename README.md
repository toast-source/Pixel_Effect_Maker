# Pixel Effect Maker

현재 버전은 **v0.0.04**이며, 가져온 에셋을 타임라인 기반 Resource Composition으로 애니메이션화해 Particle에 사용하는 첫 알파 체크포인트입니다.

Pixel Effect Maker의 장기적인 목적은 Aseprite를 대체하는 범용 픽셀 편집기가 되는 것이 아닙니다. 사용자가 만든 임의의 투명 PNG를 비파괴 Source Asset으로 가져오고, 범용 Emitter와 시간 기반 Transform으로 여러 프레임의 픽셀 이펙트를 반자동 생성하는 도구를 목표로 합니다. 파일명이나 특정 실루엣에 따른 특수 처리는 사용하지 않습니다.

## 현재 구현 기능

- PySide6 기반 1280 × 800 반응형 메인 창
- 정수 배율·최근접 이웃 렌더링과 투명 체커보드가 있는 중앙 캔버스
- 레이어 추가/삭제 및 프레임 추가/복제/삭제
- 전역 Undo/Redo(`Ctrl+Z`, `Ctrl+Shift+Z`, `Ctrl+Y`)와 축 제한 Move/Scale·2D Rotate 기즈모
- 설정에서 20~96px로 조절하고 재시작 후 복원되는 공통 Timeline Frame Width
- 레이어를 행, 프레임 번호를 열로 표시하고 클릭 드래그 스크러빙을 지원하는 통합 타임라인
- 통합 타임라인 안에서 레이어·프레임 추가 및 삭제
- 프레임 애니메이션 재생/정지와 1–120 FPS 설정
- 일반 실행 시 먼저 표시되며 이름, 캔버스 크기, FPS, 초기 프레임 수, 반복 재생 또는 기존 프로젝트 열기를 선택하는 시작 대화상자
- Aseprite 기준 기본 단축키와 사용자 단축키 설정
- `File > Project Settings…`에서 이름, FPS, Loop, 캔버스 크기 변경
- 9개 anchor 기반 Canvas Only resize와 최근접 이웃 Scale
- 메인/숫자 키패드 `Enter` 또는 타임라인 재생 버튼을 통한 애니메이션 재생·정지
- 빈 캔버스에서도 보이는 Playing/Stopped, 현재 프레임, 전체 프레임 수, FPS 상태 표시
- 현재 프레임 열 강조와 자동 스크롤
- RGBA/RGB/인덱스/그레이스케일 PNG의 독립 Source Asset 가져오기와 프로젝트 내부 픽셀 저장
- Imported Assets, Resource Compositions, Legacy Clip Generators, Particle Emitters를 구분하는 편집 흐름
- Point, Line, Circle 배치의 범용 Transform Emitter
- Position, Rotation Z, 독립 Scale X/Y, 반전, Opacity의 수명 기반 보간
- Horizontal Tilt, Vertical Tilt, Perspective의 최근접 사각형 변형
- Linear, Ease In, Ease Out 공통 easing
- 생성기별 전용 Generated Layer와 비파괴·원자적 재생성
- Generator별 Draft와 실제 프로젝트를 분리한 비파괴 Live Preview
- 250ms Auto Preview, 수동 Refresh, Apply to Frames와 Revert Changes
- Preview 전체 프레임 재생 및 현재 표시 대상 배지
- `Left`/`<`, `Right`/`>` 이전·다음 프레임 이동
- 한국어·English 런타임 UI 전환과 QSettings 유지
- 저장 가능한 3분할 Splitter, 스크롤 가능한 우측 패널과 클릭 포커스 기반 Wheel 입력
- Move/Rotate/Scale/Distribution Clip Generator 캔버스 기즈모
- 독립 RGBA Animation Clip 생성·명시적 업데이트 및 공유
- Seed 결정적 Particle Emitter와 Animated Particle Preview, Bake, PNG 시퀀스 출력
- PNG/GIF Embedded Resource, GIF 프레임 duration과 정적 Resource Particle 재생
- 프로젝트 레이어별 표시 전환과 형식 5 Resource Composition 저장
- Effect Editor/Resource Editor Workspace 전환과 통합 Resource Library
- PNG/GIF/Aseprite 다중 Drag and Drop, 전용 Preview·duration Timeline·Pivot 편집
- 비어 있는 Resource Editor에서 에셋 가져오기 또는 빈 Resource Composition 생성을 선택하는 시작 패널
- 정적/애니메이션 Resource 공통 Particle Picker와 Resource→Emitter 생성
- QSettings 기반 External Tools Aseprite 경로 탐색·검증
- 움직이는 8프레임 `Playback Test Project`
- `.peffect.json` 형식 5 저장/불러오기와 형식 1·2·3·4 프로젝트 마이그레이션
- 합성 프레임의 투명 PNG 순차 내보내기
- 미저장 변경 표시와 닫기/새 프로젝트/불러오기 시 확인

## 폴더 구조

```text
app/          PySide6 UI, 모델, 저장·내보내기 서비스
tests/        데이터 모델, 파일 입출력, 버전 테스트
projects/     사용자 프로젝트 파일(기본 Git 제외)
exports/      PNG 내보내기 결과(기본 Git 제외)
docs/         개발 문서, 로드맵, 수동 테스트 체크리스트
assets/       향후 정적 에셋
```

## 설치

Python 3.13 기준입니다. 프로젝트 루트에서 다음 명령을 실행합니다.

```bat
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 실행과 진단

일반 실행:

```bat
run_app.bat
```

또는:

```bat
.venv\Scripts\python.exe -m app.main
```

메인 창을 생성한 뒤 즉시 정상 종료하는 시작 점검:

```bat
.venv\Scripts\python.exe -m app.main --check
run_app.bat --check
```

GUI를 생성하지 않고 버전 확인:

```bat
.venv\Scripts\python.exe -m app.main --version
```

## 키보드 단축키

| 명령 | 기본 단축키 | 동작 |
|---|---|---|
| New Layer | `Shift+N` | 충돌하지 않는 기본 이름으로 새 레이어 생성 |
| New Frame | `Alt+N` | 현재 프레임을 독립 복사해 바로 다음에 삽입 |
| New Empty Frame | `Alt+B` | 투명 프레임을 현재 프레임 다음에 삽입 |
| Play / Stop Animation | `Enter` | 애니메이션 재생과 정지 전환 |

`Edit > Keyboard Shortcuts…`에서 변경, 비활성화, 기본값 복원이 가능합니다. 사용자 설정은 QSettings에 저장되며 프로젝트 JSON에는 포함되지 않습니다. 동일한 단축키를 여러 명령에 지정할 수 없습니다. 기본 `Enter`는 메인 편집기의 일반 선택 상태에서 메인 Return과 숫자 키패드 Enter를 모두 지원하며, 텍스트·숫자·단축키 입력 중이거나 모달 대화상자 또는 메뉴가 열린 동안에는 재생을 전환하지 않습니다.

`File > Project Settings…`에서 프로젝트 이름, FPS, 반복 재생과 캔버스 크기를 변경합니다. Canvas Only는 픽셀 크기를 유지한 채 9개 anchor를 기준으로 공간을 추가하거나 자르고, Scale은 모든 프레임·레이어를 최근접 이웃으로 변환합니다. 축소와 Scale처럼 되돌릴 수 없는 변경은 적용 전에 확인합니다.

`File > Import Source Asset…` 또는 왼쪽 Effect Library에서 PNG를 가져온 뒤 `Add Transform Emitter`를 누릅니다. 오른쪽 Effect Properties의 값을 바꾸면 기본 250ms debounce 후 중앙 캔버스에 비파괴 Live Preview가 나타납니다. Preview는 프로젝트 저장·내보내기 대상이 아니며 `Apply to Frames`를 눌러야 `Generated: <이름>` 레이어에 확정됩니다. `Revert Changes`는 마지막 적용값으로, `Reset to Defaults`는 초기 Draft로 돌아가며 둘 다 적용 전에는 프로젝트를 변경하지 않습니다.

`Settings > Language`에서 한국어와 English를 즉시 전환할 수 있습니다. 언어와 Auto Preview 설정은 프로젝트가 아닌 QSettings에 저장됩니다.

## Resource Composition 빠른 흐름

`Resource Editor`가 비어 있으면 시작 패널에서 PNG/GIF/Aseprite를 가져오거나 현재 프로젝트 크기·FPS를 기본값으로 빈 리소스를 만들 수 있습니다. 에셋을 선택하고 `Create Resource from This Asset`을 누르면 원본 이름·크기·재생 시간을 기준으로 설정된 리소스와 첫 Layer가 한 번에 생성됩니다. 이어서 `Full Rotation`을 누르면 전체 구간에 0°→360° 키프레임이 만들어져 바로 재생할 수 있습니다. Asset 검사 중에는 Composition Timeline과 기즈모가 숨겨지고, Resource와 Layer를 편집할 때만 관련 Canvas·Inspector·Timeline이 표시됩니다.

완성한 Composition은 `Use This Resource in Effect`으로 Particle Emitter를 생성하고 Effect Editor에서 바로 Preview할 수 있습니다. Particle 시간은 Effect Project FPS를 초 단위로 변환한 뒤 Composition FPS와 Playback Speed를 적용합니다. 자세한 구조는 [Resource Editor](docs/RESOURCE_EDITOR.md)와 [Resource Compositions](docs/RESOURCE_COMPOSITIONS.md)를 참고합니다.

브러시 없이도 재생을 확인하려면 `File > Create Playback Test Project`를 사용합니다. 투명 배경 위의 8×8 사각형이 8프레임 동안 좌우로 이동하며 일반 프로젝트와 동일하게 저장·불러오기·PNG 내보내기가 가능합니다.

## 테스트

```bat
.venv\Scripts\python.exe -m pytest -q
```

## 기본 파일 위치

- 프로젝트: `projects/*.peffect.json`
- PNG 내보내기: `exports/*.png`

파일 대화상자에서 다른 위치도 선택할 수 있습니다. 생성된 프로젝트와 내보내기 결과는 기본적으로 Git에서 제외됩니다.

## 현재 지원하지 않는 기능

- 브러시, 지우개, 스포이트, 채우기, 선택
- Custom Path, Spiral, Orbit distribution
- Bend, Twist, Wave, Bulge, Pinch, 자유 Mesh Deform
- 그래프 기반 속성 커브 편집, 다중 키프레임 선택·드래그
- Resource Composition 레이어 재정렬과 중첩 Composition
- 스프라이트 시트, GIF, Unity, Godot 내보내기
- PyInstaller 실행 파일 배포
- 대형 프로젝트용 압축 픽셀 저장 형식

프레임은 타임라인에서 현재 배열 순서를 기준으로 `1`, `2`, `3`처럼 표시됩니다. 프로젝트 파일 호환성을 위해 프레임의 기존 `name` 필드는 유지하지만 타임라인 번호에는 사용하지 않습니다. 새 프로젝트의 캔버스 범위는 현재 모델 제약에 맞춘 `1–1024`, FPS 범위는 `1–120`입니다.

기본 화면은 왼쪽 `Effect Library`, 중앙 캔버스, 오른쪽 `Effect Properties`, 하단 통합 타임라인으로 구성됩니다. 구현되지 않은 Bend, Twist, Mesh 등의 컨트롤은 표시하지 않습니다. 상단 `Animation` 메뉴는 향후 명령을 위한 자리로 유지하지만 현재는 비어 있으며, 재생은 타임라인 버튼 또는 단축키로 조작합니다. 자세한 생성 규칙은 [Effect System](docs/EFFECT_SYSTEM.md)을 참고합니다.
