del "C:\Users\RM\Roaming\Workspaces\myrepos\ra-kay-sh-may-none\it-toolkit\fud\tests\test_failures.log"
del "C:\Users\RM\Roaming\Workspaces\myrepos\ra-kay-sh-may-none\it-toolkit\fud\src\patcher.log"
python -m coverage erase
rmdir /s /q htmlcov

set COVERAGE_PROCESS_START=
@REM C:\Users\RM\Roaming\Workspaces\myrepos\ra-kay-sh-may-none\it-toolkit\fud\\tests\.coveragerc"
set PYTHONPATH=.


python "C:\Users\RM\Roaming\Workspaces\myrepos\ra-kay-sh-may-none\it-toolkit\fud\tests\fud-patcher-test-runner.py"

@REM  --rcfile="C:\Users\RM\Roaming\Workspaces\myrepos\ra-kay-sh-may-none\it-toolkit\fud\\tests\.coveragerc"
@REM python -m coverage run -m unittest "C:\Users\RM\Roaming\Workspaces\myrepos\ra-kay-sh-may-none\it-toolkit\fud\tests\fud-patcher-test-runner.py"
python -m coverage combine
@REM python -m coverage report -m
python -m coverage report -m "C:\Users\RM\Roaming\Workspaces\myrepos\ra-kay-sh-may-none\it-toolkit\fud\src\fud-patcher.py"
python -m coverage html

python "C:\Users\RM\Roaming\Workspaces\myrepos\ra-kay-sh-may-none\it-toolkit\batch_replace\batch_replace.py" "C:\Users\RM\Roaming\Workspaces\myrepos\ra-kay-sh-may-none\it-toolkit\fud\tests\test_failures.log" "C:\Users\RM\Roaming\Workspaces\myrepos\ra-kay-sh-may-none\it-toolkit\batch_replace\safe_rulex.txt"  --dry-run