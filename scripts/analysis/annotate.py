"""Build a study edition of a Chinese book: flag unknown words/characters
against an Anki deck, with tone-colored ruby pinyin, a rarity-tier underline,
and English glosses via EPUB3 popup footnotes.

Usage:
    python scripts/analysis/annotate.py --book books/BOOK.epub --deck xiezh \
        [--names 张三,李四 --title 书名 --author 作者]
"""
from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import quote

import jieba
import jieba.posseg as pseg
import logging

import ebooklib
from bs4 import BeautifulSoup
from ebooklib import epub

from gap import clean_text
from stats import AnkiConnect

jieba.setLogLevel(logging.WARNING)

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent.parent / "build"

# ---- tier (rarity/investment) underline colors: cold(rare) -> warm(common) ----
TIER_COLORS = ["#1a237e", "#1565c0", "#00897b", "#f57c00", "#d32f2f"]

# tone -> color (mirrors card/styling.css)
TONE_COLORS = {1: "#e30000", 2: "#02b31c", 3: "#1510f0", 4: "#8900bf", 5: "#777777"}

_VOWEL_TONE = {
    "a": "āáǎà", "e": "ēéěè", "i": "īíǐì",
    "o": "ōóǒò", "u": "ūúǔù", "ü": "ǖǘǚǜ",
}


def mark_tone(base: str, tone: int) -> str:
    """Place a tone mark on a plain syllable base. tone in 1..4."""
    idx = tone - 1
    for v in ("a", "e", "o"):
        if v in base:
            i = base.index(v)
            return base[:i] + _VOWEL_TONE[v][idx] + base[i + 1:]
    i = max(base.rfind("i"), base.rfind("u"), base.rfind("ü"))
    if i < 0:
        return base
    v = base[i]
    return base[:i] + _VOWEL_TONE[v][idx] + base[i + 1:]


def num2tone(syl: str):
    """'kan4' -> ('kàn', 4); 'nu:3' -> ('nǚ', 3); 'le5' -> ('le', 5)."""
    m = re.match(r"^([A-Za-z:]+?)(\d+)?$", syl)
    if not m:
        return syl, 5
    base = m.group(1).replace("u:", "ü").replace("U:", "Ü")
    tone = int(m.group(2)[0]) if m.group(2) else 5
    if tone == 5 or tone == 0:
        return base.lower(), 5
    return mark_tone(base.lower(), tone), tone


def word_pinyin(word: str, pmap: dict):
    """Return (list_of_tone_marked_pinyin, list_of_tones) for a word, or None."""
    readings = pmap.get(word)
    if not readings:
        return None
    syls = readings[0].split()
    if len(syls) != len(word):
        return None
    out, tones = [], []
    for s in syls:
        d, t = num2tone(s)
        out.append(d)
        tones.append(t)
    return out, tones


def char_pinyin(ch: str, pmap: dict):
    readings = pmap.get(ch)
    if not readings:
        return None
    return num2tone(readings[0].split()[0])


def tier(bf: int) -> int:
    if bf >= 21:
        return 4
    if bf >= 6:
        return 3
    if bf >= 3:
        return 2
    if bf == 2:
        return 1
    return 0


def load_data(deck: str, anki_url: str):
    words_rank = {w: i for i, w in enumerate(json.loads((BUILD / "words.json").read_text()))}
    freqs = json.loads((BUILD / "freqs.json").read_text())
    cedict_pinyin = json.loads((BUILD / "cedict.json").read_text())["pinyin"]
    defs = json.loads((BUILD / "cedict-defs.json").read_text())

    anki = AnkiConnect(anki_url)
    deck_words, deck_chars, _ = anki.fetch_deck_words(deck) if anki.check() else (None, None, None)
    source = "AnkiConnect"
    if deck_words is None:
        deck_words, deck_chars = set(), set()
        dump = HERE.parent.parent.parent / "progress-new" / f"{deck.replace('::', '_')}.txt"
        for line in dump.read_text().splitlines():
            p = line.split("\t")
            if p and p[0].strip():
                deck_words.add(p[0].strip())
        deck_chars = set("".join(deck_words))
        source = f"dump ({dump.name})"
    return words_rank, freqs, cedict_pinyin, defs, deck_words, deck_chars, source


