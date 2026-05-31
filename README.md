# GakumasTranslationData zhTW

Traditional Chinese build fork for Gakumas translation data.

這個倉庫維持上游的同步與發布流程，並在 `local-files` 之上增加繁中轉換與驗證流程。

**Latest package API:** `https://api.github.com/repos/fullpie/GakumasTranslationData/releases/latest`

## Android App

Android 版建議使用本倉庫提供的修正版 app。此 app 修正了原 Android 版部分文字掛載問題，包括 Produce Card 文字缺漏、genericTrans hook 匹配，以及部分數值顯示成重複數字的問題，例如 `+7` 顯示為 `+77`、`+2` 顯示為 `+22`。

這些問題是在 Android app 端修正，繁中包本身仍維持與 PC/DMM 版共用，不需要在翻譯包內加入 Android 專用資料。

### 方式一：下載 APK

請到本倉庫的 [Releases](https://github.com/fullpie/GakumasTranslationData/releases) 下載修正版 APK：

- `GakumasLocalify-Android-patched.apk`

### 方式二：自行編譯

也可以到 [Releases](https://github.com/fullpie/GakumasTranslationData/releases) 下載 app 原始碼壓縮包：

- `GakumasLocalify-Android-source.zip`

解壓後可上傳到自己的 GitHub repo，使用內建 GitHub Actions 自動編譯 APK，並從 Actions artifact 下載建置結果。

### 安裝注意事項

上述兩種方式產出的 APK 都是透過 GitHub Actions 建置。若沒有使用同一組固定簽名，不同來源或不同次建置的 APK 可能會出現簽名不同的情況。

如果 Android 顯示簽名衝突、套件無法更新，或無法覆蓋安裝，請先解除安裝舊版 app，再安裝新版。

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
