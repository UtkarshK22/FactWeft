#!/usr/bin/env python3
import re

with open('app/llm/adapter.py', 'r') as f:
    content = f.read()

# Find SYSTEM_PROMPT = """ pattern
match = re.search(r'SYSTEM_PROMPT\s*=\s*""", content)
if match:
    start = match.start()
    # Find the closing """ by counting triple quotes
    after = content[start:]
    positions = []
    i = 0
    while True:
        idx = after.find('"""', i)
        if idx == -1:
            break
        positions.append(idx)
        i = idx + 3
        if len(positions) >= 2:
            break
    
    if len(positions) >= 2:
        end = start + positions[1] + 3
        # Extract inner content (between the opening and closing """)
        inner = content[start + 3:end - 3]
        
        # Escape for single-quoted string: replace backslash first, then quotes
        escaped = inner.replace('\\', '\\\\').replace("'", '\\"')
        
        # Build new single-quoted string
        new_system = 'SYSTEM_PROMPT = "' + escaped + '"'
        
        # Replace
        new_content = content[:start] + new_system + content[end:]
        
        with open('app/llm/adapter.py', 'w') as f:
            f.write(new_content)
        print('File fixed successfully')
        print(f'New SYSTEM_PROMPT starts with: {new_system[:80]}...')
    else:
        print('ERROR: Could not find closing triple quote')
else:
    print('ERROR: SYSTEM_PROMPT pattern not found')