@REM pip install coverage
@REM python -c "import sys; import os; print(os.path.join(sys.prefix, 'Scripts'))"
@REM python -m coverage erase
@REM python -m coverage run -m unittest test_batch_replace.py
@REM python -m coverage combine
@REM python -m coverage report -m
@REM python -m coverage html

@echo off
:: 1. Clean up old data
python -m coverage erase
rmdir /s /q htmlcov

:: 2. Set environment variables for the current session
set COVERAGE_PROCESS_START=.coveragerc
set PYTHONPATH=.

:: 3. Run the tests
python -m coverage run -m unittest test_batch_replace.py

:: 4. Merge subprocess data and show report
python -m coverage combine
python -m coverage report -m
python -m coverage html
@REM pause
