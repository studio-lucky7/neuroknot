"""Summarize initial priors and selection ties without learning or changing policy."""

import argparse
import json
import sys
from collections import Counter
from copy import deepcopy
from itertools import combinations
from math import isfinite
from pathlib import Path
from statistics import fmean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "gen"))

from neuroknot_gen.schemas import GeneratedQuiz, Passage  # noqa: E402
from neuroknot_gen.validate import check_quiz  # noqa: E402
from neuroknot_ml.elo import DEFAULT_LEVEL_PRIOR, EloModel  # noqa: E402
from neuroknot_ml.selection import PassageCandidate, select_passage  # noqa: E402
from neuroknot_ml.service_workflow import PredictionService  # noqa: E402


def load_inputs(generated_dir=None, passages_dir=None):
    if (generated_dir is None) != (passages_dir is None):
        raise ValueError("provide both --generated-dir and --passages-dir")
    if generated_dir is None:
        fixtures = json.loads((ROOT / "fixtures/service_workflow.json").read_text(encoding="utf-8"))
        source = "synthetic_test_fixtures"
    else:
        paths = sorted(Path(generated_dir).glob("*.json"))
        if not paths:
            raise ValueError("no Generation output JSON files found")
        fixtures = []
        for path in paths:
            generated = json.loads(path.read_text(encoding="utf-8"))
            GeneratedQuiz.model_validate(generated)
            # Match by stored ID, without treating external IDs as filesystem paths.
            fixtures.append({"generated": generated, "output_file": path.name, "passage": None})
        passages = {}
        for path in sorted(Path(passages_dir).glob("*.json")):
            passage = Passage.model_validate_json(path.read_text(encoding="utf-8"))
            if passage.id in passages:
                raise ValueError(f"duplicate passage ID: {passage.id}")
            passages[passage.id] = passage.model_dump(mode="json")
        for fixture in fixtures:
            passage_id = fixture["generated"]["passage_id"]
            if passage_id not in passages:
                raise ValueError(f"missing source passage: {passage_id}")
            fixture["passage"] = passages[passage_id]
        source = "supplied_generation_outputs"
    ids = set()
    for fixture in fixtures:
        generated = GeneratedQuiz.model_validate(fixture["generated"])
        passage = Passage.model_validate(fixture["passage"])
        problems = check_quiz(generated.quiz, passage)
        if generated.passage_id != passage.id or problems:
            raise ValueError(f"invalid quiz for {passage.id}: {problems}")
        if passage.id in ids:
            raise ValueError("provide one published quiz per passage for this diagnostic")
        ids.add(passage.id)
        # Also check the three distinct, supported skills required by Prediction.
        PassageCandidate.from_generated(generated.model_dump(mode="json"), ["slot-0", "slot-1", "slot-2"])
    return source, fixtures


def _distribution(values):
    return {"count": len(values), "unique_values": len(set(values)), "min": min(values), "mean": fmean(values), "max": max(values)}


def _scenario(fixtures, *, item_stars=None, uniform_hint=None, near_tolerance=0.01):
    service = PredictionService()
    candidates = []
    for fixture in fixtures:
        generated = deepcopy(fixture["generated"])
        if uniform_hint is not None:
            generated["quiz"]["difficulty_hint"] = uniform_hint
        quiz = service.register_quiz(
            generated, quiz_version="diagnostic-v1", passage_body=fixture["passage"]["body"],
            item_difficulties=None if item_stars is None else dict(enumerate(item_stars)),
        )
        candidates.append(PassageCandidate.from_generated(generated, [q["item_id"] for q in quiz["questions"]]))
    # Export through the public boundary. No updates or exposures are performed.
    model = EloModel.from_state(service.checkpoint()["history"]["model"])
    levels = {}
    for level in DEFAULT_LEVEL_PRIOR:
        user_id = f"diagnostic:{level}"
        model.register_user(user_id, level)
        scored = [select_passage(model, user_id, [candidate]).scores for candidate in candidates]
        pairs = list(combinations(scored, 2))
        selected = select_passage(model, user_id, candidates)
        best_key = (selected.scores.total_score, selected.scores.target_distance)
        top_ties = sum((score.total_score, score.target_distance) == best_key for score in scored)
        near = sum(abs(a.total_score - b.total_score) <= near_tolerance for a, b in pairs)
        exact = sum(a.total_score == b.total_score for a, b in pairs)
        levels[level] = {
            "initial_probabilities": _distribution([p for score in scored for p in score.probabilities]),
            "candidate_scores": _distribution([score.total_score for score in scored]),
            "candidate_pair_count": len(pairs),
            "equal_score_pairs": exact,
            "near_score_pairs_including_equal": near,
            "near_pair_fraction": near / len(pairs) if pairs else None,
            "top_rank_ties": top_ties,
            "hash_decides_winner": top_ties > 1,
            "selected_passage_id": selected.passage.passage_id,
        }
    return levels


def diagnose(fixtures, *, source, item_stars=(1, 3, 5), near_tolerance=0.01):
    if not fixtures:
        raise ValueError("at least one validated quiz is required")
    if len(item_stars) != 3 or any(type(star) is not int or not 1 <= star <= 5 for star in item_stars):
        raise ValueError("provide three integer item stars from 1 to 5")
    if not isfinite(near_tolerance) or near_tolerance < 0:
        raise ValueError("near tolerance must be finite and nonnegative")
    hints = Counter(f["generated"]["quiz"]["difficulty_hint"] for f in fixtures)
    baseline = _scenario(fixtures, near_tolerance=near_tolerance)
    overrides = _scenario(fixtures, item_stars=item_stars, near_tolerance=near_tolerance)
    return {
        "source": source,
        "diagnostic_quiz_version": "diagnostic-v1",
        "input_passage_ids": sorted(f["passage"]["id"] for f in fixtures),
        "passage_count": len(fixtures),
        "skill_validation": "Generation schema, evidence checks and three distinct Prediction skills",
        "difficulty_hints": {str(star): {"count": hints[star], "fraction": hints[star] / len(fixtures)} for star in range(1, 6)},
        "near_tolerance": near_tolerance,
        "baseline_hint_only": baseline,
        "illustrative_item_stars_by_slot": list(item_stars),
        "illustrative_item_stars": overrides,
        "selection_changed_by_illustrative_stars": {
            level: baseline[level]["selected_passage_id"] != overrides[level]["selected_passage_id"]
            for level in DEFAULT_LEVEL_PRIOR
        },
        "counterfactual_uniform_hint_2": _scenario(fixtures, uniform_hint=2, near_tolerance=near_tolerance),
        "limitations": [
            "Initial, unexposed users only; no answer events or learned skill differences.",
            "Item stars and uniform hint 2 are hypothetical sensitivity checks, not calibrated difficulty labels.",
            "The supplied file label records input provenance, not independent verification of how it was generated.",
            "Pair frequencies describe this catalog only; near scores do not activate the exact hash tie breaker.",
            "No observed accuracy, calibration, learning benefit or production data quality can be inferred.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generated-dir", type=Path)
    parser.add_argument("--passages-dir", type=Path)
    parser.add_argument("--item-stars", type=int, choices=range(1, 6), nargs=3, default=(1, 3, 5))
    parser.add_argument("--near-tolerance", type=float, default=0.01)
    args = parser.parse_args()
    source, fixtures = load_inputs(args.generated_dir, args.passages_dir)
    report = diagnose(fixtures, source=source, item_stars=args.item_stars, near_tolerance=args.near_tolerance)
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
