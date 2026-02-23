import json
from collections import Counter
import re
import sys

# Read the text file
with open(sys.argv[1], 'r', encoding='utf-8') as file:
    text = file.read()

# Filter Chinese characters (Unicode range for CJK characters)
chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)

# Count frequency and sort from most to least
char_freq = Counter(chinese_chars)
sorted_chars = sorted(char_freq.items(), key=lambda x: x[1], reverse=True)

# Create a single string of characters
char_string = ''.join([char for char, _ in sorted_chars])

# Create JSON structure: starting and ending with comma
json_output = f'"{char_string}"'

# Write to JSON file
with open('output.json', 'w', encoding='utf-8') as file:
    file.write(json_output)

print(f"Processed {len(chinese_chars)} Chinese characters")
print(f"Found {len(sorted_chars)} unique Chinese characters")
print(f"Output written to output.json")