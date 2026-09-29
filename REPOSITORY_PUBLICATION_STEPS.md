# Repository maintenance and release steps

## Verified repository

- Name: `decision-relevance-uncertainty-calibration`
- URL: https://github.com/9liforeverloves-lgtm/decision-relevance-uncertainty-calibration
- Visibility: public
- Description: Reproducibility package for Decision Relevance of Uncertainty Calibration in Active-Learning Materials Screening
- Topics: materials-informatics, active-learning, uncertainty-quantification, materials-science, matbench, scientific-machine-learning, reproducibility

## Publish reviewed changes

From the repository root, regenerate and verify the file hashes, inspect the staged diff, and push only a normal fast-forward:

```powershell
python scripts/generate_sha256_manifest.py
python scripts/verify_sha256.py SHA256SUMS.txt
git status --short --branch
git diff --check
git add -A
git diff --cached --check
git status --short --branch
git commit -m "docs: update reproducibility release"
git push origin main
gh repo view 9liforeverloves-lgtm/decision-relevance-uncertainty-calibration --json nameWithOwner,description,visibility,url
```

Never use `--force` or overwrite unrelated history. Inspect the remote branch before publishing if local and remote histories diverge.

## Create the reviewed release

Only after the public-file and content audits pass:

```powershell
git tag -a v1.0.0-rc1 -m "MLST submission release candidate"
git push origin v1.0.0-rc1
gh release create v1.0.0-rc1 --title "MLST submission release candidate" --notes-file docs/RELEASE_NOTES_v1.0.0-rc1.md
gh release view v1.0.0-rc1 --json tagName,name,url,isDraft
```

Do not add or claim a DOI unless a later Zenodo deposit has issued one. See `docs/ZENODO_DEPOSIT_STEPS.md` for the optional archive workflow.
