# WPプラグインスキャナー

このツールはWordPressのプラグインをダウンロードし、アップロード機能の有無を調べます。

## 特長
- WordPress.orgからプラグインを取得
- キーワード検索によるプラグイン取得
- アップロード関連コードの検出
- 結果は`scan_results.db`(SQLite)に保存
- GUIやWebインターフェースも利用可能

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
- `--web` : Web GUIを起動
- 引数無し: Tkinter GUIを起動します

結果はSQLiteデータベース(`scan_results.db`)と`saved_plugins`フォルダーに保存されます。

テスト実行:
```
python main.py --test
```
