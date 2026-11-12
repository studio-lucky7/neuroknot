"""Estimator-only check: replay one V1 log without letting candidate models select."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from research_v2.experiment import world, model_for, probe, predictive, run, variants, summarize, VALIDATION_SEEDS


def replay(v, seed, observed, users=60, passages=60, rounds=16):
    source, items, _, _, heldout = world(seed, users, passages, rounds)
    model = model_for(v, source, items, heldout)
    theta = {(r.user_id,r.skill):r.theta_initial for r in source.user_skills.itertuples()}
    noise = np.random.default_rng([seed,72]).random((users,3,len(heldout)))
    indices = {u:i for i,u in enumerate(source.users.user_id)}
    probes = []
    for u in indices:
        probes.extend(probe(model,u,theta,heldout,noise[indices[u],0],0))
    for row in observed.itertuples(index=False):
        model.update(row.user_id,row.item_id,bool(row.y))
        n = row.n_prior+1
        if n in (6,3*rounds):
            probes.extend(probe(model,row.user_id,theta,heldout,noise[indices[row.user_id],1 if n==6 else 2],n))
    common = pd.DataFrame(probes,columns=['user_id','checkpoint','item_id','skill','p','true_p','y'])
    metrics = {}
    for n, frame in common.groupby('checkpoint'):
        metrics.update({f'common_{n}_{k}':v for k,v in predictive(frame).items()})
    metrics['b_train_rmse'] = float(np.sqrt(np.mean([(model.item_difficulty(r.item_id)-r.b)**2 for r in items.itertuples()])))
    metrics['theta_rmse'] = float(np.sqrt(np.mean([(model.user_rating(u,s)-value)**2 for (u,s),value in theta.items()])))
    return metrics


def main():
    out = Path('research_v2/artifacts')
    frozen = json.loads((out/'frozen_candidates.json').read_text())
    names = ['v1',*frozen['candidates']]
    rows = []
    for seed in VALIDATION_SEEDS:
        observed = run(variants()['v1'],seed,return_logs=True)[4]
        for name in names:
            rows.append(dict(variant=name,seed=seed,**replay(variants()[name],seed,observed)))
    frame = pd.DataFrame(rows)
    frame.to_csv(out/'replay_seeds.csv',index=False)
    summarize(frame).to_csv(out/'replay_summary.csv',index=False)
    summarize(frame,paired=True).to_csv(out/'replay_paired.csv',index=False)
    (out/'replay_manifest.json').write_text(json.dumps(dict(seeds=VALIDATION_SEEDS,
        variants=names,reference='v1',learning_rate=0,users=60,passages=60,rounds=16),indent=2)+'\n')

if __name__ == '__main__':
    main()
