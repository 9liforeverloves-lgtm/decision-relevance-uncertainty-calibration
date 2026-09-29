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

## Published initial release

The initial `v1.0.0-rc1` prerelease is already published at https://github.com/9liforeverloves-lgtm/decision-relevance-uncertainty-calibration/releases/tag/v1.0.0-rc1. Do not rerun the initial tag/release commands.

## Create a later release

For a future version, first update the version and release date in `CITATION.cff`, prepare notes that describe that version, review all public files, regenerate the hashes, and push the reviewed `main` branch. Then choose a new tag (never reuse `v1.0.0-rc1`) and run:

```powershell
$nextTag = 'v1.0.1'
git tag -a $nextTag -m "Reproducibility release"
git push origin $nextTag
gh release create $nextTag --verify-tag --title "Reproducibility release" --notes-file "docs/RELEASE_NOTES_$nextTag.md"
gh release view $nextTag --json tagName,name,url,isDraft,isPrerelease
```

Do not add or claim a DOI unless a later Zenodo deposit has issued one. See `docs/ZENODO_DEPOSIT_STEPS.md` for the optional archive workflow.
