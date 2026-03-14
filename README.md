# GakumasTranslationData zhTW

學園偶像大師翻譯資料繁體中文構建 fork。
Traditional Chinese build fork for Gakumas translation data.

這個倉庫維持上游的同步與發布流程，並在 `local-files` 之上增加一層 zhTW 轉換與驗證。
This repository keeps the upstream sync and release flow, then adds a zhTW conversion and validation layer on top of `local-files`.

更新資源包 API: `https://api.github.com/repos/fullpie/Gakumass/releases/latest`

## 專案定位 / Repository Role

- 上游基底倉庫：[`chinosk6/GakumasTranslationData`](https://github.com/chinosk6/GakumasTranslationData)
- 這個 fork 保留原本的 merge / release pipeline，另外生成繁體中文輸出
- GitHub Actions 仍可自動更新 submodule、重建資源、打包 zhTW release
- Upstream base repository: [`chinosk6/GakumasTranslationData`](https://github.com/chinosk6/GakumasTranslationData)
- This fork keeps the original merge/release pipeline and adds a Traditional Chinese output layer
- GitHub Actions can still update submodules, rebuild resources, and publish the zhTW package automatically

## 資料流程 / Data Flow

1. 更新 submodule，取得最新翻譯資料
   Update submodules to fetch the latest translation data.
2. 將 ADV 原始腳本放入 `./raw`
   Put raw ADV script files into `./raw`.
3. 執行 `merge.py` 產生 `./local-files`
   Run `merge.py` to generate `./local-files`.
4. 執行 `build_zhtw.py` 產生 `./local-files-zhTW`
   Run `build_zhtw.py` to generate `./local-files-zhTW`.
5. 打包成 `GakumasTranslationData_zhTW.zip`
   Pack the result into `GakumasTranslationData_zhTW.zip`.

## 重要資料夾 / Important Folders

- `./raw`: ADV 原始腳本（`adv*.txt`），不應提交到 git
- `./gakuen-adapted-translation-data`: 劇情翻譯來源
- `./GakumasPreTranslation`: 預翻與本地化來源
- `./gakumas-generic-strings-translation`: 通用字串翻譯來源
- `./gakumas-master-translation`: master table 翻譯來源
- `./local-files`: 合併後的簡中輸出
- `./local-files-zhTW`: 繁中輸出
- `./raw`: raw ADV script files (`adv*.txt`), not committed
- `./gakuen-adapted-translation-data`: adapted story translation source
- `./GakumasPreTranslation`: fallback pretranslation and localization source
- `./gakumas-generic-strings-translation`: generic string translation source
- `./gakumas-master-translation`: master table translation source
- `./local-files`: merged Simplified Chinese output
- `./local-files-zhTW`: Traditional Chinese output

## 重要檔案 / Important Files

- `./merge.py`: 合併 submodule 資料與 raw ADV 腳本，輸出到 `./local-files`
- `./build_zhtw.py`: 從 `./local-files` 建立 zhTW 輸出
- `./name_dictionary_zhTW.json`: 精確詞替換，主要處理人名與保護詞
- `./term_dictionary_zhTW.json`: 專案專用的繁中詞彙補正
- `./regex_dictionary_zhTW.json`: 以正則規則做後處理與正規化
- `./version.txt`: release 版本命名用
- `./merge.py`: merges submodule data and raw ADV files into `./local-files`
- `./build_zhtw.py`: builds zhTW output from `./local-files`
- `./name_dictionary_zhTW.json`: exact replacements for names and protected terms
- `./term_dictionary_zhTW.json`: project-specific zhTW term overrides
- `./regex_dictionary_zhTW.json`: regex-based zhTW normalization rules
- `./version.txt`: version used for release naming

## 繁中轉換策略 / zhTW Build Strategy

- 以 OpenCC 為基礎，並結合專案專用規則進行轉換
- JSON 僅轉換 value；`resource` 依欄位處理 `text`、`name`、`title` 與選項文字
- 含 kana 的內容會先保護，再套用精確詞與 regex 規則
- `zhtw_validation_report.json` 用於檢查保護詞與已知簡體殘留
- Conversion is based on OpenCC with project-specific overrides
- JSON processing only converts values; `resource` files are handled by field
- Lines containing kana are protected before exact-term and regex normalization
- `zhtw_validation_report.json` is used to detect broken protected terms and known Simplified Chinese leftovers

`zhtw_validation_report.json` 是建置診斷檔，已加入 `.gitignore`，不屬於 release 內容。
`zhtw_validation_report.json` is a generated diagnostic file, ignored by git, and not part of the release payload.

## 本地建置 / Local Build

### 需求 / Requirements

- Python 3.11
- `pip install -r requirements.txt`
- `pip install opencc-python-reimplemented`
- submodule 已初始化並更新
- submodules initialized and updated

### 產生合併輸出 / Build merged source

```bash
git submodule update --init --recursive
python merge.py
```

### 產生繁中包 / Build zhTW package

```bash
python build_zhtw.py
```

輸出 / Outputs:

- `./local-files-zhTW`
- `./GakumasTranslationData_zhTW.zip`

## 維護備註 / Maintenance Notes

- `merge.py` 依賴上游資料格式；若 raw 腳本或表格結構變動，可能影響建置
- zhTW 修正請集中維護於 `name_dictionary_zhTW.json`、`term_dictionary_zhTW.json`、`regex_dictionary_zhTW.json`
- `merge.py` depends on upstream file formats; upstream changes may affect the build
- Keep zhTW-specific fixes in `name_dictionary_zhTW.json`, `term_dictionary_zhTW.json`, and `regex_dictionary_zhTW.json`
