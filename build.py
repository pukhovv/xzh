#!/usr/bin/env python3
import gzip
import os
import shutil
import subprocess
import argparse
import zipfile
import time
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = Path(__file__).resolve().parent
BUILD = HERE / "build"
DSET = BUILD / "dset"
BS = HERE / "scripts" / "build"

SOURCES: dict[str, dict] = {
    "SUBTLEX-CH-WF": {
        "urls": ["https://www.ugent.be/pp/experimentele-psychologie/en/research/documents/subtlexch/subtlexchwf.zip"],
        "zip": "SUBTLEX-CH-WF",
    },
    "SUBTLEX-CH-CHR": {
        "urls": ["https://www.ugent.be/pp/experimentele-psychologie/en/research/documents/subtlexch/subtlexchchr.zip"],
        "zip": "SUBTLEX-CH-CHR",
    },
    "cedict_ts.u8": {
        "urls": ["https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz"],
        "gunzip": "cedict_ts.u8",
    },
    "cjk-decomp-0.4.0.txt": {
        "urls": [
            "https://raw.githubusercontent.com/amake/cjk-decomp/master/cjk-decomp.txt",
            "https://raw.githubusercontent.com/cosmi/chinese-toolkit/master/chinese-toolkit/cjk-decomp-0.4.0.txt",
        ],
    },
    "zh_cn.txt.gz": {
        "urls": ["https://object.pouta.csc.fi/OPUS-OpenSubtitles/v2018/mono/zh_cn.txt.gz"],
    },
    # HSK 3.0 word lists (tab-separated: word <TAB> pinyin <TAB> ...)
    "hsk_words_L1.txt": {
        "urls": ["https://raw.githubusercontent.com/krmanik/HSK-3.0-words-list/main/New%20HSK%20(2021)/HSK%20List/HSK%201.txt"],
    },
    "hsk_words_L2.txt": {
        "urls": ["https://raw.githubusercontent.com/krmanik/HSK-3.0-words-list/main/New%20HSK%20(2021)/HSK%20List/HSK%202.txt"],
    },
    "hsk_words_L3.txt": {
        "urls": ["https://raw.githubusercontent.com/krmanik/HSK-3.0-words-list/main/New%20HSK%20(2021)/HSK%20List/HSK%203.txt"],
    },
    "hsk_words_L4.txt": {
        "urls": ["https://raw.githubusercontent.com/krmanik/HSK-3.0-words-list/main/New%20HSK%20(2021)/HSK%20List/HSK%204.txt"],
    },
    "hsk_words_L5.txt": {
        "urls": ["https://raw.githubusercontent.com/krmanik/HSK-3.0-words-list/main/New%20HSK%20(2021)/HSK%20List/HSK%205.txt"],
    },
    "hsk_words_L6.txt": {
        "urls": ["https://raw.githubusercontent.com/krmanik/HSK-3.0-words-list/main/New%20HSK%20(2021)/HSK%20List/HSK%206.txt"],
    },
    "hsk_words_L79.txt": {
        "urls": ["https://raw.githubusercontent.com/krmanik/HSK-3.0-words-list/main/New%20HSK%20(2021)/HSK%20List/HSK%207-9.txt"],
    },
}


def fetch(url: str, dest: Path) -> bool:
    """Download a URL to dest with retries and exponential backoff."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            req = Request(url, headers={"User-Agent": "xzh-build/1.0"})
            with urlopen(req, timeout=30) as r:
                with dest.open("wb") as f:
                    shutil.copyfileobj(r, f, 1024 * 1024)
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                delay = 2 ** attempt
                print(f"    retry in {delay}s: {e}")
                time.sleep(delay)
            else:
                print(f"    FAIL: {e}")
    return False


def _download_one(info: dict, dest: Path, tgt: Path | None) -> bool:
    """Download a single source; returns True on success."""
    dl = dest if not ("gunzip" in info or "zip" in info) else dest.with_suffix(dest.suffix + ".tmp")
    for url in info["urls"]:
        print(f"  {dest.name}: {url}")
        if fetch(url, dl):
            return True
    print(f"  {dest.name}: not found")
    return False


def get(name: str, info: dict) -> bool:
    dest = DSET / name
    tgt = None
    if "gunzip" in info:
        tgt = DSET / info["gunzip"]
    elif "zip" in info:
        tgt = DSET / info["zip"]
    real = tgt or dest
    if real.exists():
        print(f"  {name}: cached")
        return True

    if not info.get("urls"):
        print(f"  {name}: no URLs")
        return False

    if not _download_one(info, dest, tgt):
        return False

    dl = dest if not ("gunzip" in info or "zip" in info) else dest.with_suffix(dest.suffix + ".tmp")

    if "gunzip" in info:
        print(f"  gunzip -> {tgt}")
        with gzip.open(dl, "rb") as gz:
            with tgt.open("wb") as out:
                shutil.copyfileobj(gz, out, 1024 * 1024)
        dl.unlink()
    elif "zip" in info:
        print(f"  unzip -> {tgt}")
        zf = zipfile.ZipFile(dl)
        zf.extract(info["zip"], str(DSET))
        dl.unlink()

    print(f"  ok ({real.stat().st_size} bytes)")
    return True


def run(script: str) -> None:
    cmd = [sys.executable, str(BS / script), str(BUILD)]
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = "0"
    print(f"  {script}")
    r = subprocess.run(cmd, cwd=str(HERE), env=env)
    if r.returncode != 0:
        sys.exit(f"FAILED: {script}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--no-dl", action="store_true")
    p.add_argument("--dl-only", action="store_true")
    p.add_argument("--skip-sents", action="store_true")
    args = p.parse_args()

    DSET.mkdir(parents=True, exist_ok=True)

    if not args.no_dl:
        print("=== download ===")
        # Parallel downloads: launch all, some are small, some large
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(get, name, info): name for name, info in SOURCES.items()}
            for future in as_completed(futures):
                name = futures[future]
                if not future.result():
                    executor.shutdown(wait=False, cancel_futures=True)
                    sys.exit(1)

    if args.dl_only:
        return

    print("\n=== build ===")
    run("freqs.py")
    run("words.py")
    run("cedict.py")
    run("graph.py")
    run("hsk.py")
    if not args.skip_sents:
        run("sents.py")

    res = BUILD / "res"
    intm = [f for f in BUILD.iterdir() if f.is_file() and f.suffix == ".json" and not f.name.startswith("_")]
    deck = list(res.iterdir()) if res.is_dir() else []
    print(f"\n=== intermediate ({BUILD}/) ===")
    for f in sorted(intm):
        print(f"  {f.name:32s} {f.stat().st_size / 1024:6.0f}K")
    print(f"\n=== deck ({res}/) ===")
    for f in sorted(deck):
        print(f"  {f.name:32s} {f.stat().st_size / 1024:6.0f}K")
    print("done")


if __name__ == "__main__":
    main()
