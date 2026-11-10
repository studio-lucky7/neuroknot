import numpy as np
import pytest

from neuroknot_ml.baselines import GlobalMeanBaseline, UserMeanBaseline
from neuroknot_ml.elo import EloModel
from neuroknot_ml.evaluate import run_online, score
from neuroknot_ml.simulate import SimulationConfig, simulate


@pytest.fixture(scope="module")
def sim():
    return simulate(SimulationConfig(n_users=30, n_items=60, min_attempts=10, max_attempts=30, seed=3))


def make_elo(sim):
    m = EloModel()
    m.register_users(sim.users)
    m.register_items(sim.items)
    return m


@pytest.mark.parametrize("factory", [lambda s: GlobalMeanBaseline(), lambda s: UserMeanBaseline(), make_elo])
def test_online_predictions_are_probabilities(sim, factory):
    pred = run_online(factory(sim), sim.attempts)
    assert pred["p_pred"].between(0.0, 1.0).all()
    assert np.isfinite(pred["p_pred"]).all()


def test_elo_probability_stays_in_range_under_extreme_streaks():
    m = EloModel()
    m.register_item("easy", "fact", 1)
    m.register_item("hard", "fact", 5)
    for _ in range(500):
        m.update("u1", "hard", True)
        m.update("u2", "easy", False)
    for user in ("u1", "u2"):
        for item in ("easy", "hard"):
            assert 0.0 <= m.predict(user, item) <= 1.0


def test_score_metrics_are_finite_for_extreme_predictions():
    s = score([0, 1, 1, 0], [0.0, 1.0, 1.0, 0.0])
    assert s["auc"] == 1.0
    assert np.isfinite(s["log_loss"]) and 0.0 <= s["brier"] <= 1.0
