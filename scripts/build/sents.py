import json, os, re, sys, time, gzip as gz, random
from collections import defaultdict

import jieba
jieba.setLogLevel(20)

MAX_PER = 4
MIN_CJK, MAX_CJK = 6, 20
A, B = 50, 0.3
LOG_INTERVAL = 500000
TOTAL = 16316804

LATIN = re.compile(r'[a-zA-Z0-9@#$%^&*(){}\[\]<>]')
DIA_START = re.compile(r'^[\-\—\–\'\"]')
DIA_END = re.compile(r'[：:]$')
TRANS = set("斯尔尼卡莉艾莱蒂瑞娜妮玛莎琳弗乔迪奥洛曼伯佩詹森埃塔卢兹逊翰娅姬茜黛柯沃伊姆萨芭啡芬冈狄杜罕穆韦丘芙朱梅")
MDOT = re.compile(r'[·・]')
TJUNK = re.compile(r'[，,；;]+$')

ELLIPSIS = re.compile(r'\.\.')  # catches .. and ...
FW_ELLIPSIS = re.compile(r'[．\uff0e]{2,}|\u2026')  # fullwidth dots or …
PAREN_NOTE = re.compile(r'（[^）]{2,}）')  # parenthetical subtitle notes
DASH_START = re.compile(r'^[―—\-－\u2010-\u2015]')
BAD_SYMBOLS = re.compile(r'[♪★☆∮▲▼○●◆◇◎\u25cb――]')
JAPANESE_KANA = re.compile(r'[\u3040-\u309f\u30a0-\u30ff]')
PUA = re.compile(r'[\ue000-\uf8ff]')
REPLACEMENT = '\ufffd'
DIGITS = re.compile(r'[\d０-９]')
SUBTITLE_META = re.compile(r'人人影视|本字幕')

def ccjk(t):
    return re.sub(r'[^\u4e00-\u9fff]', '', t)

def has_trans(t, n=3):
    cur = 0
    for c in t:
        if c in TRANS:
            cur += 1
            if cur >= n: return True
        else:
            cur = 0
    return False

def trans_ratio(t):
    if not t: return 0.0
    return sum(1 for c in t if c in TRANS) / len(t)

def is_good(text, allowed):
    if DIA_START.search(text) or DIA_END.search(text): return False
    if LATIN.search(text): return False
    if MDOT.search(text): return False
    if ELLIPSIS.search(text): return False
    if FW_ELLIPSIS.search(text): return False
    if PAREN_NOTE.search(text): return False
    if DASH_START.search(text): return False
    if BAD_SYMBOLS.search(text): return False
    if JAPANESE_KANA.search(text): return False
    if PUA.search(text): return False
    if REPLACEMENT in text: return False
    if DIGITS.search(text): return False
    if SUBTITLE_META.search(text): return False
    if "'" in text: return False
    c = text.replace(' ', '').replace('\u3000', '')
    c = TJUNK.sub('', c)
    cj = ccjk(c)
    if len(cj) < MIN_CJK or len(cj) > MAX_CJK: return False
    if has_trans(cj): return False
    if trans_ratio(cj) > 0.5: return False
    return all(ch in allowed for ch in cj)

def base_syl(py):
    if len(py) >= 2 and py[-1] == '5' and py[-2].isdigit():
        return py[:-1]
    return py

def classify(sent, tc, cedict_py, seg=None):
    if seg is None:
        seg = list(jieba.cut(sent))
    readings = set()
    for sw in seg:
        if tc not in sw: continue
        pys = cedict_py.get(sw, [])
        if not pys: continue
        pos = [i for i, c in enumerate(sw) if c == tc]
        for py in pys:
            syls = py.split()
            for p in pos:
                if p < len(syls):
                    readings.add(base_syl(syls[p]))
    return list(readings)[0] if len(readings) == 1 else None

