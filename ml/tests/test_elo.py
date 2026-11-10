import pandas as pd
import pytest

from neuroknot_ml.elo import DEFAULT_LEVEL_PRIOR, EloModel, KSchedule


def make_model():
    m = EloModel()
    m.register_user("u1", "cruising")
    m.register_item("q1", "fact", 3)
    return m


def test_correct_raises_user_and_lowers_item():
    m = make_model()
    theta, b = m.user_rating("u1", "fact"), m.item_difficulty("q1")
    m.update("u1", "q1", True)
    assert m.user_rating("u1", "fact") > theta
    assert m.item_difficulty("q1") < b


def test_wrong_lowers_user_and_raises_item():
    m = make_model()
    theta, b = m.user_rating("u1", "fact"), m.item_difficulty("q1")
    m.update("u1", "q1", False)
    assert m.user_rating("u1", "fact") < theta
    assert m.item_difficulty("q1") > b


def test_update_only_touches_that_skill():
    m = make_model()
    before = m.user_rating("u1", "vocab")
    m.update("u1", "q1", True)
    assert m.user_rating("u1", "vocab") == before


def test_onboarding_prior_is_initial_rating():
    m = EloModel()
    for level, prior in DEFAULT_LEVEL_PRIOR.items():
        m.register_user(level, level)
        assert m.user_rating(level, "fact") == prior
    assert m.user_rating("unknown", "fact") == 0.0


def test_register_items_without_difficulty_column():
    m = EloModel()
    m.register_items(pd.DataFrame({"item_id": ["q1"], "skill": ["fact"]}))

    assert m.item_difficulty("q1") == 0.0


@pytest.mark.parametrize("missing", [None, float("nan"), pd.NA], ids=["None", "NaN", "pd.NA"])
def test_register_items_with_missing_difficulty(missing):
    m = EloModel()
    items = pd.DataFrame(
        {"item_id": ["q1"], "skill": ["fact"], "difficulty": pd.Series([missing], dtype=object)}
    )
    m.register_items(items)

    assert m.item_difficulty("q1") == 0.0


def test_register_items_with_mixed_difficulties():
    m = EloModel()
    m.register_items(
        pd.DataFrame({"item_id": ["q1", "q2", "q3"], "skill": ["fact"] * 3, "difficulty": [1, None, 5]})
    )

    assert [m.item_difficulty(item_id) for item_id in ("q1", "q2", "q3")] == [-1.6, 0.0, 1.6]


def test_estimate_theta_without_items_uses_onboarding_prior():
    m = EloModel()
    m.register_user("u1", "cruising")

    assert m.estimate_theta("u1") == DEFAULT_LEVEL_PRIOR["cruising"]


def test_estimate_theta_without_items_for_unregistered_user():
    assert EloModel().estimate_theta("unknown") == 0.0


def test_estimate_theta_averages_distinct_registered_skills():
    m = make_model()
    m.register_item("q2", "fact", 4)
    m.register_item("q3", "vocab", 2)
    m.update("u1", "q1", True)
    fact_rating = m.user_rating("u1", "fact")
    vocab_rating = m.user_rating("u1", "vocab")

    assert fact_rating != vocab_rating
    assert m.estimate_theta("u1", skill="fact") == fact_rating
    assert m.estimate_theta("u1") == pytest.approx((fact_rating + vocab_rating) / 2)


def test_k_shrinks_with_attempts():
    k = KSchedule(k0=0.8, decay=0.1, k_min=0.1)
    values = [k(n) for n in range(200)]
    assert all(a >= b for a, b in zip(values, values[1:]))
    assert values[0] == 0.8 and values[-1] == 0.1


def test_unregistered_item_raises():
    with pytest.raises(KeyError):
        EloModel().predict("u1", "nope")
