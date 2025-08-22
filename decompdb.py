import re
import json

file = open('_xiezh_decomp.json', 'r', encoding='utf-8')
file_content = file.read()

def parse_entries(data):
    entries = {}
    pattern = re.compile(r'([^:]+):([^\(]*)\(([^)]*)\)')
    
    for entry in data.split(';'):
        entry = entry.strip()
        if not entry:
            continue
            
        match = pattern.match(entry)
        if match:
            key, rel, comps = match.groups()
            entries[key] = {
                'key': key,
                'rel': rel.strip(),
                'comps': [c.strip() for c in comps.split(',')]
            }
        else:
            print("not matched: ", entry)
    
    return entries

def filter_reachable(parsed_data, roots):
    referenced = set()
    queue = list(roots)
    
    while queue:
        key = queue.pop()
        if key in referenced or key not in parsed_data:
            continue
        
        referenced.add(key)
        # print("push " + key)
        
        entry = parsed_data[key]
        
        for comp in entry['comps']:
            if comp not in referenced:
                queue.append(comp)
    
    return {k: parsed_data[k] for k in referenced}

def sort_by_frequency(data, freq_list):
    freq_rank = {char: idx for idx, char in enumerate(freq_list)}
    
    sorted_keys = sorted(data.keys(),
                       key=lambda x: freq_rank.get(x, float('inf')))
    
    sorted_data = {}
    for key in sorted_keys:
        entry = data[key]
        
        char_comps = [c for c in entry['comps'] if not c.isdigit()]
        num_comps = [c for c in entry['comps'] if c.isdigit()]
        
        sorted_char_comps = sorted(char_comps,
                                 key=lambda x: freq_rank.get(x, float('inf')))
        
        sorted_comps = sorted_char_comps + num_comps
        
        sorted_data[key] = {
            'key': key,
            'rel': entry['rel'],
            'comps': sorted_comps
        }
    
    return sorted_data

def dump_fmt(filtered_data, output_file):
    with open(output_file, 'w', encoding='utf-8') as f:
        entries = []
        f.write("\"")
        for key, data in filtered_data.items():
            comps = ','.join(data['comps'])
            entries.append(f"{key}:{data['rel']}({comps})")
        f.write(';'.join(entries))
        f.write("\"")

freqlist = list(json.load(open("freqs.json", 'r', encoding='utf-8')))

entries = parse_entries(file_content)
print("size: ", len(entries))

normalized = filter_reachable(entries, freqlist)
normalized = sort_by_frequency(normalized, freqlist)
print("filtered: ", len(normalized))

dump_fmt(normalized, '_xiezh_decomp_light.json')
