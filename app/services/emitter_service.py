"""Deterministic Transform Emitter instance and lifetime calculations."""

from __future__ import annotations

import math

from app.models.effect_generator import (
    Distribution,
    Easing,
    EffectInstance,
    TransformEmitterSettings,
)


def ease(value: float, easing: str) -> float:
    value = max(0.0, min(1.0, value))
    if easing == Easing.EASE_IN.value:
        return value * value
    if easing == Easing.EASE_OUT.value:
        return 1.0 - (1.0 - value) * (1.0 - value)
    return value


def interpolate(start: float, end: float, amount: float) -> float:
    return start + (end - start) * amount


def distribution_origin(
    settings: TransformEmitterSettings, index: int
) -> tuple[float, float]:
    """Return the stable start position for one distribution slot."""
    count = settings.instance_count
    fraction = 0.0 if count <= 1 else index / (count - 1)
    distribution = Distribution(settings.distribution)
    if distribution is Distribution.LINE:
        return (
            interpolate(settings.origin_x, settings.line_end_x, fraction),
            interpolate(settings.origin_y, settings.line_end_y, fraction),
        )
    if distribution is Distribution.CIRCLE:
        angle = math.radians(
            interpolate(settings.angle_start, settings.angle_end, fraction)
        )
        return (
            settings.origin_x + math.cos(angle) * settings.radius,
            settings.origin_y + math.sin(angle) * settings.radius,
        )
    return settings.origin_x, settings.origin_y


def build_instances(settings: TransformEmitterSettings) -> list[EffectInstance]:
    """Create deterministic emitted instances without rendering pixels."""
    settings.validate()
    return [
        EffectInstance(
            source_asset_id=settings.source_asset_id,
            birth_frame=settings.start_frame + index * settings.emission_interval,
            lifetime=settings.lifetime,
            distribution_index=index,
            random_seed=settings.seed + index,
            origin_x=distribution_origin(settings, index)[0],
            origin_y=distribution_origin(settings, index)[1],
        )
        for index in range(settings.instance_count)
    ]


def normalized_lifetime(instance: EffectInstance, frame_index: int) -> float | None:
    """Return 0..1 while alive, otherwise None."""
    age = frame_index - instance.birth_frame
    if age < 0 or age >= instance.lifetime:
        return None
    if instance.lifetime == 1:
        return 0.0
    return age / (instance.lifetime - 1)
