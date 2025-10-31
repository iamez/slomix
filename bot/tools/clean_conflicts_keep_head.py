import re
from pathlib import Path

p = Path(r"g:\VisualStudio\Python\stats\bot\ultimate_bot.py")
text = p.read_text(encoding='utf-8')

# Pattern for conflict: <<<<<<< HEAD ... ======= ... >>>>>>> branch
# We'll keep the HEAD part and remove the markers and the other branch.
pattern = re.compile(r"^<<<<<<< HEAD\n(.*?)\n^=======\n(.*?)\n^>>>>>>> .*?$", re.S | re.M)

new_text = text
iterations = 0
while True:
    m = pattern.search(new_text)
    if not m:
        break
    head_part = m.group(1)
    # Replace the whole match with the head part (no markers)
    new_text = new_text[:m.start()] + head_part + new_text[m.end():]
    iterations += 1

# Also remove any leftover markers (if any odd cases)
new_text = new_text.replace('<<<<<<< HEAD\n', '')
new_text = new_text.replace('=======\n', '')
# remove >>>>>>> lines
new_text = re.sub(r"^>>>>>>> .*?$\n", '', new_text, flags=re.M)

out = p.with_suffix('.cleaned.py')
out.write_text(new_text, encoding='utf-8')
print(f"Wrote cleaned file to: {out}\nConflicts processed: {iterations}")
# Overwrite original after writing cleaned copy (keep backup already created)
p.write_text(new_text, encoding='utf-8')
print("Original file overwritten with cleaned content.")
