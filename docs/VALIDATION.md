# Local Validation

The source archive was validated before packaging with:

```bash
python -m compileall -q leafroute
PYTHONPATH=. pytest -q
python -m pip wheel . --no-deps --no-build-isolation
```

The included test suite passed all 9 tests during packaging.

Additional CLI smoke checks exercised:

- `leafroute compile`
- `leafroute search`
- `leafroute benchmark`
- artifact reopen
- route cache

The sample benchmark exists only to validate the benchmark plumbing. It is not evidence of competitive performance on real datasets.
