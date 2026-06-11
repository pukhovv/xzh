import json, os, re, sys

TARGET_WORDS = 20000
TARGET_CHARS = 4000
ENCODING = "gb2312"

NUM_DIGITS = set("零一二三四五六七八九十百千万亿两")
ARABIC = set("0123456789０１２３４５６７８９")
MEASURE = "个只条张把支块根颗粒辆次遍回趟件项等部台位名号站点种样份片双对"
TIME_U = "点时钟分秒"
CAL_U = "年月日号"
MONEY_U = "元角分块毛"
PHYS_U = "米公里千克吨升度倍"
AGE = "岁"

LEX = {
    "十分", "一点", "万一", "千万", "一旦", "一半", "一时", "万岁", "一致", "统一",
    "唯一", "单一", "同一", "一瞬", "一阵", "一下子", "一辈子", "一生", "一律",
    "一同", "一再", "一口气", "一流", "一丝", "一手", "一齐", "多重", "八成",
    "十足", "三方", "百分比", "万分", "零碎", "零星", "零花钱", "两难", "两样",
    "两面", "两端", "两边", "两极", "俩", "百万", "亿万", "半边", "双击", "一样",
    "双方", "双重", "两位数", "两手", "两回事", "加倍", "减半", "三分之一",
    "一无所知", "二话不说", "三思", "四面八方", "四起", "四处", "五颜六色",
}

TRANS = set("斯尔尼卡莉艾莱蒂瑞娜妮玛莎琳弗乔迪奥洛"
    "曼伯佩詹森埃塔卢兹逊翰娅姬茜黛柯沃伊姆"
    "萨芭啡芬冈狄杜罕穆韦丘芙朱梅")

WCD_THRESH = 30

def _arabic(w):
    return any(c in ARABIC for c in w)

def _pure_num(w):
    return all(c in NUM_DIGITS for c in w)

def _ordinal(w):
    if not (w.startswith("第") and len(w) > 1):
        return False
    rest = w[1:]
    if all(c in NUM_DIGITS for c in rest):
        return True
    return len(rest) >= 1 and all(c in NUM_DIGITS for c in rest[:-1]) and rest[-1] in MEASURE

def _calendar(w):
    if w.startswith("星期") and len(w) == 3:
        return True
    if w.startswith("周") and len(w) == 2 and w[1] in "一二三四五六日天":
        return True
    if len(w) >= 2 and w[-1] in "月日号年":
        prefix = w[:-1]
        return prefix and all(c in "零一二三四五六七八九十百千万亿两0123456789" for c in prefix)
    return False

def _time(w):
    if w.endswith("点半") and len(w) > 2:
        return all(c in "零一二三四五六七八九十百千万亿两0123456789" for c in w[:-2])
    if len(w) >= 2 and w[-1] in "点分秒":
        return all(c in "零一二三四五六七八九十百千万亿两0123456789" for c in w[:-1])
    if w.endswith("时") and len(w) > 1:
        return all(c in "零一二三四五六七八九十百千万亿两0123456789" for c in w[:-1])
    if w in ("小时", "分钟", "秒钟"):
        return False
    return bool(re.match(r'^[零一二三四五六七八九十百千万亿两\d]+小时$', w))

def _countable(w):
    if _arabic(w) and len(w) > 1:
        return True
    if len(w) < 2:
        return False
    suffixes = set(MEASURE + AGE + PHYS_U + MONEY_U + "点分秒时日号年月")
    if w[-1] in suffixes:
        return all(c in NUM_DIGITS for c in w[:-1])
    return False

def is_noise(w):
    if w in LEX:
        return False
    return _pure_num(w) or _arabic(w) or _ordinal(w) or _calendar(w) or _time(w) or _countable(w)

def is_garbage(word, wcd):
    return '\ufffd' in word or (len(word) > 1 and wcd < WCD_THRESH)

def is_trans(word, pmap):
    if len(word) < 2:
        return False
    if word in pmap:
        return False
    return sum(1 for c in word if c in TRANS) / len(word) >= 0.5

def parse_wf(path):
    r = []
    with open(path, "r", encoding=ENCODING, errors="replace") as f:
        for i, line in enumerate(f):
            if i < 3:
                continue
            parts = line.strip().split("\t")
            if not parts or not parts[0]:
                continue
            word = parts[0].strip()
            if not word:
                continue
            try: count = int(parts[1]) if len(parts) > 1 else 0
            except ValueError: count = 0
            try: wcd = int(parts[4]) if len(parts) > 4 else 9999
            except ValueError: wcd = 9999
            r.append((word, count, wcd))
    return r

def parse_chr(path):
    chars = []
    with open(path, "r", encoding=ENCODING, errors="replace") as f:
        for i, line in enumerate(f):
            if i < 3:
                continue
            parts = line.strip().split("\t")
            if parts and parts[0]:
                c = parts[0].strip()
                if c and len(c) == 1 and '\ufffd' not in c:
                    chars.append(c)
    return chars

build = sys.argv[1]
dset = os.path.join(build, "dset")
wf = os.path.join(dset, "SUBTLEX-CH-WF")
chrf = os.path.join(dset, "SUBTLEX-CH-CHR")

with open(os.path.join(build, "cedict.json")) as f:
    pmap = json.load(f)["pinyin"]

raw = parse_wf(wf)
clean = []
noise_n = 0
for w, cnt, wcd in raw:
    if is_noise(w):
        noise_n += 1
    else:
        clean.append((w, cnt, wcd))
print(f"raw={len(raw)} noise={noise_n} non_noise={len(clean)}")

filtered = []
garbage_n = 0
trans_n = 0
for w, cnt, wcd in clean:
    if is_garbage(w, wcd):
        garbage_n += 1
    elif is_trans(w, pmap):
        trans_n += 1
    else:
        filtered.append((w, cnt))
print(f"garbage={garbage_n} trans={trans_n} clean={len(filtered)}")

words = filtered[:TARGET_WORDS]
word_chars = set()
for w, _ in words:
    word_chars.update(w)
print(f"words={len(words)} word_chars={len(word_chars)}")

all_chars = parse_chr(chrf)
selected = []
for c in all_chars:
    if c in word_chars:
        selected.append(c)
        if len(selected) >= TARGET_CHARS:
            break
print(f"selected_chars={len(selected)}")

os.makedirs(build, exist_ok=True)
wlist = [w for w, _ in words]
with open(os.path.join(build, "words.json"), "w", encoding="utf-8") as f:
    json.dump(wlist, f, ensure_ascii=False)
clist = "".join(selected)
raw_freqs = "".join(all_chars)
with open(os.path.join(build, "chars.json"), "w", encoding="utf-8") as f:
    json.dump({"chars": clist, "freqs": raw_freqs}, f, ensure_ascii=False)
print(f"wrote words={len(wlist)} chars={len(clist)} freqs={len(raw_freqs)}")
