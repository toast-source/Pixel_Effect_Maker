# Effect System Foundation

## 목적

이 시스템은 특정 초승달, 검기, 불꽃 형태를 판별하거나 파일명에 따라 특수 처리하지 않습니다. 임의의 투명 RGBA Source Asset을 여러 위치와 시간에 인스턴스화하고 동일한 Transform 파이프라인으로 Generated Layer를 만드는 범용 기반입니다.

## 데이터 흐름

외부 PNG/GIF/Aseprite는 Imported Asset이 된 뒤 Resource Editor의 Composition Layer에서 비파괴적으로 애니메이션화됩니다. Resource Composition ID/type 참조가 Particle Emitter로 전달되며 파일 형식별 별도 이동·방출 렌더 경로를 만들지 않습니다.

```text
Imported Asset
→ Resource Composition
→ Particle Emitter
→ deterministic Particle Instances
→ non-destructive Preview
→ Bake / Preview Sequence Export
```

Source 편집은 원본 리소스 관리, Clip 제작은 짧은 재사용 애니메이션 확정, Particle 합성은 Clip 인스턴스의 시간·공간 배치, Bake는 최종 프로젝트 프레임 적용입니다. Preview Sequence Export는 Bake 없이 현재 revision의 미리보기만 기록합니다.

Source Asset은 일반 프레임 레이어와 분리됩니다. 가져올 때 RGBA NumPy 배열을 복사해 프로젝트 JSON 안에 저장하므로 이후 외부 PNG가 없어도 동작합니다. 기본 피벗은 이미지 중앙이며 현재 UI에서는 읽기 전용입니다. 여러 Emitter가 같은 Source를 공유할 수 있습니다.

## 현재 구현

- Distribution: Point, Line, Circle 및 각도 범위를 이용한 호
- Timing: output frames, instance count, start frame, emission interval, lifetime
- Transform: Position, Rotation Z, signed Scale X/Y, Opacity
- Pseudo-3D: Horizontal Tilt, Vertical Tilt, Perspective
- Easing: Linear, Ease In, Ease Out
- Determinism: 저장된 seed와 안정된 instance 순서

Pseudo-3D는 실제 카메라나 3D 모델이 아닙니다. Source를 네 모서리의 사각형으로 보고 목적지 사변형을 만든 뒤 역방향 좌표 매핑으로 변형합니다. 샘플 좌표는 정수에 반올림하며 Bilinear/Bicubic을 사용하지 않습니다. Opacity는 Source alpha에 곱하고 인스턴스 겹침은 straight-alpha source-over 순서로 합성합니다.

## 비파괴 재생성

Generate는 언제나 원본 Source Asset과 현재 settings에서 전체 출력 버퍼를 새로 계산합니다. 이전 Generated Layer를 다시 변형하지 않습니다. 계산을 완료한 뒤 해당 Emitter의 전용 레이어만 교체하며 일반 레이어, 다른 Emitter 결과와 Source 원본은 바꾸지 않습니다. 출력 프레임이 부족하면 확장하지만 기존 프레임은 삭제하지 않습니다.

## Live Preview와 Draft

Properties 입력은 committed Generator settings를 직접 바꾸지 않습니다. Generator별 Draft 복사본이 revision과 dirty 상태를 보유하고, 250ms debounce 후 Source·Draft·캔버스 메타데이터 snapshot만 worker에서 렌더합니다. 결과는 메인 스레드가 수거하며 현재 revision과 Generator/project context가 일치할 때만 PreviewSession에 반영합니다.

Canvas는 Preview 활성 Generator의 실제 Generated Layer를 transient Preview buffer로 대체해 표시합니다. 다른 레이어와 Source 원본은 공유하되 수정하지 않습니다. Preview frame count는 프로젝트와 독립적이며 재생, Enter와 이전·다음 프레임 이동이 Preview 범위를 사용합니다. Save, 프로젝트 JSON과 PNG Export에는 Preview가 포함되지 않습니다.

`Apply to Frames`만 Preview/Draft를 실제 Generator settings와 Generated Layer에 원자적으로 확정합니다. 같은 revision의 Preview가 있으면 재사용하고 없으면 최종 snapshot을 렌더합니다. `Revert Changes`는 committed settings를 Draft로 복원하고, `Reset to Defaults`는 초기값 Draft만 만들기 때문에 다시 Apply해야 확정됩니다.

## 파일 형식

애플리케이션 버전은 `0.0.04`, 최신 프로젝트 `FORMAT_VERSION`은 `5`입니다. 형식 5는 Imported Asset, 기존 Animation Clip/Particle/Legacy Generator와 함께 Resource Composition의 크기·FPS·길이·Loop, Layer, Track, Keyframe과 easing을 저장합니다. 형식 1~4는 기존 데이터를 유지하고 Composition 목록만 빈 상태로 보완합니다.

## Particle 규칙

모든 범위 난수는 Seed 기반 Instance 생성 시 한 번 확정합니다. Burst는 같은 시점, Over Time은 emission duration에 분산합니다. Point/Line/Circle 표면/Box 내부 생성과 Fixed Direction/Spread, Radial Outward를 지원합니다. 위치는 `start + velocity × age`, 회전은 `initial + angular velocity × age`입니다. Once는 Clip 종료 후 숨고 Loop는 순환하며 Hold는 마지막 프레임을 유지합니다.

Resource Composition 재생 시간은 Effect 프레임 번호를 Composition FPS로 직접 해석하지 않습니다. `particle age / Effect Project FPS`로 실제 초를 계산하고 `Composition FPS × Playback Speed`를 적용해 내부 프레임을 선택합니다. 이 규칙은 12↔24 FPS 조합, 0.5×/2× 속도와 Random Start에서도 동일합니다.

## 후속 확장 지점

현재 deformation 값은 `none`만 허용하며 작동하지 않는 컨트롤은 표시하지 않습니다. Particle 기즈모, 수명 기반 Scale curve, Spread 드래그 핸들, 실행 중 worker 강제 취소는 후속 확장입니다. Bend, Twist, Mesh Deform, Orbit, Custom Path와 힘장도 아직 구현되지 않았습니다.
