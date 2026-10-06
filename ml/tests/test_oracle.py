import numpy as np

from neuroknot_ml.baselines import OracleModel
from neuroknot_ml.evaluate import run_online, theta_recovery
from neuroknot_ml.simulate import SimulationConfig, simulate


def test_oracle_tracks_true_theta_exactly():
    sim = simulate(SimulationConfig(n_users=20, n_items=40, min_attempts=5, max_attempts=15, learning_rate=0.05, seed=1))
    oracle = OracleModel.from_simulation(sim)
    pred = run_online(oracle, sim.attempts)
    assert pred["p_pred"].between(0.0, 1.0).all()
    final = [oracle.estimate_theta(u, s) for u, s in zip(sim.user_skills["user_id"], sim.user_skills["skill"])]
    np.testing.assert_allclose(final, sim.user_skills["theta_final"])
    assert theta_recovery(oracle, sim.user_skills)["spearman_skill"] > 0.999
