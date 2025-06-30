from pathlib import Path
import pandas as pd
import shutil

from .config import SAVE_SOURCE, CSV_PATH

def clean_saved_plugins_only_true():
    """plugin_upload_audit.csv を読み込み、upload=True 以外の保存済みプラグインを削除。"""
    if not CSV_PATH.exists():
        print("[!] CSV file not found; skipping cleanup.")
        return

    try:
        df = pd.read_csv(CSV_PATH)
    except Exception as e:
        print(f"[!] Failed to read CSV: {e}")
        return

    true_slugs = set(df[df["upload"] == "True"]["slug"].astype(str))
    all_dirs = list(SAVE_SOURCE.glob("*"))

    removed = 0
    for d in all_dirs:
        if d.is_dir() and d.name not in true_slugs:
            try:
                shutil.rmtree(d)
                removed += 1
            except Exception as e:
                print(f"[!] Failed to delete {d}: {e}")

    print(f"[i] Cleanup complete. Removed {removed} plugin(s) not marked as upload=True.")
    

def clean_saved_plugins():
    """全ての保存済みプラグインを削除。"""
    if not SAVE_SOURCE.exists():
        print("[!] Save root does not exist; skipping cleanup.")
        return

    try:
        shutil.rmtree(SAVE_SOURCE)
        print("[i] All saved plugins have been removed.")
    except Exception as e:
        print(f"[!] Failed to remove saved plugins: {e}")