NAME_FLAGS = {"nr", "ns", "nt", "nz", "nrfg", "nrt", "nrtj"}
PUNCT_FLAGS = {"x", "w"}
NUM_FLAGS = {"m", "q"}


def load_chapters(book_path: Path):
    """Return [(title, [paragraph]), ...] from an epub or plain-text file."""
    if book_path.suffix.lower() == ".epub":
        return _chapters_from_book(epub.read_epub(str(book_path)))
    text = clean_text(book_path.read_text(encoding="utf-8"))
    paras = [p for p in text.split("\n") if p.strip() and re.search(r"[\u4e00-\u9fff]", p)]
    return [("", paras)]


def _chapters_from_book(book):
    chapters = []
    for idref, linear in book.spine:
        if linear != "yes":
            continue
        doc = book.get_item_with_id(idref)
        if doc is None or doc.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
        soup = BeautifulSoup(doc.get_content(), "html.parser")
        title = ""
        for h in soup.find_all(["h1", "h2", "h3"]):
            t = h.get_text().strip()
            if t:
                title = t
                break
        paras = [p.get_text().strip() for p in soup.find_all("p") if p.get_text().strip()]
        if not paras:
            continue  # cover pages etc.
        chapters.append((title, paras))
    return chapters


class Annotator:
    def __init__(self, deck_words, deck_chars, words_rank, cedict_pinyin, defs,
                 threshold=800, pinyin_freq=5, names=()):
        self.deck_words = deck_words
        self.deck_chars = deck_chars
        self.words_rank = words_rank
        self.pmap = cedict_pinyin
        self.defs = defs
        self.threshold = threshold
        self.pinyin_freq = pinyin_freq
        self.names = set(names)
        self._fn = Counter()
        self._fnids = {}

    # word-level decision
    def is_name(self, w, flag):
        if w in self.names:
            return True
        # jieba posseg tags many common nouns as nr/ns; only trust it when the
        # token is not a real dictionary word.
        return flag in NAME_FLAGS and w not in self.pmap

    LOC_SUFFIX = "里上中下内外边旁面"

    def is_transparent(self, w, flag):
        """True if a word is a guessable 'X + locative' compound."""
        if flag == "i":  # idioms are opaque
            return False
        if not set(w).issubset(self.deck_chars):  # unknown char -> not guessable
            return False
        return w[-1] in self.LOC_SUFFIX

    def decide_word(self, w, flag):
        """-> 'punct' | 'name' | 'num' | 'known' | 'flag' | 'bare'"""
        if flag in PUNCT_FLAGS:
            return "punct"
        if not re.search(r"[\u4e00-\u9fff]", w):
            return "punct"
        if self.is_name(w, flag):
            return "name"
        if flag in NUM_FLAGS:
            return "num"
        if w in self.deck_words:
            return "known"
        if w in self.pmap:  # real lexical word (in CC-CEDICT)
            r = self.words_rank.get(w)
            if r is not None and r < self.threshold:
                return "known"   # known-by-frequency
            if self.is_transparent(w, flag):
                return "bare"    # guessable compound
            return "flag"
        return "bare"  # transparent collocation / rare compound

    def word_gloss(self, w):
        return self.defs.get(w)

    # ---------- rendering ----------
    def footnote(self, w, gloss):
        nid = self._fnids.setdefault(w, f"fn-{len(self._fnids) + 1}")
        pinyin = ""
        pp = word_pinyin(w, self.pmap)
        if pp:
            pinyin = "".join(pp[0])
        inner = f'<b>{html.escape(w)}</b> <i>{html.escape(pinyin)}</i> — {html.escape(gloss)}'
        pleco = f'plecoapi://x-callback-url/s?q={quote(w)}'
        inner += f' <a class="pleco" href="{pleco}" aria-label="Lookup in Pleco">鱼</a>'
        entry = f'<aside epub:type="footnote" id="{nid}"><p>{inner}</p></aside>'
        return nid, entry

    def render_word(self, w, flag, bf):
        kind = self.decide_word(w, flag)
        if kind in ("punct", "name", "num", "known"):
            return html.escape(w), None
        if kind == "bare":
            html_s, notes = self.render_chars(w, char_underline=True)
            return html_s, notes
        # kind == "flag": underline the word + gloss; pinyin only on unknown chars
        t = tier(bf)
        inner, _ = self.render_chars(w, char_underline=False)
        s = f'<span class="tr{t}">{inner}</span>'
        notes = []
        gloss = self.word_gloss(w)
        if gloss:
            nid, note = self.footnote(w, gloss)
            s = f'<a epub:type="noteref" href="#{nid}">{s}</a>'
            notes.append(note)
        return s, notes

    def render_chars(self, w, char_underline=True):
        """Tone-color + ruby + (optionally) underline unknown characters."""
        out, notes = [], []
        for ch in w:
            if not re.search(r"[\u4e00-\u9fff]", ch):
                out.append(html.escape(ch))
                continue
            if ch in self.deck_chars:
                out.append(html.escape(ch))
                continue
            # unknown char: tone-colored, ruby pinyin if rare, underline if standalone
            bf = self.char_freq.get(ch, 0)
            t = tier(bf)
            cp = char_pinyin(ch, self.pmap)
            tone = cp[1] if cp else 5
            tc = tone if tone in TONE_COLORS else 5
            inner = html.escape(ch)
            if bf < self.pinyin_freq and cp:
                inner = f'<ruby>{ch}<rt class="t{tc}">{html.escape(cp[0])}</rt></ruby>'
            inner = f'<span class="t{tc}">{inner}</span>'
            if char_underline:
                inner = f'<span class="tr{t}">{inner}</span>'
                gloss = self.word_gloss(ch)
                if gloss:
                    nid, note = self.footnote(ch, gloss)
                    inner = f'<a epub:type="noteref" href="#{nid}">{inner}</a>'
                    notes.append(note)
            out.append(inner)
        return "".join(out), notes

    def render_paragraph(self, pairs):
        body, notes = [], []
        for w, flag in pairs:
            if not w:
                continue
            bf = self.word_freq.get(w, 0)
            s, ns = self.render_word(w, flag, bf)
            body.append(s)
            if ns:
                notes.extend(ns)
        return "".join(body), notes


