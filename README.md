# GakumasTranslationData zhTW

Traditional Chinese build fork for Gakumas translation data.

This repository keeps the original upstream sync flow and adds a zhTW packaging layer on top. Upstream translation sources are still updated through submodules, then merged into `local-files`, then converted into `local-files-zhTW`, and finally packed as `GakumasTranslationData_zhTW.zip`.

## Repository Role

- Upstream base repo: [chinosk6/GakumasTranslationData](https://github.com/chinosk6/GakumasTranslationData)
- This fork keeps the same merge/release pipeline and adds Traditional Chinese conversion plus validation
- GitHub Actions can still update submodules, rebuild the package, and publish the zhTW release automatically

## Data Flow

1. Update submodules to fetch the latest upstream translation data
2. Put raw ADV script files into `./raw`
3. Run `merge.py` to generate `./local-files`
4. Run `build_zhtw.py` to generate `./local-files-zhTW`
5. Pack `./local-files-zhTW` into `GakumasTranslationData_zhTW.zip`

## Important Folders

- `./raw`: raw ADV script files (`adv*.txt`), not committed
- `./gakuen-adapted-translation-data`: adapted story translation files
- `./GakumasPreTranslation`: fallback pretranslation data and localization source
- `./gakumas-generic-strings-translation`: generic string translation source
- `./gakumas-master-translation`: master table translation source
- `./local-files`: merged Simplified Chinese build output
- `./local-files-zhTW`: Traditional Chinese build output

## Important Files

- `./merge.py`: merges submodule data and raw ADV files into `./local-files`
- `./build_zhtw.py`: builds zhTW output from `./local-files`
- `./name_dictionary_zhTW.json`: exact replacement rules, mainly names and protected terms
- `./term_dictionary_zhTW.json`: project-specific zhTW override terms
- `./regex_dictionary_zhTW.json`: regex-based zhTW normalization rules
- `./version.txt`: version used for release naming

## Traditional Chinese Build Strategy

The zhTW build is not a plain folder-wide OpenCC pass.

- JSON files are converted recursively by value
- ADV resource files are parsed by field, so `text`, `name`, `title`, and choice text are all handled
- Lines containing kana are protected from blanket conversion to avoid breaking mixed Japanese text
- Exact-term protection and override rules are applied before and after OpenCC
- A validation pass checks for broken protected terms and known forbidden simplified leftovers

Validation output is written to `zhtw_validation_report.json` during local or CI builds. It is ignored by git because it is a generated diagnostic file, not release content.

## Local Build

### Requirements

- Python 3.11
- `pip install -r requirements.txt`
- `pip install opencc-python-reimplemented`
- submodules initialized and updated

### Build merged source

```bash
git submodule update --init --recursive
python merge.py
```

### Build zhTW package

```bash
python build_zhtw.py
```

Outputs:

- `./local-files-zhTW`
- `./GakumasTranslationData_zhTW.zip`

## GitHub Actions

The workflow keeps the original upstream sync model:

- update submodules
- rebuild merged resources
- build zhTW package
- create or update release
- commit generated changes back to the repository

The workflow entry still runs:

```bash
python build_zhtw.py
```

So as long as `build_zhtw.py` and the zhTW rule files are committed, the GitHub Action can continue to run automatically without local-only path settings.

## Notes

- `merge.py` depends on upstream file formats; if upstream raw text or CSV validation changes, merge failures can happen before zhTW conversion starts
- zhTW-specific fixes should go into `name_dictionary_zhTW.json`, `term_dictionary_zhTW.json`, or `regex_dictionary_zhTW.json`, not hardcoded ad hoc into unrelated scripts
- `zhtw_validation_report.json` is for debugging build quality and should not be treated as a release artifact
