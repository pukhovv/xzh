"""Collect HSK 3.0 word lists into a structured JSON for stats.py.

Reads per-level text files from dset/ (tab-separated: word<TAB>pinyin<TAB>...)
and writes a combined hsk.json to the build directory.
"""
import json
import sys
from pathlib import Path

HSK_FILES = {
    1:  "hsk_words_L1.txt",
    2:  "hsk_words_L2.txt",
    3:  "hsk_words_L3.txt",
    4:  "hsk_words_L4.txt",
    5:  "hsk_words_L5.txt",
    6:  "hsk_words_L6.txt",
    7:  "hsk_words_L79.txt",  # levels 7-9 combined
}


def main() -> None:
    build = Path(sys.argv[1])
    dset = build / "dset"

    if not any((dset / f).exists() for f in HSK_FILES.values()):
        print("  (no HSK files in dset/ — skipping)")
        return

    out: dict[str, list[str]] = {}
    for lvl, filename in sorted(HSK_FILES.items()):
        path = dset / filename
        if not path.exists():
            continue
        words: list[str] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            # lines are tab-separated: word \t pinyin \t ...
            word = line.split("\t")[0].strip()
            if word:
                words.append(word)
        out[str(lvl)] = words
        label = "7-9" if lvl == 7 else f"L{lvl}"
        print(f"  HSK {label}: {len(words)} words")

    if not out:
        print("  (no HSK files parsed)")
        return

    op = build / "hsk.json"
    with op.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  wrote hsk.json ({op.stat().st_size / 1024:.0f}K)")


if __name__ == "__main__":
    main()
