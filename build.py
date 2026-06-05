#!/usr/bin/env python3
import os, sys, gzip, shutil, subprocess, argparse, zipfile
from urllib.request import Request, urlopen

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build")
DSET = os.path.join(BUILD, "dset")
BS = os.path.join(HERE, "scripts", "build")

SOURCES = {
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
}


def fetch(url, dest):
    try:
        req = Request(url, headers={"User-Agent": "xzh-build/1.0"})
        with urlopen(req, timeout=30) as r:
            with open(dest, "wb") as f:
                shutil.copyfileobj(r, f, 1024 * 1024)
        return True
    except Exception as e:
        print(f"    FAIL: {e}")
        return False


def get(name, info):
    dest = os.path.join(DSET, name)
    tgt = None
    if "gunzip" in info:
        tgt = os.path.join(DSET, info["gunzip"])
    elif "zip" in info:
        tgt = os.path.join(DSET, info["zip"])
    real = tgt or dest
    if os.path.exists(real):
        print(f"  {name}: cached")
        return True

    if not info.get("urls"):
        print(f"  {name}: no URLs")
        return False
    for url in info["urls"]:
        dl = dest if not ("gunzip" in info or "zip" in info) else dest + ".tmp"
        print(f"  {name}: {url}")
        if fetch(url, dl):
            break
    else:
        print(f"  {name}: not found")
        return False

    if "gunzip" in info:
        print(f"  gunzip -> {tgt}")
        with gzip.open(dl, "rb") as gz:
            with open(tgt, "wb") as out:
                shutil.copyfileobj(gz, out, 1024 * 1024)
        os.remove(dl)
    elif "zip" in info:
        print(f"  unzip -> {tgt}")
        zf = zipfile.ZipFile(dl)
        zf.extract(info["zip"], DSET)
        os.remove(dl)

    print(f"  ok ({os.path.getsize(real)} bytes)")
    return True


def run(script):
    cmd = [sys.executable, os.path.join(BS, script), BUILD]
    print(f"  {script}")
    r = subprocess.run(cmd, cwd=HERE)
    if r.returncode != 0:
        sys.exit(f"FAILED: {script}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--no-dl", action="store_true")
    p.add_argument("--dl-only", action="store_true")
    p.add_argument("--skip-sents", action="store_true")
    args = p.parse_args()

    os.makedirs(DSET, exist_ok=True)

    if not args.no_dl:
        print("=== download ===")
        for name, info in SOURCES.items():
            if not get(name, info):
                sys.exit(1)

    if args.dl_only:
        return

    print("\n=== build ===")
    run("freqs.py")
    run("words.py")
    run("cedict.py")
    run("graph.py")
    if not args.skip_sents:
        run("sents.py")

    res = os.path.join(BUILD, "res")
    intm = [f for f in os.listdir(BUILD) if f.endswith(".json") and not f.startswith("_")]
    deck = os.listdir(res) if os.path.isdir(res) else []
    print(f"\n=== intermediate ({BUILD}/) ===")
    for f in sorted(intm):
        print(f"  {f:32s} {os.path.getsize(os.path.join(BUILD, f))/1024:6.0f}K")
    print(f"\n=== deck ({res}/) ===")
    for f in sorted(deck):
        print(f"  {f:32s} {os.path.getsize(os.path.join(res, f))/1024:6.0f}K")
    print("done")

if __name__ == "__main__":
    main()
