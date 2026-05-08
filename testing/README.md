Regression Testing

Purpose
- Keep quality checks simple, repeatable, and easy to run in development and CI.
- Verify behavior with automated regression tests instead of launch-time gating.

What this folder contains
- run_regression_tests.py
  - Runs pytest against the regression suite.
  - Supports verbose mode and optional JUnit report output.

How to run
- Standard regression run:
  - .venv\Scripts\python.exe continuous_validation\run_regression_tests.py
- Verbose run:
  - .venv\Scripts\python.exe continuous_validation\run_regression_tests.py --verbose
- Generate JUnit XML report:
  - .venv\Scripts\python.exe continuous_validation\run_regression_tests.py --report

What is tested
1. Core pages render successfully.
2. Vulnerable SQLi behavior differs from parameterized login behavior.
3. XSS safe rendering escapes dangerous content.
4. Scraping endpoint returns expected structured results.
5. SQLMap simulator reports expected findings for vulnerable target patterns.
6. Challenge scoring and progress APIs work.
7. Terminal command execution and admin data filters behave correctly.

Notes
- Tests use an isolated temporary database per run.
- Test source is in tests/test_regression.py.
