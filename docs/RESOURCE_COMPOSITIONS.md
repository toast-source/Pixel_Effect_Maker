# Resource Compositions

Resource Composition은 Imported Asset과 Effect 사이의 재사용 가능한 애니메이션 단위입니다.

```text
Imported Asset → Resource Composition → Particle / Effect → Preview → Bake / Export
```

Composition은 독립적인 이름, 캔버스 크기, FPS, 프레임 수, Loop, 출력 Pivot과 정렬된 Layer 목록을 가집니다. Layer는 SourceAsset 또는 AnimationClipAsset ID를 참조하고 표시 상태, 시작·종료 프레임, 원본 시작 프레임과 Composition 전용 Pivot을 가집니다. Composition 중첩은 허용하지 않아 순환 참조가 생기지 않습니다.

등록 가능한 Track은 `position`, `rotation`, `scale`, `opacity`입니다. 등록하지 않은 Track은 각각 `[0, 0]`, `0°`, `[1, 1]`, `1.0`을 사용합니다. Keyframe은 프레임, 값과 Linear/Ease In/Ease Out/Ease In/Out easing을 저장합니다. 같은 프레임에 다시 기록하면 교체되며 평가 시 항상 프레임 순서로 정렬됩니다.

Renderer는 매 프레임을 투명 `uint8 RGBA` 버퍼에서 새로 시작합니다. Layer 표시·범위를 확인하고, Animated Asset duration을 Composition 시간에 매핑한 다음 Pivot 기준 Position/Rotation/Scale, Opacity와 source-over 합성을 수행합니다. 좌표 샘플링은 최근접 이웃만 사용하고 캔버스 밖은 자릅니다. 원본 Asset과 이전 렌더 결과는 수정하지 않습니다.

Particle 연결에서는 Composition 전체 프레임을 결정적으로 렌더한 AnimationClip-compatible frame source를 사용합니다. Particle age는 먼저 `age / effect_project_fps`로 초 단위가 되고, 여기에 Composition FPS와 Particle Playback Speed를 곱해 `floor`한 프레임을 선택합니다. 따라서 Effect와 Composition FPS가 달라도 실제 재생 시간이 유지됩니다. Random Start를 더한 뒤 Loop/Once/Hold를 적용합니다.

캐시 키는 Composition ID, revision, 크기, FPS와 프레임 수이며 Composition 또는 참조 원본이 바뀌면 무효화합니다. 캐시는 저장 데이터가 아니므로 프로젝트를 다시 열면 재생성됩니다.

형식 5는 Composition과 모든 Layer/Track/Keyframe을 저장합니다. 형식 1~4는 원본 Asset, Animation Clip, Particle 및 Legacy Generator를 그대로 읽고 빈 Composition 목록으로 마이그레이션합니다. 파일을 여는 것만으로 디스크의 원본 프로젝트를 다시 쓰지 않습니다.
