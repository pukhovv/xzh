import json, os, re, sys

def pinyin_to_number(py):
    tone_map = {
        'ā': ('a', 1), 'á': ('a', 2), 'ǎ': ('a', 3), 'à': ('a', 4),
        'ē': ('e', 1), 'é': ('e', 2), 'ě': ('e', 3), 'è': ('e', 4),
        'ī': ('i', 1), 'í': ('i', 2), 'ǐ': ('i', 3), 'ì': ('i', 4),
        'ō': ('o', 1), 'ó': ('o', 2), 'ǒ': ('o', 3), 'ò': ('o', 4),
        'ū': ('u', 1), 'ú': ('u', 2), 'ǔ': ('u', 3), 'ù': ('u', 4),
        'ǖ': ('v', 1), 'ǘ': ('v', 2), 'ǚ': ('v', 3), 'ǜ': ('v', 4),
        'ń': ('n', 2), 'ň': ('n', 3), 'ǹ': ('n', 4),
        'ḿ': ('m', 2),
    }
    result = []
    tone = 5
    for c in py:
        if c in tone_map:
            base, t = tone_map[c]
            result.append(base)
            tone = t
        else:
            result.append(c)
    return ''.join(result) + str(tone)

def parse_cedict(path):
    pmap = {}
    pat = re.compile(r'^(\S+)\s+(\S+)\s+\[([^\]]+)\]\s+')
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('#'):
                continue
            m = pat.match(line)
            if not m:
                continue
            trad, simp, py = m.groups()
            pn = pinyin_to_number(py)
            if simp not in pmap:
                pmap[simp] = []
            if pn not in pmap[simp]:
                pmap[simp].append(pn)
    return pmap

def build_compounds(wlist, pmap):
    cw = {}
    for i, w in enumerate(wlist):
        for c in set(w):
            if c not in cw:
                cw[c] = []
            cw[c].append(w)

    result = {}
    for c, words in cw.items():
        ws = sorted(words, key=lambda w: wlist.index(w))
        total_w = sum(1.0 / (wlist.index(w) + 1) for w in ws)

        sr = 0.0
        if c in ws:
            sc_pos = wlist.index(c)
            total_weight = sum(1.0 / (wlist.index(w) + 1) for w in ws)
            sr = (1.0 / (sc_pos + 1)) / total_weight if total_weight > 0 else 0

        sel = []
        cum = 0.0
        for w in ws:
            contrib = (1.0 / (wlist.index(w) + 1)) / total_w
            if len(sel) >= 2 and contrib < 0.02:
                break
            sel.append(w)
            cum += contrib
            if len(sel) >= 4 or cum >= 0.85:
                break

        result[c] = {"compounds": sel, "standalone_ratio": round(sr, 4)}

    return result

build = sys.argv[1]
dset = os.path.join(build, "dset")

cedict_path = os.path.join(dset, "cedict_ts.u8")
wlist_path = os.path.join(build, "words.json")

pmap = parse_cedict(cedict_path)
print(f"cedict entries: {len(pmap)}")

with open(wlist_path, 'r') as f:
    wlist = json.load(f)

compounds = build_compounds(wlist, pmap)
print(f"compounds: {len(compounds)} chars")

out = {"pinyin": pmap, "compounds": compounds}
os.makedirs(build, exist_ok=True)
with open(os.path.join(build, "cedict.json"), 'w') as f:
    json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
sz = os.path.getsize(os.path.join(build, "cedict.json"))
print(f"wrote cedict: {sz/1024:.0f}K")
