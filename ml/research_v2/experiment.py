"""Research-only evaluation. Production model and selector are used unchanged."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import numpy as np
import pandas as pd
from scipy.stats import t

from neuroknot_ml.elo import EloModel, KSchedule, DEFAULT_LEVEL_PRIOR, DEFAULT_STAR_PRIOR
from neuroknot_ml.evaluate import score
from neuroknot_ml.selection import SelectionConfig, PassageCandidate, PassageQuestion, select_passage
from neuroknot_ml.simulate import SimulationConfig, simulate, sigmoid, difficulty_to_stars
from neuroknot_ml.skills import SKILLS

TUNE_SEEDS = (11, 29, 47)
VALIDATION_SEEDS = (101, 211, 307, 401, 503)

@dataclass(frozen=True)
class Variant:
    name: str
    selection: SelectionConfig = SelectionConfig()
    random: bool = False
    user_k: KSchedule = KSchedule(.8, .1, .1)
    item_k: KSchedule = KSchedule(.4, .1, .05)
    level_scale: float = 1.
    star_scale: float = 1.


def variants():
    base = Variant('v1')
    result = [base, replace(base, name='random', random=True)]
    changes = {
        'no_weakness': dict(weakness_weight=0),
        'no_coverage': dict(coverage_weight=0),
        'no_bonuses': dict(weakness_weight=0, coverage_weight=0),
        # Pure target fit also removes the cold-start target switch.
        'target_only': dict(weakness_weight=0, coverage_weight=0, cold_start_attempts=0),
        'no_cold': dict(cold_start_attempts=0),
        'target_060': dict(target_p=.6), 'target_080': dict(target_p=.8),
        'cold_target_070': dict(cold_start_target_p=.7),
        'cold_target_090': dict(cold_start_target_p=.9),
        'cold_n3': dict(cold_start_attempts=3), 'cold_n12': dict(cold_start_attempts=12),
        'weak_010': dict(weakness_weight=.1), 'weak_040': dict(weakness_weight=.4),
        'coverage_0075': dict(coverage_weight=.075), 'coverage_030': dict(coverage_weight=.3),
    }
    result += [replace(base, name=name, selection=replace(base.selection, **kw)) for name, kw in changes.items()]
    for field, default in [('user_k', base.user_k), ('item_k', base.item_k)]:
        for factor in (.5, 1.5):
            result.append(replace(base, name=f'{field}_scale_{factor}', **{
                field: KSchedule(default.k0 * factor, default.decay, default.k_min * factor)}))
        for decay in (.05, .2):
            result.append(replace(base, name=f'{field}_decay_{decay}', **{
                field: replace(default, decay=decay)}))
    for field in ('level_scale', 'star_scale'):
        for factor in (0., .5, 1.5):
            result.append(replace(base, name=f'{field}_{factor}', **{field: factor}))
    return {v.name: v for v in result}

ABLATIONS = ('v1', 'random', 'target_only', 'no_weakness', 'no_coverage', 'no_bonuses', 'no_cold')


def world(seed, users=60, passages=60, rounds=16):
    """Same training population/catalog/schedule construction as passage_experiment."""
    source = simulate(SimulationConfig(n_users=users, n_items=3*passages,
        min_attempts=3*rounds, max_attempts=3*rounds, seed=seed, learning_rate=0.))
    bank = []
    for index in range(passages):
        skills = [s for i, s in enumerate(SKILLS) if i != index % len(SKILLS)]
        ids = source.items.item_id.iloc[3*index:3*(index+1)]
        bank.append(PassageCandidate(f'p{index:04d}', tuple(PassageQuestion(i, s) for i, s in zip(ids, skills))))
    items = source.items.assign(skill=[q.skill for p in bank for q in p.questions])
    starts = source.attempts.groupby('user_id', sort=False).cumcount() % 3 == 0
    schedule = list(source.attempts.loc[starts, ['user_id', 'timestamp']].itertuples(index=False, name=None))
    # Independent held-out item bank, balanced by skill, never in candidate bank.
    rng = np.random.default_rng([seed, 71])
    b = rng.normal(0, source.config.item_sd, 40)
    heldout = pd.DataFrame(dict(item_id=[f'h{i:03d}' for i in range(40)],
        skill=np.tile(SKILLS, 10), b=b, difficulty=difficulty_to_stars(b)))
    return source, items, bank, schedule, heldout


def model_for(v, source, items, heldout):
    model = EloModel(level_prior={k: x*v.level_scale for k, x in DEFAULT_LEVEL_PRIOR.items()},
        star_prior={k: x*v.star_scale for k, x in DEFAULT_STAR_PRIOR.items()}, user_k=v.user_k, item_k=v.item_k)
    # Explicit whitelist: latent theta/b and source responses cannot reach registration.
    model.register_users(source.users[['user_id', 'onboarding_level']])
    model.register_items(pd.concat([items, heldout])[['item_id', 'skill', 'difficulty']])
    return model


def probe(model, user, theta, heldout, draws, checkpoint):
    """Read-only probe: labels and true probabilities are evaluator-only."""
    rows = []
    for item, draw in zip(heldout.itertuples(index=False), draws):
        true_p = float(sigmoid(theta[user, item.skill] - item.b))
        rows.append((user, checkpoint, item.item_id, item.skill, model.predict(user, item.item_id),
                     true_p, int(draw < true_p)))
    return rows


def predictive(frame):
    result = score(frame.y, frame.p)
    result['probability_mse'] = float(np.mean((frame.p-frame.true_p)**2))
    result['expected_brier'] = float(np.mean((frame.p-frame.true_p)**2 + frame.true_p*(1-frame.true_p)))
    return result


def run(v, seed, users=60, passages=60, rounds=16, learning_rate=0., return_logs=False):
    if users < 1 or not 2 <= rounds <= passages or learning_rate < 0:
        raise ValueError('require users > 0, 2 <= rounds <= passages and learning_rate >= 0')
    source, items, bank, schedule, heldout = world(seed, users, passages, rounds)
    model = model_for(v, source, items, heldout)
    theta = {(r.user_id, r.skill): r.theta_initial for r in source.user_skills.itertuples(index=False)}
    difficulty = dict(zip(items.item_id, items.b))
    counts = {u: dict.fromkeys(SKILLS, 0) for u in source.users.user_id}
    seen = {u: set() for u in counts}
    response = np.random.default_rng([seed, 2]).random((len(schedule), 3))
    random = np.random.default_rng([seed, 3])
    # Same heldout uniforms for every policy at each user's same attempt milestone.
    probe_noise = np.random.default_rng([seed, 72]).random((users, 3, len(heldout)))
    user_index = {u: i for i, u in enumerate(counts)}
    logs, probes, theta_rows = [], [], []

    def checkpoint(user, n, index):
        probes.extend(probe(model, user, theta, heldout, probe_noise[user_index[user], index], n))
        for skill in SKILLS:
            estimate = model.user_rating(user, skill)
            theta_rows.append((user, n, skill, estimate, theta[user, skill], estimate-theta[user, skill]))

    for u in counts:
        checkpoint(u, 0, 0)
    for (u, timestamp), noise in zip(schedule, response):
        n = sum(counts[u].values())
        if v.random:
            available = [p for p in bank if p.passage_id not in seen[u]]
            candidate = available[random.integers(len(available))]
        else:
            candidate = select_passage(model, u, bank, seen_passage_ids=seen[u],
                skill_attempts=counts[u], config=v.selection).passage
        seen[u].add(candidate.passage_id)
        applied_target = max(v.selection.target_p, v.selection.cold_start_target_p) if n < v.selection.cold_start_attempts else v.selection.target_p
        for j, (q, draw) in enumerate(zip(candidate.questions, noise)):
            true_p = float(sigmoid(theta[u, q.skill]-difficulty[q.item_id]))
            y = int(draw < true_p)
            p = model.update(u, q.item_id, bool(y))
            logs.append((u, timestamp, candidate.passage_id, q.item_id, q.skill, n+j, y, p, true_p, applied_target))
            theta[u, q.skill] += learning_rate
            counts[u][q.skill] += 1
        if n+3 == 6:
            checkpoint(u, 6, 1)
        if n+3 == 3*rounds:
            checkpoint(u, 3*rounds, 2)
    observed = pd.DataFrame(logs, columns=['user_id','timestamp','passage_id','item_id','skill','n_prior','y','p','true_p','target'])
    common = pd.DataFrame(probes, columns=['user_id','checkpoint','item_id','skill','p','true_p','y'])
    estimates = pd.DataFrame(theta_rows, columns=['user_id','checkpoint','skill','estimate','truth','error'])
    metrics = {}
    for label, data in [('observed', observed), ('early', observed[observed.n_prior < 6]),
                        ('late', observed[observed.n_prior >= 30])]:
        if len(data):
            metrics.update({f'{label}_{k}': val for k, val in predictive(data).items()})
    for n, data in common.groupby('checkpoint'):
        metrics.update({f'common_{n}_{k}': val for k, val in predictive(data).items()})
    user_rows = []
    for u, data in observed.groupby('user_id'):
        c = np.array(list(counts[u].values()))
        row = dict(user_id=u, accuracy=float(data.y.mean()), cold_accuracy=float(data[data.n_prior<6].y.mean()),
            target_pred_mae=float(np.mean(abs(data.p-.7))), target_true_mae=float(np.mean(abs(data.true_p-.7))),
            configured_true_mae=float(np.mean(abs(data.true_p-data.target))),
            coverage_gap=float((max(c)-min(c))/sum(c)),
            cold_true_mae=float(np.mean(abs(data[data.n_prior<6].true_p-.8))))
        late_common = common[(common.user_id==u)&(common.checkpoint==3*rounds)]
        row.update({f'common_{k}': val for k, val in predictive(late_common).items() if k != 'n'})
        e = estimates[(estimates.user_id==u)&(estimates.checkpoint==3*rounds)].error
        row['theta_rmse'] = float(np.sqrt(np.mean(e**2)))
        user_rows.append(row)
    user_frame = pd.DataFrame(user_rows)
    for col in user_frame.columns.drop('user_id'):
        metrics[col] = float(user_frame[col].mean())
        for q in (.1, .5, .9):
            metrics[f'user_{col}_p{int(q*100)}'] = float(user_frame[col].quantile(q))
    for n, data in estimates.groupby('checkpoint'):
        metrics[f'theta_{n}_rmse'] = float(np.sqrt(np.mean(data.error**2)))
        metrics[f'theta_{n}_user_mean_rmse'] = float(np.sqrt(np.mean(data.groupby('user_id').error.mean()**2)))
        for skill, group in data.groupby('skill'):
            metrics[f'theta_{n}_{skill}_rmse'] = float(np.sqrt(np.mean(group.error**2)))
    item_rows = []
    exposed = set(observed.item_id)
    for split, frame in [('train', items), ('heldout', heldout)]:
        for item in frame.itertuples(index=False):
            item_rows.append(dict(item_id=item.item_id, split=split, exposed=item.item_id in exposed,
                truth=item.b, estimate=model.item_difficulty(item.item_id)))
    item_frame = pd.DataFrame(item_rows)
    item_frame['error'] = item_frame.estimate-item_frame.truth
    for split, data in item_frame.groupby('split'):
        metrics[f'b_{split}_rmse'] = float(np.sqrt(np.mean(data.error**2)))
    data = item_frame[item_frame.exposed]
    metrics['b_exposed_rmse'] = float(np.sqrt(np.mean(data.error**2)))
    # Heldout registration is prior-only; evaluation must never train its items.
    assert all(model.to_state()['items'][i]['attempts'] == 0 for i in heldout.item_id)
    result = (metrics, user_frame, estimates, item_frame)
    return (*result, observed, common) if return_logs else result


def summarize(frame, paired=False):
    """Seed is the replication unit; uncertainty is not computed over response rows."""
    metrics = frame.select_dtypes(include='number').columns.drop('seed')
    rows = []
    base = frame[frame.variant=='v1'].set_index('seed')
    for name, group in frame.groupby('variant'):
        for metric in metrics:
            values = group.set_index('seed')[metric]
            if paired:
                values = values-base.loc[values.index, metric]
            values = values.dropna()
            n = len(values)
            mean, variance = values.mean(), values.var(ddof=1)
            half = t.ppf(.975, n-1)*np.sqrt(variance/n) if n > 1 else np.nan
            rows.append(dict(variant=name, metric=metric, n=n, mean=mean, variance=variance,
                sd=np.sqrt(variance), ci_low=mean-half, ci_high=mean+half))
    return pd.DataFrame(rows)
