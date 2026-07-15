# GakumasTranslationData zhTW

Traditional Chinese build fork for Gakumas translation data.

這個倉庫維持上游的同步與發布流程，並在 `local-files` 之上增加繁中轉換與驗證流程。

**Latest package API:** `https://api.github.com/repos/fullpie/GakumasTranslationData/releases/latest`

## Android App

Android 版建議搭配 [`fullpie/Gakumas_apptest`](https://github.com/fullpie/Gakumas_apptest) 提供的修正版 app。此 app 修正了原 Android 版部分文字掛載問題，包括 Produce Card 文字缺漏、genericTrans hook 匹配，以及部分數值顯示成重複數字的問題，例如 `+7` 顯示為 `+77`、`+2` 顯示為 `+22`。

這些問題是在 Android app 端修正，繁中包本身仍維持與 PC/DMM 版共用，不需要在翻譯包內加入 Android 專用資料。

### 方式一：下載 APK

請到 App 倉庫的 [Releases](https://github.com/fullpie/Gakumas_apptest/releases)，在最新的 `app-v...` Release 下載：

- `GakumasLocalify-app-vX.Y.Z.apk`

### 方式二：自行編譯

App 原始碼位於 [`fullpie/Gakumas_apptest`](https://github.com/fullpie/Gakumas_apptest)，也可以直接下載 [main 分支 ZIP](https://github.com/fullpie/Gakumas_apptest/archive/refs/heads/main.zip)。

Fork、clone 或解壓後上傳到自己的 GitHub repo，即可使用內建的 `Android CI` workflow 編譯 APK，並從 Actions artifact 下載建置結果。

### 安裝注意事項

第一次從原作者 app、其他人建置的版本，或舊的非固定簽名版本切換到本專案時，請先解除安裝舊的 Gakumas Localify app，再安裝新版，以免 Android 因簽名不同而拒絕安裝。

這項提醒只針對 Localify app。安裝本專案的固定簽名版本後，後續 `app-v...` 新版可以直接覆蓋安裝。

## Repository Role

- Upstream base repository: [`chinosk6/GakumasTranslationData`](https://github.com/chinosk6/GakumasTranslationData)
- This fork keeps the original merge/release pipeline and adds a Traditional Chinese output layer.
- GitHub Actions can update submodules, rebuild resources, and publish the zhTW package automatically.

## Data Flow

1. Update submodules to fetch the latest translation data.
2. Put raw ADV script files into `./raw`.
3. Run `merge.py` to generate `./local-files`.
4. Run `build_zhtw.py` to generate `./local-files-zhTW`.
5. Pack the result into `GakumasTranslationData_zhTW.zip`.

## Important Folders

- `./raw`: raw ADV script files (`adv*.txt`), not committed
- `./gakuen-adapted-translation-data`: adapted story translation source
- `./GakumasPreTranslation`: fallback pretranslation and localization source
- `./gakumas-generic-strings-translation`: generic string translation source
- `./gakumas-master-translation`: master table translation source
- `./local-files`: merged Simplified Chinese output
- `./local-files-zhTW`: Traditional Chinese output

## Important Files

- `./merge.py`: merges submodule data and raw ADV files into `./local-files`
- `./build_zhtw.py`: builds zhTW output from `./local-files`
- `./name_dictionary_zhTW.json`: exact replacements for names and protected terms
- `./term_dictionary_zhTW.json`: project-specific zhTW term overrides
- `./regex_dictionary_zhTW.json`: regex-based zhTW normalization rules
- `./version.txt`: version used for release naming

## zhTW Build Strategy

- Conversion is based on OpenCC with project-specific overrides.
- JSON processing only converts values; `resource` files are handled by field.
- Lines containing kana are protected before exact-term and regex normalization.
- `zhtw_validation_report.json` is used to detect broken protected terms and known Simplified Chinese leftovers.

`zhtw_validation_report.json` is a generated diagnostic file, ignored by git, and not part of the release payload.

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

## Maintenance Notes

- `merge.py` depends on upstream file formats; upstream changes may affect the build.
- Keep zhTW-specific fixes in `name_dictionary_zhTW.json`, `term_dictionary_zhTW.json`, and `regex_dictionary_zhTW.json`.
- Android app compatibility fixes should stay in the app build, not in the shared translation package, unless the same issue is confirmed on PC/DMM.