def build_epub(chapters, annotator, out_path: Path, book_title: str, book_author: str = ""):
    book = epub.EpubBook()
    book.set_identifier("study-edition")
    book.set_title(book_title)
    book.set_language("zh")
    if book_author:
        book.add_author(book_author)

    css = annotation_css()
    css += "body{font-family:'Noto Serif CJK SC',serif;line-height:1.9;}"
    css += "p{margin:0.3em 0;text-indent:2em;}"
    nav_css = epub.EpubItem(uid="style", file_name="style/study.css",
                            media_type="text/css", content=css)
    book.add_item(nav_css)

    total_notes = 0
    epub_chapters = []
    for i, (ch_title, paras) in enumerate(chapters):
        body, notes = [], []
        for para in paras:
            pairs = list(pseg.cut(para))
            html_s, ns = annotator.render_paragraph(pairs)
            body.append(f"<p>{html_s}</p>")
            notes.extend(ns)
        content = "".join(body)
        if notes:
            content += '<div class="footnotes">' + "".join(dict.fromkeys(notes)) + "</div>"
        total_notes += len(notes)
        ch = epub.EpubHtml(title=ch_title or f"Chapter {i + 1}", file_name=f"chap_{i + 1}.xhtml")
        ch.content = f"<html><body>{content}</body></html>"
        ch.add_item(nav_css)
        book.add_item(ch)
        epub_chapters.append(ch)

    book.toc = tuple(epub_chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav"] + epub_chapters
    epub.write_epub(str(out_path), book, {})
    return total_notes


def annotation_css():
    css = "a{color:inherit;text-decoration:none;}"
    for i in range(5):
        css += f".tr{i}{{border-bottom:2px solid {TIER_COLORS[i]};}}"
    for t, c in TONE_COLORS.items():
        css += f".t{t}{{color:{c};}}"
    css += "ruby{line-height:1.35;}rt{font-family:sans-serif;font-size:0.55em;}"
    css += "aside{font-size:0.85em;border-top:1px solid #ccc;margin-top:1em;}"
    css += "a.pleco{text-decoration:none;border:1px solid #999;border-radius:3px;padding:0 0.35em;margin-left:0.5em;font-size:0.85em;}"
    return css


def annotate_epub(book, annotator, out_path: Path, book_title=None, book_author=""):
    """Annotate an existing epub in place: only paragraph text is replaced, so
    the cover, stylesheet, headings and page structure are preserved."""
    if book_title and book_title != book.title:
        book.set_unique_metadata("DC", "title", book_title)
    if book_author:
        book.add_author(book_author)

    # the source book is EPUB2 (NCX only): emit a proper EPUB3 nav so that
    # conformant readers honor the epub:type popup footnotes below
    book.add_item(epub.EpubNav())

    style_item = epub.EpubItem(uid="study-style", file_name="style/study.css",
                               media_type="text/css", content=annotation_css())
    book.add_item(style_item)

    total_notes = 0
    for idref, linear in book.spine:
        if linear != "yes":
            continue
        doc = book.get_item_with_id(idref)
        if doc is None or doc.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
        soup = BeautifulSoup(doc.get_content(), "html.parser")
        notes = []
        for p in soup.find_all("p"):
            text = p.get_text().strip()
            if not text:
                continue
            pairs = list(pseg.cut(text))
            html_s, ns = annotator.render_paragraph(pairs)
            p.clear()
            p.append(BeautifulSoup(html_s, "html.parser"))
            notes.extend(ns)
        if notes and soup.body is not None:
            foot = soup.new_tag("div", **{"class": "footnotes"})
            foot.append(BeautifulSoup("".join(dict.fromkeys(notes)), "html.parser"))
            soup.body.append(foot)
        doc.add_item(style_item)
        doc.set_content(str(soup).encode("utf-8"))
        total_notes += len(notes)
    epub.write_epub(str(out_path), book, {})
    return total_notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", type=Path, required=True,
                    help="Input book (.epub preserves chapters, or plain .txt)")
    ap.add_argument("--deck", default="xiezh")
    ap.add_argument("--threshold", type=int, default=800)
    ap.add_argument("--pinyin-freq", type=int, default=5)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--title", default=None, help="Book title (default: input filename stem)")
    ap.add_argument("--author", default="", help="Book author")
    ap.add_argument("--names", default="",
                    help="Comma-separated list of character names to exclude from flags")
    args = ap.parse_args()

    words_rank, freqs, pmap, defs, deck_words, deck_chars, source = load_data(args.deck, "http://127.0.0.1:8765")
    print(f"deck source: {source}  words={len(deck_words)} chars={len(deck_chars)}")

    is_epub = args.book.suffix.lower() == ".epub"
    book = epub.read_epub(str(args.book)) if is_epub else None
    chapters = _chapters_from_book(book) if is_epub else load_chapters(args.book)
    all_paras = [p for _, paras in chapters for p in paras]
    print(f"chapters: {len(chapters)}  paragraphs: {len(all_paras)}")

    names = {n.strip() for n in args.names.split(",") if n.strip()}

    ann = Annotator(deck_words, deck_chars, words_rank, pmap, defs,
                    threshold=args.threshold, pinyin_freq=args.pinyin_freq, names=names)

    # pre-compute frequencies over the whole book
    word_freq = Counter()
    char_freq = Counter()
    for para in all_paras:
        for w, f in pseg.cut(para):
            word_freq[w] += 1
            char_freq.update(re.findall(r"[\u4e00-\u9fff]", w))
    ann.word_freq = word_freq
    ann.char_freq = char_freq

    out = args.out or (args.book.parent / f"{args.book.stem}.study.epub")
    if is_epub:
        title = args.title or book.title or args.book.stem
        n = annotate_epub(book, ann, out, book_title=title, book_author=args.author)
    else:
        title = args.title or args.book.stem
        n = build_epub(chapters, ann, out, book_title=title, book_author=args.author)
    print(f"wrote {out} ({n} footnote entries)")

    # --- terminal preview ---
    start = 0
    for i, para in enumerate(all_paras):
        if any(ann.decide_word(w, f) == "flag" for w, f in pseg.cut(para)):
            start = i
            break
    print(f"\n=== preview (from paragraph {start}) ===")
    for para in all_paras[start:start + 8]:
        parts = []
        for w, f in pseg.cut(para):
            kind = ann.decide_word(w, f)
            if kind == "flag":
                parts.append(f"⟦{w}⟧")
            elif kind == "name":
                parts.append(f"({w})")
            else:
                buf = []
                for ch in w:
                    if re.search(r"[\u4e00-\u9fff]", ch) and ch not in deck_chars:
                        buf.append(f"⟪{ch}⟫")
                    else:
                        buf.append(ch)
                parts.append("".join(buf))
        print(" ".join(parts))
        print()


if __name__ == "__main__":
    main()
