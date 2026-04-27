import re
import os
import sys

def batch_replace(target_file, mapping_file, dry_run=False):
    # 1. Load find/replace rules from separate file
    # Format: find_regex|replace_string
    rules = []
    try:
        with open(mapping_file, 'r') as f:
            for line in f:
                if '|' in line:
                    pattern, replacement = line.strip().split('|', 1)
                    rules.append((re.compile(pattern), replacement))
    except FileNotFoundError:
        print(f"Error: Mapping file '{mapping_file}' not found.")
        return

    temp_path = target_file + ".tmp"
    
    try:
        with open(target_file, 'r') as fin:
            # Only create temp file if we are NOT in dry_run mode
            fout = open(temp_path, 'w') if not dry_run else None
            
            for line in fin:
                new_line = line
                # Apply all regex rules to the current line
                for pattern, replacement in rules:
                    new_line = pattern.sub(replacement, new_line)
                
                if dry_run:
                    # Output modified lines to screen only
                    if new_line != line:
                        print(new_line.rstrip())
                else:
                    fout.write(new_line)
            
            if fout:
                fout.close()
                # Move tmp file to original
                os.replace(temp_path, target_file)
                print(f"Processed: {target_file}")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Cleanup temp file if it exists after a crash
        if not dry_run and os.path.exists(temp_path):
            os.remove(temp_path)

if __name__ == "__main__":
    # Usage: python batch_replace.py <file_to_mod> <rules_file> [--dry-run]
    target = sys.argv[1]
    mapping = sys.argv[2]
    is_dry = "--dry-run" in sys.argv
    
    batch_replace(target, mapping, dry_run=is_dry)
