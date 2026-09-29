from __future__ import annotations
import argparse, shutil
from pathlib import Path
import pandas as pd

def main():
    ap=argparse.ArgumentParser(description='Prepare isolated manifests for independent pending alpha levels.')
    ap.add_argument('--alpha-root',type=Path,required=True)
    ap.add_argument('--workers-root',type=Path,required=True)
    a=ap.parse_args(); root=a.alpha_root.resolve(); workers=a.workers_root.resolve()
    if not (root/'ALPHA_SENSITIVITY_PROTOCOL.json').is_file(): raise FileNotFoundError('frozen protocol missing')
    if workers.exists() and any(workers.iterdir()): raise FileExistsError(f'worker root is not empty: {workers}')
    workers.mkdir(parents=True,exist_ok=True)
    manifest=pd.read_csv(root/'alpha_sensitivity_run_manifest.csv',dtype={'status':'string','result_sha256':'string','error':'string'})
    if manifest.job_id.duplicated().any(): raise ValueError('duplicate job IDs')
    replay=manifest[manifest.alpha.astype(float)==0.5]
    if len(replay)!=160 or not replay.status.eq('complete').all(): raise ValueError('all 160 alpha=0.50 replay jobs must be complete first')
    for alpha in (0.25,0.75,1.0):
        subset=manifest[(manifest.status=='planned') & (manifest.alpha.astype(float)==alpha)].copy()
        if subset.empty: raise ValueError(f'no pending jobs at alpha={alpha}')
        d=workers/f'alpha_{str(alpha).replace(".","p")}'
        d.mkdir(parents=True)
        shutil.copy2(root/'ALPHA_SENSITIVITY_PROTOCOL.json',d/'ALPHA_SENSITIVITY_PROTOCOL.json')
        shutil.copy2(root/'alpha_raw_baseline_manifest.csv',d/'alpha_raw_baseline_manifest.csv')
        subset.to_csv(d/'alpha_sensitivity_run_manifest.csv',index=False)
        print(f'alpha={alpha:.2f} jobs={len(subset)} path={d}')
if __name__=='__main__': main()
