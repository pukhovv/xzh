#!/usr/bin/env python3
import argparse
import json
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ANKICONNECT = "http://127.0.0.1:8765"
MODEL_NAME = "xiezh-note"

CARD_DIR = HERE / "card"
FRONT_FILE = CARD_DIR / "xnote.html"
BACK_FILE = CARD_DIR / "xnote_back.html"
CSS_FILE = CARD_DIR / "styling.css"


def anki(action, **params):
    resp = requests.post(
        ANKICONNECT,
        json={"action": action, "version": 6, "params": params},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("error"):
        raise RuntimeError(f"AnkiConnect error: {data['error']}")
    return data["result"]


def sync(model_name, dry_run=False):
    front = FRONT_FILE.read_text()
    back = BACK_FILE.read_text()
    css = CSS_FILE.read_text()

    models = anki("modelNamesAndIds")
    if model_name not in models:
        raise SystemExit(
            f"Model '{model_name}' not found in Anki.\n"
            f"Available models: {list(models.keys())}"
        )

    templates = anki("modelTemplates", modelName=model_name)
    card_names = list(templates.keys())
    if not card_names:
        raise SystemExit(f"Model '{model_name}' has no card templates.")
    if len(card_names) > 1:
        print(
            f"Note: model has multiple card types ({card_names}). "
            f"Updating only '{card_names[0]}'."
        )

    card_name = card_names[0]

    if dry_run:
        print(f"[dry-run] Would update:")
        print(f"  Front ← {FRONT_FILE} ({len(front)} chars)")
        print(f"  Back  ← {BACK_FILE} ({len(back)} chars)")
        print(f"  CSS   ← {CSS_FILE} ({len(css)} chars)")
        return

    anki(
        "updateModelTemplates",
        model={
            "name": model_name,
            "templates": {card_name: {"Front": front, "Back": back}},
        },
    )
    anki("updateModelStyling", model={"name": model_name, "css": css})

    print(
        f"Synced {FRONT_FILE.name}, {BACK_FILE.name}, {CSS_FILE.name} "
        f"→ '{model_name}/{card_name}'"
    )


def watch(model_name, interval):
    files = {
        "front": FRONT_FILE,
        "back": BACK_FILE,
        "css": CSS_FILE,
    }
    mtimes = {k: p.stat().st_mtime for k, p in files.items()}

    print(f"Watching {CARD_DIR} (Ctrl+C to stop)")
    try:
        while True:
            for key, path in files.items():
                current = path.stat().st_mtime
                if current <= mtimes[key]:
                    continue
                print(f"Changed: {path.name}")
                try:
                    sync(model_name)
                except Exception as e:
                    print(f"Sync failed: {e}")
                mtimes = {k: p.stat().st_mtime for k, p in files.items()}
                break
            time.sleep(interval)
    except KeyboardInterrupt:
        print("Stopped.")


def main():
    parser = argparse.ArgumentParser(
        description="Push card templates to Anki via AnkiConnect"
    )
    parser.add_argument(
        "--watch", "-w", action="store_true", help="Watch files and sync on change"
    )
    parser.add_argument(
        "--model", "-m", default=MODEL_NAME, help=f"Note type name (default: {MODEL_NAME})"
    )
    parser.add_argument(
        "--interval", "-i", type=float, default=2,
        help="Watch polling interval in seconds (default: 2)",
    )
    parser.add_argument(
        "--dry-run", "-n", action="store_true",
        help="Show what would be synced without making changes",
    )
    args = parser.parse_args()

    for fp in [FRONT_FILE, BACK_FILE, CSS_FILE]:
        if not fp.exists():
            raise SystemExit(f"File not found: {fp}")

    try:
        anki("version")
    except requests.ConnectionError:
        raise SystemExit(
            "Cannot reach AnkiConnect (http://127.0.0.1:8765).\n"
            "Is Anki running with the AnkiConnect add-on installed?\n"
            "Add-on code: 2055492159"
        )

    if args.watch:
        watch(args.model, args.interval)
    else:
        sync(args.model, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
