# GakumasTranslationData zhTW

學園偶像大師翻譯資料繁體中文構建 fork。
Traditional Chinese build fork for Gakumas translation data.

這個倉庫維持上游的同步與發布流程，並在 `local-files` 之上增加一層 zhTW 轉換與驗證。
This repository keeps the upstream sync and release flow, then adds a zhTW conversion and validation layer on top of `local-files`.

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

這個 zhTW build 不是單純整包丟給 OpenCC。
The zhTW build is not a plain folder-wide OpenCC pass.

- JSON 會遞迴轉換 value，不碰 key
- `resource` 劇情腳本會先 parse，再依欄位處理 `text`、`name`、`title` 與選項文字
- 含有 kana 的行會先保護，避免混合日文被整段強轉
- OpenCC 前後都會套用精確詞與 regex 規則
- build 結束後會產生 `zhtw_validation_report.json`，檢查保護詞是否被破壞、是否殘留已知簡體詞
- JSON values are converted recursively without touching keys
- `resource` story scripts are parsed field by field, including `text`, `name`, `title`, and choices
- Lines containing kana are protected from blanket conversion so mixed Japanese text is not damaged
- Exact-term and regex rules are applied before and after OpenCC
- `zhtw_validation_report.json` is generated after build to detect broken protected terms and known Simplified Chinese leftovers

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

## GitHub Actions

GitHub Actions 仍維持原本的自動同步模型，但測試分支只做 build 與 artifact 上傳。
GitHub Actions keeps the original sync model, while non-`main` test branches only build and upload artifacts.

- 更新 submodule
- 重建 merged resources
- 建立 zhTW package
- `main` 分支建立或更新 release
- `main` 分支才會 commit 並 push 生成結果
- update submodules
- rebuild merged resources
- build the zhTW package
- create or update the release only on `main`
- commit and push generated results back only on `main`

workflow 入口仍然是：

```bash
python build_zhtw.py
```

只要 `build_zhtw.py` 與 zhTW 規則檔有提交，GitHub 上就能照原流程自動跑。
As long as `build_zhtw.py` and the zhTW rule files are committed, the GitHub workflow can keep running without any local-only path settings.

## 維護備註 / Maintenance Notes

- `merge.py` 依賴上游資料格式；若 raw 腳本或 CSV 結構變動，可能會在 zhTW 轉換前就先失敗
- zhTW 修正請優先放在 `name_dictionary_zhTW.json`、`term_dictionary_zhTW.json`、`regex_dictionary_zhTW.json`
- 不建議把專案特例零散硬寫進其他無關腳本
- `merge.py` depends on upstream file formats; upstream changes can fail before zhTW conversion starts
- Put zhTW-specific fixes in `name_dictionary_zhTW.json`, `term_dictionary_zhTW.json`, or `regex_dictionary_zhTW.json`
- Avoid scattering project-specific fixes into unrelated scripts
