import json
# import csv
import os
import sys

def main():
    if len(sys.argv) < 2:
        print("Usage: python export_coverage.py <json_in> [psv_out] [aligned_psv_out]")
        sys.exit(1)

    json_input = sys.argv[1]
    
    # Precedence Logic for psv
    if len(sys.argv) >= 3:
        psv_output = sys.argv[2]
    else:
        psv_output = os.path.splitext(json_input)[0] + ".psv"

    # Precedence Logic for aligned_psv
    if len(sys.argv) >= 4:
        aligned_psv_output = sys.argv[3]
    else:
        aligned_psv_output = os.path.splitext(psv_output)[0] + ".aligned.psv"

    if not os.path.exists(json_input):
        print(f"Error: {json_input} not found.")
        sys.exit(1)

    with open(json_input, 'r', encoding='utf-8') as f:
        data = json.load(f)

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
                line=line.strip("\r\n")
                source_lines[i] = line
                if len(line) > max_len:
                    max_len=len(line)
    except Exception as e:        
        print(f"Error: Could not read source file at {target_path}")
        raise
    
    # 5. Write the psv
    # with open(psv_output, 'w', newline='', encoding='utf-8') as f:
    with open(psv_output, 'w', encoding='utf-8') as fc, open(aligned_psv_output, 'w', newline='', encoding='utf-8') as ft:
        # writer = csv.writer(f, delimiter='\t')
        # writer.writerow(['LineNo', 'Status', 'Source Code'.ljust(max_len), 'Tests'])
        header = f"{'LNo'} | {'Status'} | {'Source Code'} | {'Tests'}\n"
        fc.write(header)
        fc.write("-" * len(header) + "\n")

        header = f"{'LNo':<5} | {'Status':<8} | {'Source Code'.ljust(max_len)} | {'Tests'}\n"
        ft.write(header)
        ft.write("-" * len(header) + "\n")
        
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
            # writer.writerow([lno, status, line_text.ljust(max_len), line_contexts])

            line_out = f"{lno} | {status} | {line_text} | {line_contexts}\n"
            fc.write(line_out)

            line_out = f"{lno:<5} | {status:<8} | {line_text.ljust(max_len)} | {line_contexts}\n"
            ft.write(line_out)
    print(f"Success! {target_path} exported to {psv_output} and to {aligned_psv_output}")

if __name__ == "__main__":
    main()
