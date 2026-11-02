# Translation tools / 翻译工具

Run from the repository root with Python 3.10+. No packages, JDK or Android SDK are needed.

在仓库根目录运行，需要 Python 3.10+，不需要安装依赖、JDK 或 Android SDK。

```sh
python tools/i18n/translations.py check
python tools/i18n/translations.py export --output translations.csv
python -m unittest discover -s tools/i18n -v
```

## Check keys / 检查条目

`check` compares `string`, `plurals` and `string-array` resource names in `strings*.xml` against the default English `values/` folder. It reports every missing/extra key by locale and resource type, even if a key moves to another file. Entries marked `translatable="false"` in English are excluded and should not be duplicated in translations. Duplicate resources and malformed XML are errors.

Language folders are discovered automatically: `values-zh`, `values-ru`, `values-in` (Android's legacy code for Indonesian), region folders such as `values-fr-rCA`, and BCP 47 folders such as `values-b+zh+Hant`. Configuration overlays such as `values-night` and `values-zh-v31` are excluded. Only folders containing `strings*.xml` are checked; this command does not verify that every language registered by the app has a resource folder.

Exit codes: **0** means keys match, **1** means missing/extra keys, **2** means invalid input or an I/O error. The GitHub Actions workflow runs this check and the tool's tests for resource/tool changes.

This is a fast key check, not a replacement for `StringResourcesTest`: the existing Android JVM tests still check placeholders, supported languages and their plural rules. Different languages can have different plural quantities; this tool does not require English's quantities in every translation.

`check` 对比 `values/` 英文基准与各语言 `strings*.xml` 中的字符串、复数和字符串数组名称，逐条报告缺失、多余的 key。条目可以放在不同文件里；默认资源中标为 `translatable="false"` 的条目不需要翻译。重复 key、XML 错误会报错。

工具自动发现有字符串文件的语言目录，不检查夜间模式等配置覆盖目录，也不验证 App 注册的语言是否都有对应目录。返回码：0 为通过，1 为缺失或多余 key，2 为输入或文件错误。占位符、已支持语言和各语言复数规则仍由现有 `StringResourcesTest` 检查。

## Export reference CSV / 导出翻译对照表

`export` writes UTF-8 CSV with a BOM so spreadsheet applications can open Chinese text. The parent directory of `--output` must already exist; an existing output file is replaced. The generated file is for review and translation reference, **not for automatic import**. Do not commit generated CSV files; submit changes to the XML resources instead.

Columns:

- `key`, `type`: Android resource name and resource type.
- `item`: blank for strings, a quantity for plurals, a zero-based index for arrays.
- `source`: English resource file relative to the resource directory.
- `context`: XML comments immediately before the English resource, if any.
- `values`, `values-zh`, `values-b+zh+Hant`, then other discovered folders: English, Simplified Chinese, Traditional Chinese, and other translations. Only existing folders get columns.

Each plural quantity gets a separate row, including quantities found only in translations. Blank cells mean that exact item is absent; the tool does not fill in fallback text. This is normal for plural categories a language does not use. Markup and Android escapes such as `\n`, `\'`, and `%1$s` are kept for review rather than rendered as Android display text. CSV quoting preserves commas and embedded newlines.

To contribute a translation, use the English and Chinese references plus the source file for context. Edit the XML in the relevant language folder, preserve format placeholders and Android escaping, then run the key check and the existing JVM resource tests:

```sh
./gradlew :app:testDebugUnitTest --tests 'com.wangzan101.mika.i18n.StringResourcesTest'
```

`export` 导出带 UTF-8 BOM 的 CSV，包含 key、资源类型、复数数量词或数组下标、英文来源文件、相邻注释，以及英文、简体、繁体和其他语言。复数逐项占一行；缺失项留空，不自动套用英文。保留 Android 转义、占位符和内联 XML 标签。

输出目录需要已存在，同名 CSV 会被覆盖。CSV 只作翻译参考，不支持自动导入，也不需要提交到仓库。贡献时修改对应语言的 XML，保留占位符和转义，再运行完整性检查及上面的 JVM 资源测试。
