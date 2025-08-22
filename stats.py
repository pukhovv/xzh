import json

def extract_anki_hanzi(filename):
    hanzi = set()
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                hanzi.update(char for char in line.split('[')[0] if char.strip())
    return hanzi

def load_freq_list(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def filter_freq_list(freq_str, anki_hanzi):
    return ''.join(char for char in freq_str if char not in anki_hanzi)

anki_hanzi = extract_anki_hanzi('../xiezh.txt')
freq_list = load_freq_list('freqs.json')
filtered = filter_freq_list(freq_list, anki_hanzi)

print(f"Anki hanzi: {len(anki_hanzi)}")
print(f"Original: {len(freq_list)}")
print(f"Filtered: {len(filtered)}")

to_print = 500
print(f"Next {to_print}")
print(filtered[:to_print])

#with open('filtered.json', 'w', encoding='utf-8') as f:
#    json.dump(filtered, f, ensure_ascii=False)

