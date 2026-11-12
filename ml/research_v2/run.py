"""Run from ml: python -m research_v2.run --phase tune|validate|learning"""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import subprocess
from importlib.metadata import version
import pandas as pd
from research_v2.experiment import variants, run, summarize, ABLATIONS, TUNE_SEEDS, VALIDATION_SEEDS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=['tune','validate','learning'], required=True)
    parser.add_argument('--output', type=Path, default=Path('research_v2/artifacts'))
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    all_variants = variants()
    if args.phase == 'tune':
        names, seeds = list(all_variants), TUNE_SEEDS
    else:
        frozen = json.loads((out/'frozen_candidates.json').read_text())
        if frozen['tune_seeds'] != list(TUNE_SEEDS) or set(TUNE_SEEDS)&set(VALIDATION_SEEDS):
            raise ValueError('Invalid seed separation')
        names = list(dict.fromkeys([*ABLATIONS, *frozen['candidates']]))
        seeds = VALIDATION_SEEDS
    rate = .01 if args.phase == 'learning' else 0.
    manifest = dict(phase=args.phase, seeds=seeds, users=60, passages=60, rounds=16,
        heldout_items=40, learning_rate=rate, variants={n: asdict(all_variants[n]) for n in names},
        python=platform.python_version(), dependencies={p:version(p) for p in ['numpy','pandas','scipy','scikit-learn','pytest','pydantic']},
        base_commit='d17ac32', source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('research_v2').glob('*.py')})
    (out/f'{args.phase}_manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    rows, users, theta, items = [], [], [], []
    for seed in seeds:
        for name in names:
            metrics, u, th, it = run(all_variants[name], seed, learning_rate=rate)
            rows.append(dict(variant=name, seed=seed, **metrics))
            for frame, target in [(u,users),(th,theta),(it,items)]:
                target.append(frame.assign(variant=name, seed=seed))
            pd.DataFrame(rows).to_csv(out/f'{args.phase}_seeds.csv', index=False)
            print(f'{args.phase} seed={seed} variant={name}: common Brier={metrics["common_48_brier"]:.5f}', flush=True)
    frame = pd.DataFrame(rows)
    summarize(frame).to_csv(out/f'{args.phase}_summary.csv', index=False)
    summarize(frame, paired=True).to_csv(out/f'{args.phase}_paired.csv', index=False)
    for label, frames in [('users',users),('theta',theta),('items',items)]:
        pd.concat(frames, ignore_index=True).to_csv(out/f'{args.phase}_{label}.csv', index=False)
    if args.phase == 'tune':
        # Predeclared ranking: two best one-factor variants on common probability MSE;
        # also retain best coverage variant, with common MSE as tie-breaker.
        means = frame.groupby('variant').mean(numeric_only=True)
        eligible = means.drop(index=list(ABLATIONS))
        top = eligible.sort_values(['common_48_probability_mse','coverage_gap']).head(2).index.tolist()
        coverage = eligible.sort_values(['coverage_gap','common_48_probability_mse']).index[0]
        frozen = dict(tune_seeds=list(TUNE_SEEDS), validation_seeds=list(VALIDATION_SEEDS),
            rule='Two lowest common_48_probability_mse and lowest coverage_gap among non-ablation one-factor variants',
            candidates=list(dict.fromkeys([*top,coverage])),
            tune_csv_sha256=hashlib.sha256((out/'tune_seeds.csv').read_bytes()).hexdigest())
        (out/'frozen_candidates.json').write_text(json.dumps(frozen, indent=2)+'\n')

if __name__ == '__main__':
    main()
