"""Leakage boundaries, production equivalence, pairing and metric tests."""
import numpy as np
import pandas as pd
import pytest
from research_v2.experiment import (variants, world, model_for, probe, run, predictive,
    summarize, TUNE_SEEDS, VALIDATION_SEEDS)
from neuroknot_ml.passage_experiment import compare_passage_policies


def test_default_research_path_matches_existing_passage_experiment():
    existing = compare_passage_policies(n_users=4, n_passages=8, rounds=4, seed=42, learning_rate=0)
    for name, original in [('v1','prediction_core_v1'), ('random','random')]:
        log = run(variants()[name], 42, users=4, passages=8, rounds=4, return_logs=True)[4]
        assert log.item_id.tolist() == existing[original].item_id.tolist()
        np.testing.assert_array_equal(log.y, existing[original].is_correct.astype(int))
        np.testing.assert_allclose(log.p, existing[original].p_pred, rtol=0, atol=0)


def test_common_bank_never_trains_and_probe_is_read_only():
    source, items, bank, _, heldout = world(11, users=3, passages=8, rounds=4)
    assert set(heldout.item_id).isdisjoint({q.item_id for p in bank for q in p.questions})
    model = model_for(variants()['v1'], source, items, heldout)
    before = model.to_state()
    theta = {(r.user_id,r.skill):r.theta_initial for r in source.user_skills.itertuples()}
    probe(model, 'u0000', theta, heldout, np.zeros(40), 0)
    assert model.to_state() == before
    # Altering simulator truth/unused source outcomes cannot alter model registration.
    source.users['theta'] = 999
    source.user_skills['theta_initial'] = 999
    source.attempts['is_correct'] = False
    items['b'] = 999
    heldout['b'] = 999
    assert model_for(variants()['v1'], source, items, heldout).to_state() == before


def test_common_labels_and_initial_predictions_are_paired():
    runs = [run(variants()[v], 29, users=4, passages=8, rounds=4, return_logs=True) for v in ['v1','no_bonuses']]
    a, b = [r[5].sort_values(['user_id','checkpoint','item_id']).reset_index(drop=True) for r in runs]
    pd.testing.assert_series_equal(a.true_p,b.true_p)
    pd.testing.assert_series_equal(a.y,b.y)
    np.testing.assert_array_equal(a[a.checkpoint==0].p,b[b.checkpoint==0].p)
    assert set(TUNE_SEEDS).isdisjoint(VALIDATION_SEEDS)


def test_expected_brier_decomposition_and_paired_seed_summary():
    f = pd.DataFrame(dict(y=[0,1],p=[.25,.75],true_p=[.25,.75]))
    m = predictive(f)
    assert m['probability_mse'] == 0
    assert m['expected_brier'] == .1875
    frame = pd.DataFrame(dict(variant=['v1','v1','x','x'],seed=[1,2,1,2],loss=[1.,2.,.9,1.9]))
    summary = summarize(frame, paired=True).set_index('variant')
    assert summary.loc['x','mean'] == pytest.approx(-.1)
    assert summary.loc['x','variance'] == pytest.approx(0)
    assert summary.loc['x','n'] == 2


def test_fixed_log_replay_matches_v1_and_ignores_policy_settings():
    from research_v2.replay import replay
    v = variants()
    result = run(v['v1'], 47, users=4, passages=8, rounds=4, return_logs=True)
    for name in ['v1','no_coverage']:
        scores = replay(v[name],47,result[4],users=4,passages=8,rounds=4)
        for n in (0,6,12):
            for metric in ['auc','brier','log_loss','ece','probability_mse']:
                key = f'common_{n}_{metric}'
                assert scores[key] == pytest.approx(result[0][key])
