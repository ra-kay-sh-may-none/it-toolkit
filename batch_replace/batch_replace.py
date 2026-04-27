import re
import os
import sys

def batch_replace(target_file, mapping_file, dry_run=False):
    rules = []
    try:
        with open(mapping_file, 'r') as f:
            content = f.read()
            blocks = content.strip().split('[RULE]')
            for block in blocks:
                if '---' in block:
                    pattern, replacement = block.split('---', 1)
                    rules.append((re.compile(pattern.strip(), re.DOTALL), replacement.strip()))
    except FileNotFoundError:
        print(f"Error: Mapping file '{mapping_file}' not found.")
        return

    try:
        with open(target_file, 'r') as f:
            original_content = f.read()

        modified_content = original_content
        for pattern, replacement in rules:
            modified_content = pattern.sub(replacement, modified_content)

        if dry_run:
            print("--- DRY RUN OUTPUT ---")
            print(modified_content)
        else:
            temp_path = target_file + ".tmp"
            with open(temp_path, 'w') as f:
                f.write(modified_content)
            os.replace(temp_path, target_file)
            print(f"Successfully updated {target_file}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        target = sys.argv[1]
        mapping = sys.argv[2]
        is_dry = "--dry-run" in sys.argv
        batch_replace(target, mapping, is_dry)
