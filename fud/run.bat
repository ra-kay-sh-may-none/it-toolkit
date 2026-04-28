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
set PYTHONPATH=.;%PROJECT_ROOT%\tests;%PROJECT_ROOT%\src;

@REM run with yes before running no, if coverage files are not there
set FUD_FULL_SUITE=no

if "%FUD_FULL_SUITE%"=="yes" (
    python -m coverage erase
    del %PROJECT_ROOT%\.coverage
    del %PROJECT_ROOT%\.coverage.*
)

rmdir /s /q htmlcov

if "%FUD_FULL_SUITE%"=="yes" (
    python "%PROJECT_ROOT%\tests\fud-patcher-test-runner.py"
) else (
    python "%PROJECT_ROOT%\tests\fud-patcher-test-runner.py" -k test_16_
)

@REM  --rcfile="%PROJECT_ROOT%\tests\.coveragerc"
@REM python -m coverage run -m unittest "%PROJECT_ROOT%\tests\fud-patcher-test-runner.py"

python -m coverage combine --keep

python -m coverage report -m
@REM python -m coverage html
python -m coverage html --show-contexts

del %PROJECT_ROOT%\coverage_detailed.json
python -m coverage json --show-contexts --pretty-print -o "%PROJECT_ROOT%\coverage_detailed.json"

del "%PROJECT_ROOT%\coverage_detailed.psv"
del "%PROJECT_ROOT%\coverage_detailed.aligned.psv"
python "%PROJECT_ROOT%\..\python-coverage-tools\convert_coverage_json_to_psv.py" "%PROJECT_ROOT%\coverage_detailed.json"

python "%PROJECT_ROOT%\..\batch_replace\batch_replace.py" "%PROJECT_ROOT%\tests\test_failures.log" "%PROJECT_ROOT%\..\batch_replace\safe_rulex.txt"  --dry-run

@REM grep -h -C 1 "| MISSING |"  "%PROJECT_ROOT%\coverage_detailed.psv"
@REM @REM --group-separator="--------------------------------" 
python "%PROJECT_ROOT%\..\content-search\context-search.py" "| MISSING |" "%PROJECT_ROOT%\coverage_detailed.psv" -hide -C 0 -s "============"
set FUD_FULL_SUITE=