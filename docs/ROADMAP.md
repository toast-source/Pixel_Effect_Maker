# Roadmap

이 문서는 향후 개발 계획이며 구현 완료 목록이 아닙니다. 현재 로컬 기준은 **v0.0.03 + Unreleased effect foundation**입니다.

## v0.0.xx — 초기 기반 안정화

- 초기 기반과 파일 형식 안정화
- 통합 레이어·프레임 타임라인 기초 안정화
- 단축키와 프로젝트 정보 등 초기 편집기 사용성 안정화
- 최소 픽셀 편집
- 완료: 전역 실행 취소/다시 실행 기반과 Resource/Effect/Particle 핵심 편집 Command
- 완료: Resource Move/Scale 축 제한 및 2D 회전 Handle
- 완료: 범용 PNG Source Asset, Transform Emitter, Generated Layer 기초
- 완료: Point/Line/Circle, 기본 Transform, Pseudo-3D, 공통 easing
- 완료: 비파괴 Live Preview, Draft/Apply/Revert 흐름과 Preview 재생
- 완료: 이전·다음 프레임 복수 단축키와 한영 런타임 전환 기반
- 완료: Animation Clip → Particle Emitter → Preview → Bake/PNG Sequence 최소 전체 흐름
- 완료: Clip Generator 기즈모와 Splitter 기반 Properties 사용성
- 완료: Resource Editor 최소 수직 흐름, Pivot, duration 재생과 Particle 연결
- 완료: Resource Composition 모델·렌더러·Layer × Time Timeline과 형식 5 저장
- 완료: Position/Rotation/Scale/Opacity Track, Keyframe easing, Composition 기즈모와 Particle 직접 연결
- 완료: 명시적 상태와 Controller 기반 Resource Editor V2, 에셋에서 리소스 원자적 생성
- 완료: 레이어 직접 선택, 실제 Handle hit-test와 Asset/Composition Timeline 분리
- 완료: Effect FPS와 Composition FPS가 다른 Particle 재생 시간 매핑
- 후속: Composition 복제·레이어 재정렬, 키프레임 드래그·다중 선택과 그래프 에디터
- 후속: 안전한 Legacy Transform Generator → Resource Composition 변환

## v0.1.0 — 기본 픽셀 편집 작업 흐름 완성

- 기본 그리기 도구와 편집 히스토리
- 레이어 속성 및 순서 관리
- Source/Generator 이름 변경과 피벗 편집
- 생성 파라미터 편집 사용성 및 미리보기 개선
- Preview 렌더 취소 최적화와 대형 프로젝트 성능 계측
- 남은 오류·경고 문구의 번역 catalog 확대

## v0.2.0 — PNG 소스 기반 이펙트 제작

- 다중 소스 조합과 랜덤 variation
- Arc/Radial/Orbit/Spiral/Custom Path distribution
- 속성별 커브와 재사용 가능한 preset

## v0.3.0 — 자동 이펙트 생성기 1

- Bend, Taper, Twist, Wave 등 deformation 전략
- 잔상, 디졸브, 발광 preset

## v0.4.0 — 자동 이펙트 생성기 2

- 파편, 스파크, 폭발 자동 생성

## v0.5.0 — Aseprite 연동

- Aseprite 파일 기반 교환 워크플로

## v1.0.0 — 정식 버전

- 실제 이펙트 제작에 안정적으로 사용할 수 있는 완성도와 배포 체계
