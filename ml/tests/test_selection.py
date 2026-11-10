import pytest

from neuroknot_ml.elo import EloModel
from neuroknot_ml.selection import PassageCandidate, PassageQuestion, SelectionConfig, select_passage


def passage(passage_id, skills=("fact", "inference", "vocab")):
    return PassageCandidate(passage_id, tuple(PassageQuestion(f"{passage_id}-{s}", s) for s in skills))


class FixedModel:
    def __init__(self, *groups):
        self.probabilities = {
            q.item_id: p for candidate, probabilities in groups for q, p in zip(candidate.questions, probabilities)
        }

    def predict(self, user_id, item_id):
        return self.probabilities[item_id]


def test_maps_generation_shape_and_external_item_ids():
    generated = {
        "passage_id": "p1",
        "prompt_version": "quiz_v2",
        "model": "example",
        "quiz": {"difficulty_hint": 4, "questions": [{"skill": s} for s in ("fact", "inference", "vocab")]},
    }
    candidate = PassageCandidate.from_generated(generated, ["p1-v2:1", "p1-v2:2", "p1-v2:3"])

    assert candidate.passage_id == "p1"
    assert candidate.difficulty_hint == 4
    assert candidate.questions[1] == PassageQuestion("p1-v2:2", "inference")


def test_uses_all_three_probabilities_instead_of_only_their_mean():
    even, uneven = passage("even"), passage("uneven")
    model = FixedModel((even, (0.65, 0.75, 0.7)), (uneven, (0.1, 1.0, 1.0)))
    result = select_passage(model, "u1", [uneven, even])

    assert result.passage == even
    assert result.scores.probabilities == (0.65, 0.75, 0.7)
    assert result.scores.mean_probability == pytest.approx(0.7)
    assert result.scores.target_distance == pytest.approx(0.1 / 3)
    assert result.reasons == ("target_fit",)


def test_elo_difficulty_changes_selection_without_mutating_model():
    easy, hard = passage("easy"), passage("hard")
    model = EloModel()
    for candidate, stars in ((easy, 2), (hard, 5)):
        for q in candidate.questions:
            model.register_item(q.item_id, q.skill, stars)
    before = model.to_state()

    result = select_passage(model, "unknown", [hard, easy])

    assert result.passage == easy
    assert result.scores.probabilities == tuple(model.predict("unknown", q.item_id) for q in easy.questions)
    assert model.to_state() == before


def test_skips_seen_passages_and_any_seen_item_and_deduplicates():
    seen, overlap, fresh = (passage(p) for p in ("seen", "overlap", "fresh"))
    model = FixedModel((fresh, (0.5, 0.6, 0.7)))
    result = select_passage(
        model,
        "u1",
        [seen, overlap, fresh, fresh],
        seen_passage_ids={"seen"},
        seen_item_ids={overlap.questions[0].item_id},
    )

    assert result.passage == fresh
    assert (result.eligible_count, result.excluded_seen, result.excluded_unregistered) == (1, 2, 0)


def test_reports_empty_or_unregistered_catalog():
    model = FixedModel()
    empty = select_passage(model, "u1", [])
    exhausted = select_passage(model, "u1", [passage("unknown")])

    assert empty.passage is empty.scores is None
    assert empty.reasons == ("empty_catalog",)
    assert exhausted.passage is exhausted.scores is None
    assert exhausted.reasons == ("no_eligible_passage",)
    assert exhausted.excluded_unregistered == 1


def test_ties_are_reproducible_per_user_regardless_of_candidate_order():
    candidates = [passage(str(i)) for i in range(8)]
    model = FixedModel(*((candidate, (0.7, 0.7, 0.7)) for candidate in candidates))
    users = [f"u{i}" for i in range(8)]
    choices = [select_passage(model, user, candidates).passage for user in users]

    assert choices == [select_passage(model, user, reversed(candidates)).passage for user in users]
    assert len(set(choices)) > 1


def test_rejects_invalid_catalog_and_predictions():
    first = passage("p1")
    with pytest.raises(ValueError, match="distinct"):
        PassageCandidate("bad", (first.questions[0],) * 3)
    with pytest.raises(ValueError, match="conflicting"):
        select_passage(FixedModel(), "u1", [first, passage("p1", ("fact", "inference", "main_idea"))])
    with pytest.raises(ValueError, match="invalid predicted probability"):
        select_passage(FixedModel((first, (0.6, float("nan"), 0.7))), "u1", [first])
    with pytest.raises(ValueError, match="target_p"):
        SelectionConfig(target_p=0)
