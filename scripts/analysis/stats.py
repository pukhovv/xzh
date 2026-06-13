"""Coverage analysis for an Anki deck: frequency + HSK per-level word stats.

Usage:
    python scripts/analysis/stats.py DECK_FILE [--build-dir build/] [--no-plot] [--limit N]

Reads:
    DECK_FILE           — Anki deck export (one line per note: word[pinyin] definition)
    build/freqs.json    — full character frequency list
    build/chars.json    — selected characters + raw frequencies
    build/hsk.json      — HSK word lists per level
"""

import json
import argparse
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt


def find_script_dir() -> Path:
    return Path(__file__).resolve().parent


def parse_deck(path: str) -> tuple[set[str], set[str], set[str]]:
    """Parse an Anki deck export file.

    Expected format (one note per line):
        word[pinyin] definition
        # comments are skipped

    Returns (words, chars, singles) where:
        words   — set of all words (whatever precedes '[')
        chars   — set of all unique characters across all words
        singles — set of single-character words
    """
    words: set[str] = set()
    chars: set[str] = set()
    singles: set[str] = set()

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line[0] == "#":
                continue
            word = line.split("[")[0].strip()
            if not word:
                continue
            words.add(word)
            chars.update(word)
            if len(word) == 1:
                singles.add(word)

    return words, chars, singles


def load_freqs(build_dir: Path) -> str:
    """Load character frequency string from build/freqs.json."""
    return json.loads((build_dir / "freqs.json").read_text(encoding="utf-8"))


def load_chars(build_dir: Path) -> str:
    """Load raw frequency character list from build/chars.json."""
    data = json.loads((build_dir / "chars.json").read_text(encoding="utf-8"))
    return data["freqs"]


def load_hsk(build_dir: Path) -> Optional[dict[int, list[str]]]:
    """Load HSK word lists per level from build/hsk.json."""
    path = build_dir / "hsk.json"
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    result: dict[int, list[str]] = {}
    if isinstance(raw, dict):
        for key, words in raw.items():
            try:
                lvl = int(key)
            except (ValueError, TypeError):
                continue
            if isinstance(words, list):
                result[lvl] = words
    return result if result else None


def hsk_coverage(hsk: dict[int, list[str]], deck_words: set[str]) -> list[tuple[int, str]]:
    """Print per-level HSK word coverage stats.

    Returns a list of (level, word) for missing words, sorted by level then list order.
    """
    all_hsk = set()
    for words in hsk.values():
        all_hsk.update(words)

    in_deck = all_hsk & deck_words
    all_missing: list[tuple[int, str]] = []

    print(f"\n{'HSK level':>10} {'total':>7} {'in deck':>8} {'%':>6}  missing")
    print("-" * 72)

    for lvl in sorted(hsk):
        words = hsk[lvl]
        total = len(words)
        covered = len(set(words) & deck_words)
        missing = set(words) - deck_words
        pct = covered / total * 100 if total else 0
        top = " ".join(w for w in words if w in missing)[:80]
        label = f"{'HSK 7-9' if lvl == 7 else 'HSK ' + str(lvl)}"
        print(f"{label:>10} {total:>7} {covered:>8} {pct:>5.1f}%  {top}")
        for w in words:
            if w in missing:
                all_missing.append((lvl, w))

    total_all = len(all_hsk)
    covered_all = len(in_deck)
    pct_all = covered_all / total_all * 100 if total_all else 0
    print("-" * 72)
    print(f"{'ALL':>10} {total_all:>7} {covered_all:>8} {pct_all:>5.1f}%")

    return all_missing


def coverage_plot(freq: str, deck_chars: set[str], limit: int = 3000) -> None:
    """Plot cumulative character frequency coverage curve."""
    found = [sum(1 for j in range(i + 1) if freq[j] in deck_chars)
             for i in range(min(limit, len(freq)))]
    total = len(found)
    plt.figure(figsize=(12, 8))
    plt.plot(range(total), found, "b-", linewidth=2)
    plt.plot([0, total], [0, total], "r--", alpha=0.5, label="perfect")
    for ratio, color in [
        (1.0, "green"),
        (0.98, "red"),
        (0.95, "purple"),
        (0.90, "orange"),
    ]:
        for i in range(total):
            if found[i] / (i + 1) < ratio:
                plt.axvline(x=i, color=color, linewidth=2,
                            label=f"<{ratio * 100:.0f}% at {i}")
                break
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.title("Character frequency coverage")
    plt.xlabel("Frequency rank")
    plt.ylabel("Characters in deck")
    plt.show()


def main() -> None:
    script_dir = find_script_dir()
    default_build = script_dir.parent.parent / "build"

    p = argparse.ArgumentParser(description="xzh deck coverage analysis")
    p.add_argument("deck", nargs="?", default=None,
                   help="Anki deck export file (one note per line)")
    p.add_argument("--build-dir", type=Path, default=default_build,
                   help="Path to the build directory")
    p.add_argument("--no-plot", action="store_true",
                   help="Skip the matplotlib plot")
    p.add_argument("--limit", type=int, default=3000,
                   help="Max frequency rank to plot (default: 3000)")
    args = p.parse_args()

    build_dir: Path = args.build_dir.resolve()

    # Load frequency data from build
    freq = load_freqs(build_dir)
    raw_freqs = load_chars(build_dir)
    hsk = load_hsk(build_dir)

    # --- Deck analysis ---
    if args.deck:
        deck_words, deck_chars, deck_singles = parse_deck(args.deck)

        # Character frequency coverage
        total_c = len(raw_freqs)
        in_deck_c = sum(1 for c in raw_freqs if c in deck_chars)
        missing_c = sorted(set(raw_freqs[:in_deck_c + 500]) - deck_chars,
                           key=lambda c: raw_freqs.index(c))
        rare_c = sorted(deck_chars - set(raw_freqs))

        print(f"deck words: {len(deck_words)}  singles: {len(deck_singles)}  chars: {len(deck_chars)}")
        print(f"char freq list: {total_c}  in deck: {in_deck_c}  "
              f"coverage: {in_deck_c / total_c * 100:.1f}%")
        if rare_c:
            print(f"rare (in deck, not in freq): {''.join(rare_c[:50])}")

        # HSK word coverage
        if hsk:
            hsk_missing = hsk_coverage(hsk, deck_words)
        else:
            hsk_missing = []
            print(f"\n  No HSK data at {build_dir / 'hsk.json'}")
            print(f"  Run:  python build.py    (to download HSK word lists)")

        # --- Extended lists ---
        if missing_c:
            print(f"\n--- next {min(250, len(missing_c))} missing chars (by frequency) ---")
            print("".join(missing_c[:250]))

        if hsk_missing:
            limit = min(1000, len(hsk_missing))
            print(f"\n--- next {limit} missing HSK words (by level) ---")
            print(" ".join(w for _, w in hsk_missing[:limit]))

        # Plot
        if not args.no_plot:
            coverage_plot(raw_freqs, deck_chars, args.limit)
    else:
        # Just show build data summary
        print(f"char freq list: {len(raw_freqs)} chars")
        if hsk:
            total_hsk = sum(len(v) for v in hsk.values())
            print(f"HSK words: {total_hsk} across {len(hsk)} levels")
            for lvl in sorted(hsk):
                label = "7-9" if lvl == 7 else str(lvl)
                print(f"  HSK {label}: {len(hsk[lvl])} words")
        else:
            print(f"\n  No HSK data at {build_dir / 'hsk.json'}")
        print("\n  Pass a deck file to analyze coverage.")


if __name__ == "__main__":
    main()
