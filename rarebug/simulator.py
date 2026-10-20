"""A bounded stochastic toy system, deliberately separate from the planner."""
import random

from .models import Feedback, digest, validate_controls


def execute_simulation(spec: dict, controls: dict, seed: int, trials: int) -> Feedback:
    validate_controls(controls)
    if type(seed) is not int or type(trials) is not int or not 1 <= trials <= 100:
        raise ValueError("Expected an integer seed and 1..100 trials")
    if spec.get("synthetic") is not True or spec.get("version") != 1:
        raise ValueError("Unsupported synthetic simulator")
    mechanism = spec["mechanism"]
    conditions = {
        "race": controls["concurrency"] >= spec.get("min_concurrency", 8)
        and controls["jitter_ms"] >= spec.get("min_jitter_ms", 30),
        "expiry": controls["clock_skew_s"] >= spec.get("min_clock_skew_s", 65),
        "cache": controls["cache_age_s"] >= spec.get("min_cache_age_s", 90),
        "none": False,
    }
    if mechanism not in conditions:
        raise ValueError("Unknown simulator mechanism")
    probability = spec["trigger_probability"] if conditions[mechanism] else spec["background_probability"]
    if type(probability) not in (float, int) or not 0 <= probability <= 1:
        raise ValueError("Invalid simulator probability")
    rng = random.Random(seed)
    for attempt in range(1, trials + 1):
        if rng.random() < probability:
            return Feedback("reproduced", attempt, 1, spec["signature"], seed, digest(spec))
    return Feedback("not_reproduced", trials, 0, None, seed, digest(spec))
