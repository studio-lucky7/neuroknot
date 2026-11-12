from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
from research_v2.experiment import summarize,TUNE_SEEDS,VALIDATION_SEEDS
p=Path('research_v2/artifacts')
checks=[]
for phase,seeds,num in [('tune',TUNE_SEEDS,31),('validate',VALIDATION_SEEDS,10),('learning',VALIDATION_SEEDS,10),('replay',VALIDATION_SEEDS,4)]:
    f=pd.read_csv(p/f'{phase}_seeds.csv')
    assert len(f)==len(seeds)*num
    assert set(f.seed)==set(seeds)
    assert not f.duplicated(['variant','seed']).any()
    for paired,suffix in [(False,'summary'),(True,'paired')]:
        expected=summarize(f,paired).sort_values(['variant','metric']).reset_index(drop=True)
        actual=pd.read_csv(p/f'{phase}_{suffix}.csv').sort_values(['variant','metric']).reset_index(drop=True)
        pd.testing.assert_frame_equal(expected,actual,check_dtype=False,rtol=1e-8,atol=1e-12)
    if phase!='replay':
        assert (f.observed_n==2880).all()
        assert (f.common_48_n==2400).all()
        manifest=json.loads((p/f'{phase}_manifest.json').read_text())
        for name,sha in manifest['source_sha256'].items():
            assert hashlib.sha256((Path('research_v2')/name).read_bytes()).hexdigest()==sha, (phase,name)
    checks.append(f'{phase}: {len(f)} seed/config runs; summaries and paired CI recomputed successfully')
frozen=json.loads((p/'frozen_candidates.json').read_text())
assert hashlib.sha256((p/'tune_seeds.csv').read_bytes()).hexdigest()==frozen['tune_csv_sha256']
assert set(TUNE_SEEDS).isdisjoint(VALIDATION_SEEDS)
checks.append('Frozen tuning hash and disjoint seeds verified; all recorded source hashes match')
print('\n'.join(checks))
