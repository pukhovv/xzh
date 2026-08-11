"""Coverage analysis for an Anki deck via AnkiConnect: frequency + HSK per-level word stats.

Usage:
    python scripts/analysis/stats.py [--list-decks]
    python scripts/analysis/stats.py --deck DECK_NAME [--build-dir build/] [--no-plot] [--limit N]
    python scripts/analysis/stats.py --deck "Chinese::HSK 1"

Reads:
    build/freqs.json    — full character frequency list
    build/chars.json    — selected characters + raw frequencies
    build/hsk.json      — HSK word lists per level

Queries Anki via AnkiConnect (Anki must be running with the AnkiConnect add-on).
"""

import json
import argparse
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import requests


class AnkiConnect:
    def __init__(self, url: str = "http://127.0.0.1:8765"):
        self.url = url

    def _call(self, action: str, **params):
        resp = requests.post(
            self.url,
            json={"action": action, "version": 6, "params": params},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("error"):
            raise RuntimeError(f"AnkiConnect error: {data['error']}")
        return data["result"]

    def check(self) -> bool:
        try:
            self._call("version")
            return True
        except requests.ConnectionError:
            return False

    def deck_names(self) -> list[str]:
        return self._call("deckNames")

    def find_notes(self, query: str) -> list[int]:
        return self._call("findNotes", query=query)

    def notes_info(self, notes: list[int]) -> list[dict]:
        return self._call("notesInfo", notes=notes)

    def _field_value(self, note: dict, field: str) -> str:
        return note["fields"].get(field, {}).get("value", "").strip()

    def fetch_deck_words(
        self, deck_name: str, field: str = "text-sc"
    ) -> tuple[set[str], set[str], set[str]]:
        note_ids = self.find_notes(f'deck:"{deck_name}"')
        if not note_ids:
            return set(), set(), set()

        notes = self.notes_info(note_ids)

        words: set[str] = set()
        chars: set[str] = set()
        singles: set[str] = set()

        for note in notes:
            word = self._field_value(note, field)
            if word:
                words.add(word)
                chars.update(word)
                if len(word) == 1:
                    singles.add(word)

        return words, chars, singles

    def fetch_deck_dump(self, deck_name: str) -> list[tuple[str, str, str]]:
        note_ids = self.find_notes(f'deck:"{deck_name}"')
        if not note_ids:
            return []

        notes = self.notes_info(note_ids)

        entries: list[tuple[str, str, str]] = []
        for note in notes:
            sc = self._field_value(note, "text-sc")
            tc = self._field_value(note, "text-tc")
            py = self._field_value(note, "pinyin")
            if sc:
                entries.append((sc, tc, py))

        return entries


def find_script_dir() -> Path:
    return Path(__file__).resolve().parent


def load_freqs(build_dir: Path) -> str:
    return json.loads((build_dir / "freqs.json").read_text(encoding="utf-8"))


def load_chars(build_dir: Path) -> str:
    data = json.loads((build_dir / "chars.json").read_text(encoding="utf-8"))
    return data["freqs"]


def load_hsk(build_dir: Path) -> Optional[dict[int, list[str]]]:
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
    found = [
        sum(1 for j in range(i + 1) if freq[j] in deck_chars)
        for i in range(min(limit, len(freq)))
    ]
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
                plt.axvline(
                    x=i, color=color, linewidth=2, label=f"<{ratio * 100:.0f}% at {i}"
                )
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

    p = argparse.ArgumentParser(description="xzh deck coverage analysis via AnkiConnect")
    p.add_argument(
        "--list-decks",
        action="store_true",
        help="List available Anki decks and exit",
    )
    p.add_argument(
        "--deck",
        default=None,
        help="Anki deck name to analyze (use --list-decks to see available decks)",
    )
    p.add_argument(
        "--field",
        default="text-sc",
        help="Note field containing the Chinese word (default: text-sc)",
    )
    p.add_argument(
        "--anki-url",
        default="http://127.0.0.1:8765",
        help="AnkiConnect URL (default: http://127.0.0.1:8765)",
    )
    p.add_argument(
        "--build-dir",
        type=Path,
        default=default_build,
        help="Path to the build directory",
    )
    p.add_argument(
        "--no-plot",
        action="store_true",
        help="Skip the matplotlib plot",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=3000,
        help="Max frequency rank to plot (default: 3000)",
    )
    p.add_argument(
        "--dump",
        action="store_true",
        help="Dump the collection (text-sc | text-tc | pinyin) to a text file",
    )
    p.add_argument(
        "--dump-dir",
        default="progress-new",
        help="Directory to write dump file (default: progress-new)",
    )
    args = p.parse_args()

    anki = AnkiConnect(args.anki_url)

    if not anki.check():
        raise SystemExit(
            f"Cannot reach AnkiConnect ({args.anki_url}).\n"
            "Is Anki running with the AnkiConnect add-on installed?\n"
            "Add-on code: 2055492159"
        )

    if args.list_decks:
        decks = anki.deck_names()
        print(f"Available decks ({len(decks)}):")
        for d in sorted(decks):
            print(f"  {d}")
        return

    if not args.deck:
        p.print_help()
        print("\nTip: use --list-decks to see available decks, then --deck NAME to analyze one.")
        return

    if args.dump:
        dump_dir = Path(args.dump_dir)
        dump_dir.mkdir(parents=True, exist_ok=True)
        entries = anki.fetch_deck_dump(args.deck)
        dump_file = dump_dir / f"{args.deck.replace('::', '_')}.txt"
        with open(dump_file, "w", encoding="utf-8") as f:
            for sc, tc, py in entries:
                f.write(f"{sc}\t{tc}\t{py}\n")
        print(f"Dumped {len(entries)} entries to {dump_file}")
        return

    build_dir: Path = args.build_dir.resolve()
    freq = load_freqs(build_dir)
    raw_freqs = load_chars(build_dir)
    hsk = load_hsk(build_dir)

    deck_words, deck_chars, deck_singles = anki.fetch_deck_words(args.deck, args.field)

    if not deck_words:
        print(f"No words found in deck '{args.deck}' (field: {args.field}).")
        print("Available decks:")
        for d in anki.deck_names():
            print(f"  {d}")
        return

    total_c = len(raw_freqs)
    in_deck_c = sum(1 for c in raw_freqs if c in deck_chars)
    missing_c = sorted(
        set(raw_freqs[: in_deck_c + 500]) - deck_chars,
        key=lambda c: raw_freqs.index(c),
    )
    rare_c = sorted(deck_chars - set(raw_freqs))

    print(f"deck words: {len(deck_words)}  singles: {len(deck_singles)}  chars: {len(deck_chars)}")
    print(
        f"char freq list: {total_c}  in deck: {in_deck_c}  "
        f"coverage: {in_deck_c / total_c * 100:.1f}%"
    )
    if rare_c:
        print(f"rare (in deck, not in freq): {''.join(rare_c[:50])}")

    if hsk:
        hsk_missing = hsk_coverage(hsk, deck_words)
    else:
        hsk_missing = []
        print(f"\n  No HSK data at {build_dir / 'hsk.json'}")
        print(f"  Run:  python build.py    (to download HSK word lists)")

    if missing_c:
        print(f"\n--- next {min(250, len(missing_c))} missing chars (by frequency) ---")
        print("".join(missing_c[:250]))

    if hsk_missing:
        limit = min(1000, len(hsk_missing))
        print(f"\n--- next {limit} missing HSK words (by level) ---")
        print(" ".join(w for _, w in hsk_missing[:limit]))

    if not args.no_plot:
        coverage_plot(raw_freqs, deck_chars, args.limit)


if __name__ == "__main__":
    main()
