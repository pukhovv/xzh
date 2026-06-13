import json, re, sys
from pathlib import Path

def parse_entries(data: str) -> dict:
    entries: dict = {}
    pat = re.compile(r'([^:]+):([^\(]*)\(([^)]*)\)')
    for entry in re.split(r'[;\n]', data):
        entry = entry.strip()
        if not entry:
            continue
        m = pat.match(entry)
        if m:
            key, rel, comps = m.groups()
            entries[key] = {'key': key, 'rel': rel.strip(),
                            'comps': [c.strip() for c in comps.split(',')]}
    return entries

def filter_reachable(data: dict, roots: list[str]) -> dict:
    ref = set()
    queue = list(roots)
    while queue:
        key = queue.pop()
        if key in ref or key not in data:
            continue
        ref.add(key)
        for comp in data[key]['comps']:
            if comp not in ref:
                queue.append(comp)
    return {k: data[k] for k in ref}

def sort_by_freq(data: dict, freq_list: list[str]) -> dict:
    rank = {c: i for i, c in enumerate(freq_list)}
    def key_fn(k):
        return rank.get(k, float('inf'))
    sorted_keys = sorted(data.keys(), key=key_fn)

    out = {}
    for key in sorted_keys:
        e = data[key]
        cc = [c for c in e['comps'] if not c.isdigit()]
        nc = [c for c in e['comps'] if c.isdigit()]
        cc.sort(key=key_fn)
        out[key] = {'key': key, 'rel': e['rel'], 'comps': cc + nc}
    return out

def dump(data: dict, path: str) -> None:
    out = [[e['key'], e['rel'], e['comps']] for e in data.values()]
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))

build = Path(sys.argv[1])
dset = build / "dset"
res = build / "res"

decomp_path = dset / "cjk-decomp-0.4.0.txt"
freqs_path = build / "freqs.json"

freqlist = list(json.loads(freqs_path.read_text(encoding='utf-8')))

with decomp_path.open('r', encoding='utf-8') as f:
    raw = f.read()

entries = parse_entries(raw)
print(f"full: {len(entries)}")

filtered = filter_reachable(entries, freqlist)
filtered = sort_by_freq(filtered, freqlist)
print(f"reachable: {len(filtered)}")

res.mkdir(parents=True, exist_ok=True)
out = res / "_xiezh_graph.json"
dump(filtered, str(out))
print(f"wrote graph: {out.stat().st_size / 1024:.0f}K")
