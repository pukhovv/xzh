"""Book-vs-deck gap analysis: which characters and words in a book
are missing from an Anki deck.

Usage:
    python scripts/analysis/gap.py --book books/qfl.txt --deck xiezh

Reads:
    The book text file (txt, extracted from epub).

Queries Anki via AnkiConnect (Anki must be running with the AnkiConnect add-on).
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Optional

import jieba
import logging

from stats import AnkiConnect

jieba.setLogLevel(logging.WARNING)


def find_script_dir() -> Path:
    return Path(__file__).resolve().parent


def clean_text(text: str) -> str:
    lines: list[str] = []
    skip_block = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(
            r"^(ISBN|图书在版编目|中国版本图书馆|[IVX]+\.)",
            stripped,
        ):
            skip_block = True
            continue
        if skip_block:
            if re.match(r"^\d{4}\.\d+$", stripped) or stripped.startswith(
                "中国版本图书馆"
            ):
                continue
            skip_block = False
        lines.append(stripped)
    return "\n".join(lines)


def extract_chars(text: str) -> Counter[str]:
    return Counter(re.findall(r"[\u4e00-\u9fff]", text))


def extract_words(text: str) -> Counter[str]:
    tokens = jieba.lcut(text)
    return Counter(t for t in tokens if re.match(r"[\u4e00-\u9fff]+", t))


def main() -> None:
    script_dir = find_script_dir()
    default_book = script_dir.parent.parent.parent / "books" / "qfl.txt"

    p = argparse.ArgumentParser(description="Book-vs-deck gap analysis")
    p.add_argument("--book", type=Path, default=default_book,
                   help="Path to book txt file")
    p.add_argument("--deck", default="xiezh", help="Anki deck name")
    p.add_argument("--field", default="text-sc",
                   help="Note field for word (default: text-sc)")
    p.add_argument("--anki-url", default="http://127.0.0.1:8765",
                   help="AnkiConnect URL")
    p.add_argument("--threshold", type=float, default=90.0,
                   help="Token coverage threshold %% for readiness (default: 90)")
    args = p.parse_args()

    anki = AnkiConnect(args.anki_url)
    if not anki.check():
        raise SystemExit(
            f"Cannot reach AnkiConnect ({args.anki_url}).\n"
            "Is Anki running with the AnkiConnect add-on installed?"
        )

    book_path: Path = args.book.resolve()
    if not book_path.exists():
        raise SystemExit(f"Book not found: {book_path}")

    raw_text = book_path.read_text(encoding="utf-8")
    text = clean_text(raw_text)
    chars_only = "".join(re.findall(r"[\u4e00-\u9fff]+", text))
    if not chars_only:
        raise SystemExit(f"No Chinese characters found in {book_path}")

    book_chars = extract_chars(text)
    book_words = extract_words(text)

    deck_words, deck_chars, deck_singles = anki.fetch_deck_words(
        args.deck, args.field
    )

    # chars
    missing_chars = sorted(
        [c for c in book_chars if c not in deck_chars],
        key=book_chars.get, reverse=True,
    )
    char_total = sum(book_chars.values())
    char_covered = sum(book_chars[c] for c in book_chars if c in deck_chars)
    char_pct = char_covered / char_total * 100 if char_total else 0

    # words (strict: exact match in deck)
    word_total = sum(book_words.values())
    word_unique = len(book_words)
    strict_covered = sum(book_words[w] for w in book_words if w in deck_words)
    missing_strict = sorted(
        [(w, book_words[w]) for w in book_words if w not in deck_words],
        key=lambda x: x[1], reverse=True,
    )
    strict_pct = strict_covered / word_total * 100 if word_total else 0

    # words (composite: all chars known)
    missing_comp: list[tuple[str, int]] = []
    comp_covered = 0
    for w, cnt in book_words.items():
        if set(w).issubset(deck_chars):
            comp_covered += cnt
        else:
            missing_comp.append((w, cnt))
    missing_comp.sort(key=lambda x: x[1], reverse=True)
    comp_pct = comp_covered / word_total * 100 if word_total else 0

    threshold = args.threshold
    char_ok = char_pct >= threshold
    strict_ok = strict_pct >= threshold
    comp_ok = comp_pct >= threshold
    ready = char_ok and comp_ok

    print(f"book: {book_path.name}")
    print(f"deck: {args.deck} ({len(deck_words)} words, {len(deck_chars)} chars, "
          f"{len(deck_singles)} singles)")
    print()

    # chars stats
    char_unique = len(book_chars)
    char_covered_unique = char_unique - len(missing_chars)
    print(f"{'=' * 55}")
    print(f"  Characters")
    print(f"{'=' * 55}")
    print(f"  Total tokens:   {char_total:>8}")
    print(f"  Unique items:   {char_unique:>8}")
    print(f"  In deck (uniq): {char_covered_unique:>8}  "
          f"({char_covered_unique/char_unique*100:5.1f}%)")
    print(f"  In deck (all):  {char_covered:>8}  ({char_pct:5.1f}%)")
    print(f"  Missing:        {len(missing_chars):>8}")

    # words strict stats
    strict_covered_unique = word_unique - len(missing_strict)
    print(f"\n{'=' * 55}")
    print(f"  Words (strict — exact match in deck)")
    print(f"{'=' * 55}")
    print(f"  Total tokens:   {word_total:>8}")
    print(f"  Unique items:   {word_unique:>8}")
    print(f"  In deck (uniq): {strict_covered_unique:>8}  "
          f"({strict_covered_unique/word_unique*100:5.1f}%)")
    print(f"  In deck (all):  {strict_covered:>8}  ({strict_pct:5.1f}%)")
    print(f"  Missing:        {len(missing_strict):>8}")

    # words composite stats
    comp_covered_unique = word_unique - len(missing_comp)
    print(f"\n{'=' * 55}")
    print(f"  Words (composite — all chars known)")
    print(f"{'=' * 55}")
    print(f"  Total tokens:   {word_total:>8}")
    print(f"  Unique items:   {word_unique:>8}")
    print(f"  In deck (uniq): {comp_covered_unique:>8}  "
          f"({comp_covered_unique/word_unique*100:5.1f}%)")
    print(f"  In deck (all):  {comp_covered:>8}  ({comp_pct:5.1f}%)")
    print(f"  Missing:        {len(missing_comp):>8}")

    sym = {True: "PASS", False: "FAIL"}
    marker = "  READY" if ready else "  NOT READY"
    print(f"\n{'=' * 55}")
    print(f"  READINESS  (threshold: {threshold:.0f}%){marker}")
    print(f"{'=' * 55}")
    print(f"  Chars:             {char_pct:5.1f}%  [{sym[char_ok]:>4}]")
    print(f"  Words (strict):    {strict_pct:5.1f}%  [{sym[strict_ok]:>4}]")
    print(f"  Words (composite): {comp_pct:5.1f}%  [{sym[comp_ok]:>4}]")

    print(f"\n--- missing chars ---")
    print(" ".join(missing_chars))

    print(f"\n--- missing words (strict) ---")
    print(" ".join(w for w, _ in missing_strict))

    print(f"\n--- missing words (composite) ---")
    print(" ".join(w for w, _ in missing_comp))


if __name__ == "__main__":
    main()
