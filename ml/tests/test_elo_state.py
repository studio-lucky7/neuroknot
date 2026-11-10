import json

import pytest

from neuroknot_ml.elo import EloModel, KSchedule


def json_round_trip(model):
    return EloModel.from_state(json.loads(json.dumps(model.to_state(), allow_nan=False)))


def make_model():
    model = EloModel(
        level_prior={"beginner": -0.6, "advanced": 0.9},
        star_prior={2: -0.4, 4: 0.7},
        user_k=KSchedule(k0=0.65, decay=0.25, k_min=0.08),
        item_k=KSchedule(k0=0.3, decay=0.2, k_min=0.04),
    )
    model.register_user("u1", "beginner")
    model.register_user("u2", "advanced")
    model.register_user("idle", "advanced")
    model.register_item("q1", "fact", 2)
    model.register_item("q2", "vocab", 4)
    model.register_item("q3", "fact")
    return model


def test_empty_model_round_trip():
    model = EloModel()
    restored = json_round_trip(model)

    state = restored.to_state()
    assert state == model.to_state()
    assert state["version"] == 1
    assert state["user_prior"] == state["user_skills"] == state["items"] == {}
    assert restored.estimate_theta("unknown") == 0.0


def test_round_trip_preserves_active_state_and_priors():
    model = make_model()
    model.update("u1", "q1", True)
    model.update("u1", "q2", False)
    model.update("u2", "q1", True)
    model.update("guest", "q1", False)

    restored = json_round_trip(model)
    state = restored.to_state()
    assert state == model.to_state()
    assert state["user_prior"] == {"u1": -0.6, "u2": 0.9, "idle": 0.9}
    assert state["user_skills"]["u1"] == {
        "fact": {"theta": model.user_rating("u1", "fact"), "attempts": 1},
        "vocab": {"theta": model.user_rating("u1", "vocab"), "attempts": 1},
    }
    assert state["items"]["q1"] == {"skill": "fact", "difficulty": model.item_difficulty("q1"), "attempts": 3}
    assert state["items"]["q3"] == {"skill": "fact", "difficulty": 0.0, "attempts": 0}
    assert restored.user_rating("idle", "fact") == 0.9
    assert restored.user_rating("u2", "vocab") == 0.9
    assert restored.user_rating("guest", "vocab") == 0.0
    for user_id in ("u1", "u2", "idle", "guest"):
        for item_id in ("q1", "q2", "q3"):
            assert restored.predict(user_id, item_id) == model.predict(user_id, item_id)

    restored.register_user("new", "beginner")
    restored.register_item("new_q", "vocab", 4)
    assert restored.user_rating("new", "vocab") == -0.6
    assert restored.item_difficulty("new_q") == 0.7


def test_five_then_restore_matches_ten_continuous_updates():
    attempts = [
        ("u1", "q1", True),
        ("u2", "q2", False),
        ("u1", "q2", True),
        ("u2", "q1", False),
        ("u1", "q1", True),
        ("u1", "q1", False),
        ("u2", "q2", True),
        ("u1", "q2", False),
        ("u2", "q1", True),
        ("u1", "q1", True),
    ]
    continuous, resumed = make_model(), make_model()
    continuous_predictions = [continuous.update(*attempt) for attempt in attempts]
    resumed_predictions = [resumed.update(*attempt) for attempt in attempts[:5]]
    resumed = json_round_trip(resumed)
    resumed_predictions.extend(resumed.update(*attempt) for attempt in attempts[5:])

    assert resumed_predictions == continuous_predictions
    assert resumed.to_state() == continuous.to_state()
    for user_id in ("u1", "u2"):
        for item_id in ("q1", "q2"):
            assert resumed.predict(user_id, item_id) == continuous.predict(user_id, item_id)


def test_snapshot_and_models_do_not_share_mutable_state():
    model = make_model()
    model.update("u1", "q1", True)
    snapshot = model.to_state()
    restored = EloModel.from_state(snapshot)
    expected = restored.to_state()

    model.update("u1", "q1", False)
    assert snapshot == expected
    snapshot["config"]["level_prior"]["beginner"] = 100.0
    snapshot["user_prior"]["idle"] = 100.0
    snapshot["user_skills"]["u1"]["fact"]["theta"] = 100.0
    snapshot["items"]["q1"]["difficulty"] = 100.0

    assert restored.to_state() == expected


def test_registered_prior_survives_config_change():
    model = make_model()
    model.level_prior["beginner"] = -0.1

    restored = json_round_trip(model)
    restored.register_user("new", "beginner")

    assert restored.user_rating("u1", "fact") == -0.6
    assert restored.user_rating("new", "fact") == -0.1


@pytest.mark.parametrize("version", [0, 2, True, 1.0, "1"])
def test_invalid_version_is_rejected(version):
    state = EloModel().to_state()
    state["version"] = version

    with pytest.raises(ValueError, match=r"state\.version"):
        EloModel.from_state(state)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("items",), []),
        (("config", "star_prior"), {"02": 0.0}),
        (("config", "star_prior"), {2: 0.0}),
        (("config", "level_prior", "beginner"), float("inf")),
        (("config", "user_k", "k0"), True),
        (("config", "user_k", "decay"), -0.1),
        (("config", "item_k", "k_min"), float("nan")),
        (("user_prior", "u1"), "-0.6"),
        (("user_skills", "u1", "fact", "theta"), float("nan")),
        (("user_skills", "u1", "fact", "attempts"), -1),
        (("items", "q1", "skill"), None),
        (("items", "q1", "difficulty"), float("-inf")),
        (("items", "q1", "attempts"), 1.0),
        (("items", "q1", "attempts"), False),
    ],
)
def test_invalid_field_value_is_rejected(path, value):
    model = make_model()
    model.update("u1", "q1", True)
    state = model.to_state()
    record = state
    for key in path[:-1]:
        record = record[key]
    record[path[-1]] = value

    with pytest.raises(ValueError) as error:
        EloModel.from_state(state)
    assert ".".join(path) in str(error.value)


def test_missing_and_unexpected_fields_are_rejected():
    state = make_model().to_state()
    del state["items"]["q1"]["attempts"]
    state["items"]["q1"]["count"] = 0

    with pytest.raises(ValueError, match=r"items\.q1.*missing fields.*attempts.*unexpected fields.*count"):
        EloModel.from_state(state)
