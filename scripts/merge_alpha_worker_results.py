from __future__ import annotations
import argparse, hashlib, json, shutil
from pathlib import Path
import pandas as pd

def sha(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def copy_checked(src:Path,dst:Path,expected:str):
    if sha(src)!=expected: raise ValueError(f'worker hash mismatch: {src}')
    dst.parent.mkdir(parents=True,exist_ok=True)
    if not dst.exists() or sha(dst)!=expected: shutil.copy2(src,dst)
    if sha(dst)!=expected: raise ValueError(f'copy verification failed: {dst}')

def main():
    ap=argparse.ArgumentParser(description='Merge completed, disjoint alpha worker outputs into the frozen campaign namespace.')
    ap.add_argument('--alpha-root',type=Path,required=True)
    ap.add_argument('--workers-root',type=Path,required=True)
    a=ap.parse_args(); root=a.alpha_root.resolve(); workers=a.workers_root.resolve()
    main_manifest_path=root/'alpha_sensitivity_run_manifest.csv'
    main=pd.read_csv(main_manifest_path,dtype={'status':'string','result_sha256':'string','error':'string'})
    lookup={r.job_id:i for i,r in main.iterrows()}; touched=set()
    for wm in sorted(workers.glob('alpha_*/alpha_sensitivity_run_manifest.csv')):
        worker=wm.parent; m=pd.read_csv(wm,dtype={'status':'string','result_sha256':'string','error':'string'})
        protocol=(worker/'ALPHA_SENSITIVITY_PROTOCOL.json').read_bytes()
        if protocol!=(root/'ALPHA_SENSITIVITY_PROTOCOL.json').read_bytes(): raise ValueError('worker protocol differs from frozen main protocol')
        for r in m.itertuples(index=False):
            if r.job_id not in lookup or r.job_id in touched: raise ValueError(f'unknown/duplicate worker ID {r.job_id}')
            idx=lookup[r.job_id]
            if main.at[idx,'status']!='planned' or r.status!='complete': raise ValueError(f'expected planned main and complete worker row: {r.job_id}')
            result_src=worker/r.result_path; result_dst=root/r.result_path
            copy_checked(result_src,result_dst,str(r.result_sha256))
            payload=json.loads(result_dst.read_text(encoding='utf-8'))
            for item in payload.get('candidate_state_files',[]):
                copy_checked(worker/item['path'],root/item['path'],item['sha256'])
            for col in main.columns:
                if col in m.columns: main.at[idx,col]=getattr(r,col)
            touched.add(r.job_id)
    main.to_csv(main_manifest_path,index=False)
    print(f'merged={len(touched)} complete={int(main.status.eq("complete").sum())} planned={int(main.status.eq("planned").sum())}')
if __name__=='__main__': main()
