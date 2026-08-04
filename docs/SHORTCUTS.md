# Keyboard Shortcuts

## 기본값

| 명령 | Primary | Alternate | 설명 |
|---|---|---|---|
| New Layer | `Shift+N` | — | 새 기본 레이어를 만들고 선택 |
| New Frame | `Alt+N` | — | 현재 프레임을 독립 복사해 다음 위치에 삽입 |
| New Empty Frame | `Alt+B` | — | 현재 위치 다음에 투명 프레임 삽입 |
| Play / Stop Animation | `Enter` | — | 프로젝트 또는 Preview 재생·정지 |
| Previous Frame | `Left` | `<` (`Shift+,`) | 재생을 정지하고 이전 프레임으로 이동 |
| Next Frame | `Right` | `>` (`Shift+.`) | 재생을 정지하고 다음 프레임으로 이동 |

## 변경 방법

1. `Edit > Keyboard Shortcuts…`를 엽니다.
2. 각 입력란에서 키 조합을 입력합니다.
3. `Apply`는 창을 유지한 채 적용하고, `OK`는 적용 후 닫습니다.
4. `Restore Defaults`는 입력란을 기본값으로 되돌립니다. 이후 `Apply` 또는 `OK`로 저장합니다.

입력란을 비우면 해당 명령의 단축키가 비활성화됩니다. 동일한 비어 있지 않은 키 조합은 두 명령에 지정할 수 없습니다. 설정은 프로젝트 파일이 아니라 운영체제의 QSettings 사용자 영역에 저장됩니다.

각 명령은 Primary와 Alternate를 최대 하나씩 저장합니다. 기존 단일 문자열 설정은 기존 값을 유지한 채 Primary 목록으로 자동 마이그레이션됩니다. 언어를 바꿔도 command ID와 저장 단축키는 변경되지 않습니다.

기본 `Enter`는 메인 키보드 Return과 숫자 키패드 Enter를 모두 지원합니다. 캔버스와 일반 선택 상태의 타임라인에서 동작하지만, 텍스트·숫자·단축키를 입력 중이거나 모달 대화상자 또는 메뉴가 열린 동안에는 실행되지 않습니다. 사용자가 다른 키로 변경하면 새 키만 동작하며, 기본값을 복원하면 두 종류의 Enter 지원이 다시 활성화됩니다.

프레임 이동 키는 캔버스와 일반 Timeline 셀에서 동작합니다. Effect Library 목록, 일반 item view, 입력 위젯, scrollbar, 메뉴 또는 대화상자에서는 원래 탐색·입력 동작을 우선합니다. 첫/마지막 프레임에서는 순환하지 않고 현재 위치를 유지합니다.
