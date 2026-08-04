# Legacy Generator 호환 정책

Transform Clip Generator와 Generated Animation Clip은 기존 프로젝트 결과를 보존하기 위해 형식 5에서도 읽고 저장합니다. 새 리소스 제작의 중심은 Resource Composition이며 Effect Library에서는 기존 생성기를 `Legacy Clip Generators`로 구분합니다.

이번 단계는 Legacy 데이터를 자동 변환하거나 삭제하지 않습니다. 안전한 변환은 Source Asset, 출력 길이, Position/Rotation/Scale/Opacity의 첫·마지막 값과 지원 easing을 새 Composition Keyframe으로 옮길 수 있어야 합니다. Tilt, Perspective, Distribution, 다중 Instance 등 의미가 일치하지 않는 설정은 자동 변환하지 않아야 합니다. 후속 변환 기능도 기존 Generator와 Generated Layer를 사용자 확인 없이 삭제하지 않습니다.
