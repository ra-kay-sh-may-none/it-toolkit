del "C:\Users\RM\Roaming\Workspaces\myrepos\ra-kay-sh-may-none\it-toolkit\fud\tests\test_failures.log"
del "C:\Users\RM\Roaming\Workspaces\myrepos\ra-kay-sh-may-none\it-toolkit\fud\src\patcher.log"
python -m coverage erase
rmdir /s /q htmlcov

set COVERAGE_PROCESS_START=.coveragerc
set PYTHONPATH=.


@REM python "C:\Users\RM\Roaming\Workspaces\myrepos\ra-kay-sh-may-none\it-toolkit\fud\tests\fud-patcher-test-runner.py"

python -m coverage run -m unittest "C:\Users\RM\Roaming\Workspaces\myrepos\ra-kay-sh-may-none\it-toolkit\fud\tests\fud-patcher-test-runner.py"
python -m coverage combine
python -m coverage report -m
python -m coverage html

python "C:\Users\RM\Roaming\Workspaces\myrepos\ra-kay-sh-may-none\it-toolkit\batch_replace\batch_replace.py" "C:\Users\RM\Roaming\Workspaces\myrepos\ra-kay-sh-may-none\it-toolkit\fud\tests\test_failures.log" "C:\Users\RM\Roaming\Workspaces\myrepos\ra-kay-sh-may-none\it-toolkit\batch_replace\safe_rulex.txt"  --dry-run