import json
import sys
import matplotlib.pyplot as plt

def extract_anki_hanzi(filename):
    hanzi = set()
    hanziu = set()
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                chars = line.split('[')[0].strip()
                hanzi.update(char for char in chars)
                if len(chars) == 1:
                    hanziu.update(chars[0])
    return hanzi, hanziu

def load_freq_list(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def create_coverage_plot(freq_list, anki_hanzi, limit=3000):
    cumulative_found = []
    count = 0
    for char in freq_list[:limit]:
        if char in anki_hanzi:
            count += 1
        cumulative_found.append(count)
    
    total = len(freq_list[:limit])
    
    plt.figure(figsize=(12, 8))
    plt.plot(range(total), cumulative_found, 'b-', linewidth=2)
    plt.plot([0, total], [0, total], 'r--', alpha=0.5, label='Perfect coverage')
    
    # Find where coverage drops below thresholds
    milestones = [1.0, 0.98, 0.95, 0.9]
    colors = ['green', 'red', 'purple', 'orange']
    
    for ratio, color in zip(milestones, colors):
        for i in range(total):
            if cumulative_found[i] / (i + 1) < ratio:
                plt.axvline(x=i, color=color, linewidth=2, label=f'Below {ratio*100:.0f}% at {i}')
                break
    
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.show()
    
    return cumulative_found

anki_hanzi, unique = extract_anki_hanzi(sys.argv[1])
freq_list = load_freq_list('freqs.json')
filtered = ''.join(char for char in freq_list if char not in anki_hanzi)
known = ''.join(char for char in freq_list if char in anki_hanzi)
missing = ''.join(char for char in anki_hanzi if char in freq_list and char not in unique)

cumulative_found = create_coverage_plot(freq_list, anki_hanzi, 3000)

total = len(freq_list)
filtered_count = len(filtered)
found = total - filtered_count

print(f"Anki hanzi: {len(anki_hanzi)}")
print(f"Original: {total}")
print(f"Filtered: {filtered_count}")
print(f"Found: {found}")
print(f"Coverage: {found/total*100:.1f}%")

print(f"Missing: {missing}")
to_print = 500
print(f"Next {to_print}: {filtered[:to_print]}")
print(f"Vocab: {known}")