def diversify(w_idx, pool, cedict_py):
    duoyin = {w for w, pys in cedict_py.items() if len(w) == 1 and len(pys) > 1}
    print(f"  duoyin: {len(duoyin)}")
    n = 0
    for c, sids in list(w_idx.items()):
        if c not in duoyin or len(sids) < 2: continue
        rs = defaultdict(list)
        for sid in sids:
            rs[classify(pool[sid], c, cedict_py)].append(sid)
        if len(rs) <= 1: continue
        new = []
        lists = [rs[r] for r in sorted(k for k in rs if k is not None) if rs[r]]
        ml = max(len(l) for l in lists)
        for i in range(ml):
            for l in lists:
                if i < len(l): new.append(l[i])
        if new != sids:
            w_idx[c] = new[:MAX_PER + 2]
            n += 1
    print(f"  re-ranked: {n}")

def dedup(sents):
    if len(sents) <= 1: return sents
    def bg(s):
        cj = ccjk(s)
        return set(cj[i:i+2] for i in range(len(cj)-1))
    kept = []
    for s in sents:
        cs = ccjk(s)
        dup = False
        for k in kept:
            ck = ccjk(k)
            if cs in ck or ck in cs:
                if len(cs) <= len(ck): dup = True; break
            bgs, bgk = bg(s), bg(k)
            if bgs and bgk and len(bgs & bgk) / max(len(bgs), len(bgk)) > 0.8:
                dup = True; break
        if not dup: kept.append(s)
    return kept

build = sys.argv[1]
dset = os.path.join(build, "dset")
res = os.path.join(build, "res")
t0 = time.time()

with open(os.path.join(build, "words.json")) as f:
    wlist = json.load(f)
with open(os.path.join(build, "chars.json")) as f:
    chardata = json.load(f)
clist = chardata["chars"]
freqlist = chardata["freqs"]
clist_set = set(clist)
with open(os.path.join(build, "cedict.json")) as f:
    cedict_data = json.load(f)
cedict_py = cedict_data["pinyin"]
char_cmp = cedict_data["compounds"]

ALLOWED = clist_set
print(f"words={len(wlist)} chars={len(clist)} cedict={len(cedict_py)}")

wp = {w: i for i, w in enumerate(wlist)}
def mx(p0):
    return max(p0, min(A + int(B * (p0 + 1)), len(wlist) - 1))
wset = set(wlist)

bias = {c for c, info in char_cmp.items() if info.get("standalone_ratio", 0) >= 0.15}
print(f"standalone bias: {len(bias)}")

pool = []
wm = defaultdict(list)
pending = set(range(len(wlist)))
pmax = {i: mx(i) for i in pending}

# Collect all good sentences during phase 1 for phase 2 reuse
sub_extras = []

opus = os.path.join(dset, "zh_cn.txt.gz")
print("\nphase 1...")
lines = 0

with gz.open(opus, 'rt', encoding='utf-8', errors='replace') as f:
    for line in f:
        lines += 1
        if lines % LOG_INTERVAL == 0:
            t = time.time() - t0
            r = lines / t
            eta = (TOTAL - lines) / r if r > 0 else 0
            print(f"  {lines/1e6:.1f}M pool={len(pool)} pending={len(pending)} {t/60:.0f}m eta={eta/60:.0f}m")
        if not pending:
            print(f"  done at {lines}")
            break
        text = line.rstrip('\n')
        if not is_good(text, ALLOWED): continue
        text = text.replace(' ', '').replace('\u3000', '')
        text = TJUNK.sub('', text)
        text = text.replace(',', '，').replace('\uff0e', '。')
        seg = list(jieba.cut(text))
        matched = {sw for sw in seg if sw in wset}
        if not matched:
            sub_extras.append(text)
            continue
        sid = len(pool)
        pool.append(text)
        na = 0
        mp = {w: wp[w] for w in matched}
        for w in matched:
            wi = wp[w]
            if wi not in pending: continue
            ok = all(mp[mw] <= pmax[wi] for mw in mp)
            if not ok: continue
            wm[w].append(sid)
            if len(wm[w]) >= MAX_PER:
                pending.discard(wi); del pmax[wi]
            na += 1
        if na == 0:
            pool.pop()
            sub_extras.append(text)

