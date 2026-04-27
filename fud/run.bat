@echo off

set PROJECT_ROOT=%CD%

del "%PROJECT_ROOT%\tests\test_failures.log"
del "%PROJECT_ROOT%\tests\test_success.log"
del "%PROJECT_ROOT%\src\patcher.log"

set "COVERAGE_PROCESS_START=%PROJECT_ROOT%\tests\.coveragerc"
set "COVERAGE_RCFILE=%PROJECT_ROOT%\tests\.coveragerc"
@REM set "COVERAGE_FILE=%PROJECT_ROOT%\.coverage"
@REM set "COVERAGE_DATA_FILE=%PROJECT_ROOT%\.coverage"
set "COVERAGE_FILE="
set "COVERAGE_DATA_FILE="
set PYTHONPATH=.;tests/;src/;
python -m coverage erase
del .coverage
del .coverage.*
rmdir /s /q htmlcov

@REM %PROJECT_ROOT%\tests\.coveragerc"


python "%PROJECT_ROOT%\tests\fud-patcher-test-runner.py"

@REM  --rcfile="%PROJECT_ROOT%\tests\.coveragerc"
@REM python -m coverage run -m unittest "%PROJECT_ROOT%\tests\fud-patcher-test-runner.py"
python -m coverage combine
@REM python -m coverage report -m
python -m coverage report -m
@REM python -m coverage html

@REM python -m coverage report -m --show-contexts
python -m coverage html --show-contexts

python -m coverage json --show-contexts --pretty-print -o coverage_detailed.json

python "C:\Users\RM\Roaming\Workspaces\myrepos\ra-kay-sh-may-none\it-toolkit\batch_replace\batch_replace.py" "%PROJECT_ROOT%\tests\test_failures.log" "C:\Users\RM\Roaming\Workspaces\myrepos\ra-kay-sh-may-none\it-toolkit\batch_replace\safe_rulex.txt"  --dry-run