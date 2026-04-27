import json
import csv
import os
import sys

def main():
    if len(sys.argv) < 3:
        print("Usage: python export_coverage.py <input_json> <output_tsv>")
        sys.exit(1)

    json_input = sys.argv[1]
    tsv_output = sys.argv[2]

    if not os.path.exists(json_input):
        print(f"Error: {json_input} not found.")
        sys.exit(1)

    with open(json_input, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 1. Find the target file entry
    target_path = next((path for path in data['files'] if 'fud-patcher.py' in path), None)
    if not target_path:
        print("Error: Could not find 'fud-patcher.py' in the coverage data.")
        sys.exit(1)

    file_data = data['files'][target_path]
    
    # 2. Extract the Context Map (ID -> Test Name)
    # The JSON stores this at the file level in some versions or root in others
    context_map = file_data.get('contexts', {})
    
    # 3. Get line data
    executed = file_data.get('executed_lines', [])
    missing = file_data.get('missing_lines', [])
    # This dictionary maps LineNo -> List of Context IDs (integers/strings)
    contexts_by_lineno = file_data.get('contexts', {})
    # contexts_by_lineno = file_data.get('contexts_by_lineno', {})
    print(len(contexts_by_lineno))
    # 4. Read source code
    source_lines = {}
    max_len=0
    try:
        with open(target_path, 'r', encoding='utf-8') as src_f:
            for i, line in enumerate(src_f, 1):
                line=line.strip()
                source_lines[i] = line
                if len(line) > max_len:
                    max_len=len(line)
    except Exception:
        print(f"Warning: Could not read source file at {target_path}")

    # 5. Write the TSV
    with open(tsv_output, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow(['LineNo', 'Status', 'Source Code'.ljust(max_len), 'Tests'])
        
        all_line_nos = sorted(list(set(executed + missing)))
        for lno in all_line_nos:
            status = "COVERED" if lno in executed else "MISSING"
            line_text = source_lines.get(lno, "[Source Not Found]")
            
            # Resolve the IDs into actual test names
            # contexts_by_lineno[str(lno)] returns a list of IDs like [2, 5, 10]
            ids = contexts_by_lineno.get(str(lno), [])
            # print(ids)
            test_names = [context_map.get(str(cid), str(cid)) for cid in ids]
            
            line_contexts = ", ".join(test_names)
            writer.writerow([lno, status, line_text.ljust(max_len), line_contexts])

    print(f"Success! {target_path} exported to {tsv_output}")

if __name__ == "__main__":
    main()
