import glob
import os
import argparse

def csearch():
    parser = argparse.ArgumentParser()
    parser.add_argument("-C", "--context", type=int, default=3)
    parser.add_argument("-s", "--separator", default="---")
    parser.add_argument("-hide", "--hide-filenames", action="store_true")
    parser.add_argument("pattern")
    parser.add_argument("path")    
    args = parser.parse_args()

    # recursive=True allows **/ syntax if needed
    files = glob.glob(args.path, recursive=True)
    
    for filepath in files:
        if not os.path.isfile(filepath): continue
            
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except Exception: continue

        # Find all matching lines
        match_indices = [i for i, line in enumerate(lines) if args.pattern in line]
        if not match_indices: continue

        # Print File Header if filenames are NOT hidden
        if not args.hide_filenames:
            print(f"\n[ FILE: {filepath} ]\n" + "="*30)

        last_printed_idx = -1
        
        for idx in match_indices:
            start = max(0, idx - args.context)
            end = min(len(lines), idx + args.context + 1)

            # Print separator if this block is separate from the previous one
            if last_printed_idx != -1 and start >= last_printed_idx:
                print(f"\n{args.separator}\n")

            for i in range(start, end):
                # Avoid re-printing lines if context blocks overlap
                if i >= last_printed_idx:
                    # marker = "> " if i == idx else "  "
                    marker = "  "
                    
                    print(f"{marker}{lines[i].rstrip()}")
            
            last_printed_idx = end
        print("\n")

if __name__ == "__main__":
    csearch()
