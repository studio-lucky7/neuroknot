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


def test_k_shrinks_with_attempts():
    k = KSchedule(k0=0.8, decay=0.1, k_min=0.1)
    values = [k(n) for n in range(200)]
    assert all(a >= b for a, b in zip(values, values[1:]))
    assert values[0] == 0.8 and values[-1] == 0.1


def test_unregistered_item_raises():
    with pytest.raises(KeyError):
        EloModel().predict("u1", "nope")
