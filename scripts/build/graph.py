import json, os, re, sys

def parse_entries(data):
    entries = {}
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

def filter_reachable(data, roots):
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

def sort_by_freq(data, freq_list):
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

def dump(data, path):
    with open(path, 'w', encoding='utf-8') as f:
        entries = []
        f.write('"')
        for key, e in data.items():
            comps = ','.join(e['comps'])
            entries.append(f"{key}:{e['rel']}({comps})")
        f.write(';'.join(entries))
        f.write('"')

build = sys.argv[1]
dset = os.path.join(build, "dset")
res = os.path.join(build, "res")

decomp_path = os.path.join(dset, "cjk-decomp-0.4.0.txt")
freqs_path = os.path.join(res, "_xiezh_freqs.json")

freqlist = list(json.load(open(freqs_path, 'r', encoding='utf-8')))

with open(decomp_path, 'r', encoding='utf-8') as f:
    raw = f.read()

entries = parse_entries(raw)
print(f"full: {len(entries)}")

filtered = filter_reachable(entries, freqlist)
filtered = sort_by_freq(filtered, freqlist)
print(f"reachable: {len(filtered)}")

os.makedirs(res, exist_ok=True)
out = os.path.join(res, "_xiezh_graph.json")
dump(filtered, out)
print(f"wrote graph: {os.path.getsize(out)/1024:.0f}K")
