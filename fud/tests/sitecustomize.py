import coverage
import os
import sys
raw_cmd = " ".join(sys.argv)
print(f"raw_cmd={raw_cmd}")
rc_file = os.environ.get("COVERAGE_RCFILE", "DEFAULT (No RCFILE found)")
coverage_file = os.environ.get("COVERAGE_FILE", "DEFAULT (No COVERAGEFILE found)")
# if not os.environ.get("COVERAGE_RUN", False):
#     if os.environ.get("COVERAGE_PROCESS_START"):
#         # F12: Access the configuration file path in Coverage 7.x
#         cov = coverage.Coverage()
#         # For Coverage 7.x, the path is stored in 'config' or '_config' depending on the exact build
#         actual_rc = getattr(cov, 'config', None)
#         if hasattr(actual_rc, 'config_file'):
#             actual_rc = actual_rc.config_file

#         # print("Started")

#         print(f"Started - {rc_file} - {actual_rc} - {coverage_file}")
#         coverage.process_startup()
# else:
#     print(f"Already running - {rc_file} - {coverage_file}")