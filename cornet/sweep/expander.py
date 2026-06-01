"""Parameter sweep expansion for CORNET unified configs."""

from __future__ import annotations

import copy
import itertools
from typing import Any

from cornet.config.schema import UnifiedConfig


def _set_keypath(obj: Any, keypath: str, value: Any) -> None:
    parts = keypath.split(".")
    current = obj
    for part in parts[:-1]:
        current = getattr(current, part)
    setattr(current, parts[-1], value)


def expand_sweep(config: UnifiedConfig) -> list[UnifiedConfig]:
    """Expand `experiment.sweep.axes` into concrete variant configs.

    Returns a single-item list with the original config when no sweep is present.
    """
    sweep = config.experiment.sweep
    if sweep is None or not sweep.axes:
        cfg = copy.deepcopy(config)
        cfg.experiment.name = config.experiment.name or "default"
        return [cfg]

    axes = list(sweep.axes.items())
    combinations = itertools.product(*(values for _, values in axes))

    variants: list[UnifiedConfig] = []
    for combo in combinations:
        for repeat_idx in range(1, sweep.repeats + 1):
            cfg = copy.deepcopy(config)
            label_parts = []
            for (keypath, _values), value in zip(axes, combo):
                _set_keypath(cfg, keypath, value)
                short = keypath.split(".")[-1]
                label_parts.append(f"{short}={value}")

            if len(axes) == 1:
                variant_id = str(combo[0])
            else:
                variant_id = "_".join(label_parts) if label_parts else "default"
            if sweep.repeats > 1:
                variant_id = f"{variant_id}_run{repeat_idx}"

            cfg.experiment.name = variant_id
            cfg.experiment.output_dir = f"{config.experiment.output_dir}/{variant_id}"
            variants.append(cfg)

    return variants
