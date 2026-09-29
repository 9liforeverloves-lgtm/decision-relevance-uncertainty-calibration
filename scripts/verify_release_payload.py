from __future__ import annotations
import argparse, hashlib
from pathlib import Path

def sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser(description='Verify a staged payload against its SHA-256 manifest.')
    ap.add_argument('--root',type=Path,required=True)
    ap.add_argument('--manifest',type=Path,default=Path('HASHES.sha256'))
    args=ap.parse_args(); root=args.root.resolve(); manifest=(root/args.manifest).resolve()
    if root not in manifest.parents: raise ValueError('manifest must be inside package root')
    lines=manifest.read_text(encoding='utf-8-sig').splitlines(); checked=0; missing=[]; mismatched=[]
    for n,line in enumerate(lines,1):
        if not line.strip(): continue
        parts=line.split(maxsplit=1)
        if len(parts)!=2: raise ValueError(f'invalid manifest line {n}')
        expected, rel=parts; rel=rel.lstrip('* ').replace('\\','/')
        path=(root/rel).resolve()
        if root not in path.parents: raise ValueError(f'path escapes package root at line {n}: {rel}')
        if not path.is_file(): missing.append(rel); continue
        actual=sha(path); checked+=1
        if actual.lower()!=expected.lower(): mismatched.append((rel,expected,actual))
    print(f'checked={checked} missing={len(missing)} mismatched={len(mismatched)} listed={len(lines)}')
    if missing: print('MISSING',*missing[:20],sep='\\n')
    if mismatched: print('MISMATCH',*mismatched[:20],sep='\\n')
    if missing or mismatched: raise SystemExit(1)
    print('PASS')
if __name__=='__main__': main()
