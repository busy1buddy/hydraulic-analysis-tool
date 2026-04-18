import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.au_pipes import get_pipe_properties, list_materials

print("Materials in database:")
print(list_materials())

test_cases = [
    ("PE100 PN10 (SDR 17)", 1000),
    ("PE100 PN16 (SDR 11)", 800),
    ("PE100 PN20 (SDR 9)", 63),
    ("PE", 110), # Legacy check
]

for mat, dn in test_cases:
    props = get_pipe_properties(mat, dn)
    if props:
        print(f"\nFound {mat} DN{dn}:")
        for k, v in props.items():
            print(f"  {k}: {v}")
    else:
        print(f"\nFailed to find {mat} DN{dn}")
