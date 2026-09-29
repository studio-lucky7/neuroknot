import numpy as np
import pytest

from neuroknot_ml.evaluate import (
    calibration_in_the_large,
    expected_calibration_error,
    reliability_table,
    score,
)


@pytest.fixture(scope="module")
def calibrated():
    """P(정답) = p 그대로 뽑은, 완벽히 보정된 가짜 예측."""
    rng = np.random.default_rng(0)
    p = rng.random(200_000)
    y = rng.random(200_000) < p
    return y, p


def test_perfectly_calibrated_ece_is_near_zero(calibrated):
    y, p = calibrated
    assert expected_calibration_error(y, p) < 0.01


def test_constant_prediction_at_true_rate_is_calibrated():
    rng = np.random.default_rng(1)
    y = rng.random(100_000) < 0.7
    assert expected_calibration_error(y, np.full(len(y), 0.7)) < 0.01


@pytest.mark.parametrize("shift", [0.15, -0.15])
def test_biased_prediction_increases_ece(calibrated, shift):
    y, p = calibrated
    biased = np.clip(p + shift, 0.0, 1.0)
    assert expected_calibration_error(y, biased) > 0.1
    assert expected_calibration_error(y, biased) > expected_calibration_error(y, p) + 0.1


def test_overconfident_prediction_increases_ece(calibrated):
    y, p = calibrated
    sharpened = np.where(p > 0.5, np.minimum(1.0, p + 0.2), np.maximum(0.0, p - 0.2))
    assert expected_calibration_error(y, sharpened) > 0.1


def test_reliability_table_shape_and_counts(calibrated):
    y, p = calibrated
    table = reliability_table(y, p, n_bins=10)
    assert len(table) == 10
    assert table["count"].sum() == len(p)
    filled = table[table["count"] > 0]
    assert ((filled["mean_pred"] >= filled["bin_lo"]) & (filled["mean_pred"] <= filled["bin_hi"])).all()


def test_edge_probabilities_go_to_end_bins():
    table = reliability_table([0, 1], [0.0, 1.0], n_bins=10)
    assert table["count"].iloc[0] == 1 and table["count"].iloc[-1] == 1


def test_calibration_in_the_large_detects_overprediction():
    res = calibration_in_the_large([1, 0, 0, 0], [0.5, 0.5, 0.5, 0.5])
    assert res["mean_actual"] == 0.25 and res["diff"] == pytest.approx(0.25)


def test_score_includes_ece(calibrated):
    y, p = calibrated
    assert score(y, p)["ece"] == pytest.approx(expected_calibration_error(y, p))
