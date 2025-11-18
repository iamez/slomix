"""
Extract all mismatched fields from the interactive HTML report
"""
import re
from collections import Counter

# Read the HTML
with open('interactive_field_mapping.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern to find mismatched fields
# Format: <td class="field-name">FIELD</td> ... <td class="value mismatch">VALUE</td>
pattern = r'<td class="field-name">([^<]+)</td>\s*<td class="field-name">([^<]+)</td>\s*<td class="value mismatch">\s*([^<\s]+)'

matches = re.findall(pattern, content)

# Count mismatches by field
field_counts = Counter()
field_examples = {}

for file_field, db_field, file_value in matches:
    field_counts[file_field] += 1
    if file_field not in field_examples:
        field_examples[file_field] = file_value

print("="*80)
print("MISMATCHED FIELDS FROM ANALYSIS")
print("="*80)
print(f"\nTotal mismatch instances found: {len(matches)}")
print(f"Unique fields with mismatches: {len(field_counts)}")

print("\n" + "="*80)
print("FIELDS BY MISMATCH COUNT:")
print("="*80)

for field, count in field_counts.most_common():
    print(f"{field:30} | {count:4} mismatches | Example value: {field_examples[field]}")

# Now extract DB values too
pattern_with_db = r'<td class="field-name">([^<]+)</td>\s*<td class="field-name">([^<]+)</td>\s*<td class="value mismatch">\s*([^<\s]+)\s*</td>\s*<td class="value mismatch">\s*([^<\s]+)'

matches_with_db = re.findall(pattern_with_db, content)

print("\n" + "="*80)
print("SAMPLE MISMATCHES (File vs DB):")
print("="*80)

# Show first 20 unique field mismatches
seen = set()
count = 0
for file_field, db_field, file_val, db_val in matches_with_db:
    if file_field not in seen and count < 20:
        print(f"\n{file_field}:")
        print(f"  File: {file_val}")
        print(f"  DB:   {db_val}")
        seen.add(file_field)
        count += 1

# Find patterns
print("\n" + "="*80)
print("PATTERNS DETECTED:")
print("="*80)

# Check for fields where DB is always 0
zero_fields = set()
non_zero_fields = set()

for file_field, db_field, file_val, db_val in matches_with_db:
    try:
        db_numeric = float(db_val)
        if db_numeric == 0:
            zero_fields.add(file_field)
        else:
            non_zero_fields.add(file_field)
    except:
        pass

always_zero = zero_fields - non_zero_fields

if always_zero:
    print(f"\n❌ Fields where DB is ALWAYS 0 (but file has values):")
    for field in sorted(always_zero):
        print(f"   • {field}")

# Check for calculated fields (dpm, kd_ratio, etc)
calculated_fields = []
for file_field, db_field, file_val, db_val in matches_with_db:
    if file_field in ['dpm', 'kd_ratio', 'efficiency', 'accuracy']:
        calculated_fields.append((file_field, file_val, db_val))

if calculated_fields:
    print(f"\n⚠️  Calculated fields (DB recalculates, expected mismatch):")
    seen_calc = set()
    for field, file_val, db_val in calculated_fields:
        if field not in seen_calc:
            print(f"   • {field}: File={file_val}, DB={db_val} (recalculated)")
            seen_calc.add(field)