if pending:
    print(f"\n  phase 1 done: {len(pending)} uncovered ({len(sub_extras)} extras)")
    print("  phase 2: substring...")
    rem = {wlist[i] for i in pending}
    for text in sub_extras:
        if not rem: break
        found = False
        for w in list(rem):
            if w in text:
                if not found:
                    sid = len(pool); pool.append(text); found = True
                wm[w].append(sid)
                if len(wm[w]) >= MAX_PER:
                    rem.discard(w); pending.discard(wp[w])
    print(f"    done: {len(rem)} still uncovered")

sneed = {w for w in bias if w in wm and len(wm[w]) >= 2}
for w in list(sneed):
    if any(w in list(jieba.cut(pool[sid])) for sid in wm[w]):
        sneed.discard(w)
if sneed:
    print(f"\n  phase 3: standalone bias {len(sneed)}")
    for w in list(sneed):
        for sid, s in enumerate(pool):
            if sid not in wm[w] and w in list(jieba.cut(s)):
                wm[w].append(sid); sneed.discard(w); break

print("\nindices...")
seen = {}
uniq = []
otn = {}
for i, s in enumerate(pool):
    if s not in seen:
        seen[s] = len(uniq); uniq.append(s)
    otn[i] = seen[s]
print(f"  sents: {len(pool)} -> {len(uniq)} unique")

w_idx = {}
drm = 0
for w, sids in wm.items():
    dd = []
    ss = set()
    for sid in sids:
        nid = otn.get(sid)
        if nid is not None and nid not in ss:
            dd.append(nid); ss.add(nid)
    ds = dedup([uniq[i] for i in dd])
    drm += len(dd) - len(ds)
    sti = {s: i for i, s in enumerate(uniq)}
    w_idx[w] = [sti[s] for s in ds][:MAX_PER]
print(f"  dedup removed: {drm}")

diversify(w_idx, uniq, cedict_py)

random.seed(42)
for v in w_idx.values():
    random.shuffle(v)

print("  pre-segmenting for c_idx...")
uniq_segs = [list(jieba.cut(s)) for s in uniq]

c_idx = defaultdict(set)
for w, sids in w_idx.items():
    for si, c in enumerate(w):
        for sid in sids:
            syl = classify(uniq[sid], c, cedict_py, uniq_segs[sid])
            if syl:
                c_idx[c + ":" + syl].add(sid)
            c_idx[c].add(sid)

for i, s in enumerate(uniq):
    for c in set(s):
        if '\u4e00' <= c <= '\u9fff' and c in clist_set:
            if len(c_idx.get(c, [])) < MAX_PER + 2:
                c_idx[c].add(i)
            syl = classify(s, c, cedict_py, uniq_segs[i])
            if syl:
                if len(c_idx.get(c + ":" + syl, [])) < MAX_PER + 2:
                    c_idx[c + ":" + syl].add(i)

c_idx = {k: sorted(list(v))[:MAX_PER + 2] for k, v in c_idx.items()}
for v in c_idx.values():
    random.shuffle(v)

cmp_out = {c: char_cmp[c]["compounds"] for c in clist_set if c in char_cmp}

wf = {w: i for i, w in enumerate(wlist)}
cf = {c: i for i, c in enumerate(freqlist)}
w_out = {}
for w, sids in w_idx.items():
    w_out[w] = {"r": wf.get(w, -1), "s": sids}
c_out = {}
for k, sids in c_idx.items():
    if ':' in k:
        c_out[k] = {"s": sids}
    else:
        c_out[k] = {"r": cf.get(k, -1), "s": sids}

out = {"s": uniq, "w": w_out, "c": c_out, "cmp": cmp_out}
os.makedirs(res, exist_ok=True)
op = os.path.join(res, "_xiezh_db.json")
with open(op, 'w') as f:
    json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
sz = os.path.getsize(op)

elapsed = time.time() - t0
print(f"wrote sents: {sz/1024:.0f}K in {elapsed/60:.1f}m")
print(f"words: {len(w_idx)}/{len(wlist)} chars: {len(c_idx)}/{len(clist)} uniq sents: {len(uniq)}")
