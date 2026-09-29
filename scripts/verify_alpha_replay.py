from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd

COMPARE=['material_id','true_y_retrospective','predicted_mu','raw_sigma','local_scale','predicted_value_rank','uncertainty_rank_raw','acquisition_score','acquisition_rank','selected_flag','query_order','counterfactual_raw_rank','counterfactual_raw_selected','counterfactual_local_rank','counterfactual_local_selected','top_tail_0p5','top_tail_1','top_tail_5']
def sha(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()
def main():
    ap=argparse.ArgumentParser(description='Check the complete alpha=0.50 replay before running other alpha groups.')
    ap.add_argument('--v2-root',type=Path,required=True); ap.add_argument('--alpha-root',type=Path,required=True); ap.add_argument('--report',type=Path,required=True)
    a=ap.parse_args(); v2=a.v2_root.resolve(); root=a.alpha_root.resolve()
    protocol_path=root/'ALPHA_SENSITIVITY_PROTOCOL.json'; protocol=json.loads(protocol_path.read_text(encoding='utf-8')); protocol_hash=sha(protocol_path)
    if sha(root.parent/'scripts'/'run_alpha_sensitivity.py')!=protocol['alpha_driver_sha256']: raise ValueError('alpha runner differs from frozen driver hash')
    m=pd.read_csv(root/'alpha_sensitivity_run_manifest.csv',dtype={'status':'string','result_sha256':'string'})
    if len(m)!=640 or m.job_id.duplicated().any(): raise ValueError('main manifest must retain 640 unique rows')
    m05=m[m.alpha.astype(float)==0.5]
    if len(m05)!=160 or m05.status.ne('complete').any() or m05.protocol_sha256.ne(protocol_hash).any(): raise ValueError('the 160 alpha=0.50 rows are not complete under the frozen protocol')
    v2m=pd.read_csv(v2/'V2_RUN_MANIFEST.csv'); lookup={(r.task,r.split,int(r.seed),r.policy,r.condition):r for r in v2m.itertuples(index=False)}
    jobs=stages=raw=0
    for r in m05.itertuples(index=False):
        rp=root/r.result_path
        if sha(rp)!=r.result_sha256: raise ValueError(f'result hash mismatch: {r.job_id}')
        result=json.loads(rp.read_text(encoding='utf-8')); refrow=lookup[(r.task,r.split,int(r.seed),r.policy,'LOCAL')]
        refresult=json.loads((v2/refrow.result_path).read_text(encoding='utf-8'))
        if result['queried_ids_sha256_in_order']!=refresult['queried_ids_sha256_in_order']: raise ValueError(f'query order mismatch: {r.job_id}')
        paths=result.get('candidate_state_files',[])
        if len(paths)!=4: raise ValueError(f'wrong stage count: {r.job_id}')
        for stage,item in enumerate(paths):
            f=root/item['path']
            if sha(f)!=item['sha256']: raise ValueError(f'state hash mismatch: {r.job_id} stage {stage}')
            x=pd.read_parquet(f); y=pd.read_parquet(v2/refrow.candidate_state_path/f'stage_{stage}.parquet')
            if x.target_labels_used_for_acquisition.astype(bool).any(): raise ValueError('target-label leakage flag set')
            ok=all(np.array_equal(x[c].to_numpy(),y[c].to_numpy()) for c in COMPARE)
            ok &= np.array_equal(x.corrected_sigma_alpha_0p5.to_numpy(),y.corrected_sigma_alpha_0p5.to_numpy())
            ok &= np.array_equal(x.counterfactual_raw_score.to_numpy(),y.counterfactual_raw_score.to_numpy())
            ok &= np.array_equal(x.counterfactual_local_score.to_numpy(),y.counterfactual_local_score.to_numpy())
            if not ok: raise ValueError(f'stage mismatch: {r.job_id} stage {stage}')
            stages+=1
        jobs+=1
    baselines=pd.read_csv(root/'alpha_raw_baseline_manifest.csv')
    if len(baselines)!=160: raise ValueError('expected 160 RAW baselines')
    for r in baselines.itertuples(index=False):
        if sha(v2/r.result_path)!=r.result_sha256: raise ValueError(f'RAW baseline hash mismatch: {r.job_id}')
        raw+=1
    report={'status':'PASS','alpha_protocol_sha256':protocol_hash,'alpha_0p50_replay_jobs':jobs,'exact_replay_stages':stages,'raw_baselines_hash_verified':raw,'target_labels_used_for_acquisition':False}
    out=a.report.resolve(); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8'); print(json.dumps(report,indent=2))
if __name__=='__main__': main()
