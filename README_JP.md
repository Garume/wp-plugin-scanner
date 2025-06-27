# WPプラグインスキャナー

このツールはWordPressのプラグインをダウンロードし、アップロード機能の有無を調べます。

## 特長
- WordPress.orgからプラグインを取得
- キーワード検索によるプラグイン取得
- アップロード関連コードの検出
- 結果はCSVまたはSQLiteデータベースに出力
- デスクトップGUIも利用可能

## インストール
1. Python 3.10以上を用意してください。
2. `pip install -r requirements.txt` を実行します。

## 使い方
```
python main.py [オプション] [スラッグ ...]
```
主なオプション:
- `--search <キーワード>` : キーワードからスラッグを検索
- `--save` / `--nosave` : プラグインの保存有無を設定
- `--db-csv` / `--db-sqlite` : 出力形式を選択（デフォルトはCSV）
- `scan-local <プラグイン>` : 検出したファイル名と行数を返却
- `--extract-matches` : 検出したファイル名と行数をcsvとして出力
- 引数無し: Tkinter GUIを起動します

結果はCSV（`plugin_upload_audit.csv`）またはSQLite（`plugin_upload_audit.db`）と`saved_plugins`フォルダーに保存されます。
また、`--extract-matches`は`plugin_upload_audit.csv`と`saved_plugins`フォルダが必要です

テスト実行:
```
python main.py --test
```
