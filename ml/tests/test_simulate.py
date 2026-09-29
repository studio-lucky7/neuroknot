import pandas as pd
import pytest

from neuroknot_ml.simulate import ONBOARDING_LEVELS, SimulationConfig, difficulty_to_stars, simulate
from neuroknot_ml.skills import SKILLS

SMALL = dict(n_users=20, n_items=40, min_attempts=5, max_attempts=15)


def test_same_seed_is_reproducible():
    a = simulate(SimulationConfig(seed=7, **SMALL))
    b = simulate(SimulationConfig(seed=7, **SMALL))
    pd.testing.assert_frame_equal(a.attempts, b.attempts)
    pd.testing.assert_frame_equal(a.users, b.users)
    pd.testing.assert_frame_equal(a.user_skills, b.user_skills)
    pd.testing.assert_frame_equal(a.items, b.items)


def test_different_seed_differs():
    a = simulate(SimulationConfig(seed=1, **SMALL))
    b = simulate(SimulationConfig(seed=2, **SMALL))
    assert not a.attempts.equals(b.attempts)


def test_attempts_schema_and_values():
    sim = simulate(SimulationConfig(seed=0, **SMALL))
    a = sim.attempts
    assert list(a.columns) == ["user_id", "item_id", "skill", "difficulty", "is_correct", "timestamp"]
    assert a["skill"].isin(SKILLS).all()
    assert a["difficulty"].between(1, 5).all()
    assert a["timestamp"].is_monotonic_increasing
    assert not a.duplicated(["user_id", "item_id"]).any()
    assert sim.users["onboarding_level"].isin(ONBOARDING_LEVELS).all()


def test_learning_effect_raises_theta():
    sim = simulate(SimulationConfig(seed=0, learning_rate=0.05, **SMALL))
    assert (sim.user_skills["theta_final"] >= sim.user_skills["theta_initial"]).all()
    no_learn = simulate(SimulationConfig(seed=0, learning_rate=0.0, **SMALL))
    assert (no_learn.user_skills["theta_final"] == no_learn.user_skills["theta_initial"]).all()


def test_difficulty_to_stars_is_monotonic():
    assert list(difficulty_to_stars([-3.0, -1.0, 0.0, 1.0, 3.0])) == [1, 2, 3, 4, 5]


ADAPTIVE = dict(n_users=60, n_items=120, min_attempts=20, max_attempts=40, seed=5)


def test_adaptive_same_seed_is_reproducible():
    a = simulate(SimulationConfig(selection="adaptive", **ADAPTIVE))
    b = simulate(SimulationConfig(selection="adaptive", **ADAPTIVE))
    pd.testing.assert_frame_equal(a.attempts, b.attempts)


def test_adaptive_keeps_schema_and_no_repeats():
    a = simulate(SimulationConfig(selection="adaptive", **ADAPTIVE)).attempts
    assert list(a.columns) == ["user_id", "item_id", "skill", "difficulty", "is_correct", "timestamp"]
    assert a["timestamp"].is_monotonic_increasing
    assert not a.duplicated(["user_id", "item_id"]).any()


def test_adaptive_shares_everything_but_item_choice_with_random():
    rnd = simulate(SimulationConfig(selection="random", **ADAPTIVE))
    ada = simulate(SimulationConfig(selection="adaptive", **ADAPTIVE))
    pd.testing.assert_frame_equal(rnd.users, ada.users)
    pd.testing.assert_frame_equal(rnd.items, ada.items)
    pd.testing.assert_series_equal(rnd.attempts["timestamp"], ada.attempts["timestamp"])
    pd.testing.assert_series_equal(rnd.attempts["user_id"], ada.attempts["user_id"])
    assert not rnd.attempts["item_id"].equals(ada.attempts["item_id"])


def test_adaptive_pulls_accuracy_toward_target():
    rnd = simulate(SimulationConfig(selection="random", **ADAPTIVE)).attempts
    ada = simulate(SimulationConfig(selection="adaptive", **ADAPTIVE)).attempts
    assert abs(ada["is_correct"].mean() - 0.7) < 0.1
    assert ada.groupby("user_id")["is_correct"].mean().std() < rnd.groupby("user_id")["is_correct"].mean().std()


def test_unknown_selection_raises():
    with pytest.raises(ValueError):
        simulate(SimulationConfig(selection="greedy", **SMALL))
