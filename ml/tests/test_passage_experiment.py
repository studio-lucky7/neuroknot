import pandas as pd
import pytest

from neuroknot_ml.passage_experiment import POLICIES, compare_passage_policies, summarize_policy


def test_comparison_reuses_schedule_and_is_reproducible_per_user():
    kwargs = {"n_users": 5, "n_passages": 7, "rounds": 4, "seed": 12}
    first = compare_passage_policies(**kwargs)
    second = compare_passage_policies(**kwargs)

    assert tuple(first) == POLICIES
    for name, attempts in first.items():
        pd.testing.assert_frame_equal(attempts, second[name])
        pd.testing.assert_frame_equal(attempts[["user_id", "timestamp"]], first["random"][["user_id", "timestamp"]])
        assert len(attempts) == 5 * 4 * 3
        assert not attempts.duplicated(["user_id", "item_id"]).any()
        assert (attempts.groupby(["user_id", "passage_id"])["skill"].nunique() == 3).all()
        assert (attempts.groupby("user_id")["passage_id"].nunique() == 4).all()
        assert attempts["p_pred"].between(0, 1).all()
        assert summarize_policy(attempts)["n"] == len(attempts)


def test_comparison_supports_catalog_exhaustion_on_final_round():
    runs = compare_passage_policies(n_users=2, n_passages=2, rounds=2)

    assert all(len(attempts) == 12 for attempts in runs.values())
    with pytest.raises(ValueError, match="rounds"):
        compare_passage_policies(n_users=2, n_passages=2, rounds=3)
