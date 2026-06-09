import json, os, sys

ENCODING = "gb2312"

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
res = os.path.join(build, "res")
chr_path = os.path.join(dset, "SUBTLEX-CH-CHR")
clist = "".join(parse_chr(chr_path))
os.makedirs(res, exist_ok=True)
with open(os.path.join(res, "_xiezh_freqs.json"), "w", encoding="utf-8") as f:
    json.dump(clist, f, ensure_ascii=False)
print(f"freqs: {len(clist)} chars")
