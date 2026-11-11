import json
from copy import deepcopy

import pytest

from scripts.diagnose_difficulty import diagnose, load_inputs


def test_synthetic_diagnostic_reproduces_equal_hint_probabilities_and_hash_ties():
    source, fixtures = load_inputs()
    before = deepcopy(fixtures)
    report = diagnose(fixtures, source=source)

    assert report["source"] == "synthetic_test_fixtures"
    assert sum(row["count"] for row in report["difficulty_hints"].values()) == len(fixtures)
    assert report["counterfactual_uniform_hint_2"]["cruising"]["initial_probabilities"]["mean"] == pytest.approx(0.6224593312)
    for level in report["counterfactual_uniform_hint_2"].values():
        assert level["top_rank_ties"] == len(fixtures)
        assert level["hash_decides_winner"]
        assert level["initial_probabilities"]["min"] == level["initial_probabilities"]["max"]
    assert fixtures == before
    assert report == diagnose(list(reversed(fixtures)), source=source)
    json.dumps(report, allow_nan=False)
    near_report = diagnose(fixtures, source=source, near_tolerance=1.0)
    for level in near_report["baseline_hint_only"].values():
        assert level["near_pair_fraction"] == 1.0
        assert not level["hash_decides_winner"]


def test_supplied_outputs_are_validated_against_source_passages(tmp_path):
    _, fixtures = load_inputs()
    outputs, passages = tmp_path / "outputs", tmp_path / "passages"
    outputs.mkdir()
    passages.mkdir()
    fixture = fixtures[0]
    # Matching uses stored passage ID, so filenames need not equal IDs.
    output = outputs / "output.json"
    output.write_text(json.dumps(fixture["generated"]), encoding="utf-8")
    (passages / "source.json").write_text(json.dumps(fixture["passage"]), encoding="utf-8")
    source, loaded = load_inputs(outputs, passages)
    report = diagnose(loaded, source=source)

    assert source == "supplied_generation_outputs"
    assert not report["baseline_hint_only"]["cruising"]["hash_decides_winner"]
    assert report["baseline_hint_only"]["cruising"]["near_pair_fraction"] is None
    invalid = deepcopy(fixture["generated"])
    invalid["quiz"]["questions"][0]["evidence"] = "This evidence is missing from the passage."
    output.write_text(json.dumps(invalid), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid quiz"):
        load_inputs(outputs, passages)


@pytest.mark.parametrize("tolerance", [-0.1, float("nan"), float("inf")])
def test_invalid_diagnostic_tolerance_is_rejected(tolerance):
    source, fixtures = load_inputs()
    with pytest.raises(ValueError, match="tolerance"):
        diagnose(fixtures, source=source, near_tolerance=tolerance)


def test_missing_sources_and_invalid_hypothetical_stars_are_rejected(tmp_path):
    with pytest.raises(ValueError, match="both"):
        load_inputs(tmp_path)
    with pytest.raises(ValueError, match="no Generation"):
        load_inputs(tmp_path, tmp_path)
    source, fixtures = load_inputs()
    with pytest.raises(ValueError, match="three integer"):
        diagnose(fixtures, source=source, item_stars=(True, 3, 5))
