# Pixel Effect Maker

현재 버전은 **v0.0.02**이며, 프로젝트 설정과 애니메이션 재생 흐름을 검증하는 초기 개발 버전입니다.

Pixel Effect Maker의 장기적인 목적은 Aseprite를 대체하는 범용 픽셀 편집기가 되는 것이 아닙니다. 사용자가 직접 만든 픽셀 이미지나 PNG·Aseprite 소스를 바탕으로 잔상, 발광, 디졸브, 파편, 스파크 등의 애니메이션 이펙트를 빠르게 생성하고 픽셀 단위로 보정할 수 있게 하는 도구를 목표로 합니다. 소스 가져오기와 자동 이펙트 생성은 향후 목표이며 v0.0.02에는 아직 구현되지 않았습니다.

## 현재 구현 기능

- PySide6 기반 1280 × 800 반응형 메인 창
- 정수 배율·최근접 이웃 렌더링과 투명 체커보드가 있는 중앙 캔버스
- 레이어 추가/삭제 및 프레임 추가/복제/삭제
- 레이어를 행, 프레임 번호를 열로 표시하는 통합 타임라인과 교차 셀 선택
- 통합 타임라인 안에서 레이어·프레임 추가 및 삭제
- 프레임 애니메이션 재생/정지와 1–120 FPS 설정
- 이름, 캔버스 크기, FPS, 반복 재생을 한 번에 설정하는 새 프로젝트 대화상자
- Aseprite 기준 기본 단축키와 사용자 단축키 설정
- `File > Project Settings…`에서 이름, FPS, Loop, 캔버스 크기 변경
- 9개 anchor 기반 Canvas Only resize와 최근접 이웃 Scale
- `Enter` 또는 재생 버튼을 통한 애니메이션 재생·정지
- 움직이는 8프레임 `Playback Test Project`
- `.peffect.json` 프로젝트 저장/불러오기와 `format_version` 검증
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

`Edit > Keyboard Shortcuts…`에서 변경, 비활성화, 기본값 복원이 가능합니다. 사용자 설정은 QSettings에 저장되며 프로젝트 JSON에는 포함되지 않습니다. 동일한 단축키를 여러 명령에 지정할 수 없습니다.

`File > Project Settings…`에서 프로젝트 이름, FPS, 반복 재생과 캔버스 크기를 변경합니다. Canvas Only는 픽셀 크기를 유지한 채 9개 anchor를 기준으로 공간을 추가하거나 자르고, Scale은 모든 프레임·레이어를 최근접 이웃으로 변환합니다. 축소와 Scale처럼 되돌릴 수 없는 변경은 적용 전에 확인합니다.

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
- 실행 취소와 다시 실행
- PNG 및 Aseprite 소스 가져오기
- 잔상, 발광, 디졸브, 파편, 스파크 등의 자동 생성
- 레이어 재정렬과 이름/가시성/불투명도 편집 UI
- 스프라이트 시트, GIF, Unity, Godot 내보내기
- PyInstaller 실행 파일 배포
- 대형 프로젝트용 압축 픽셀 저장 형식

프레임은 타임라인에서 현재 배열 순서를 기준으로 `1`, `2`, `3`처럼 표시됩니다. 프로젝트 파일 호환성을 위해 프레임의 기존 `name` 필드는 유지하지만 타임라인 번호에는 사용하지 않습니다. 새 프로젝트의 캔버스 범위는 현재 모델 제약에 맞춘 `1–1024`, FPS 범위는 `1–120`입니다.

기본 화면은 중앙 캔버스와 통합 타임라인만 사용합니다. 제거된 왼쪽 패널 영역은 향후 `Effect Library`, 오른쪽 영역은 `Effect Properties`와 생성기 파라미터용으로 계획되어 있지만, v0.0.02에는 실제 이펙트 패널이나 가짜 옵션을 표시하지 않습니다.
