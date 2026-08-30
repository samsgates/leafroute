.PHONY: install test smoke artifact benchmark api

install:
	python -m pip install -e ".[dev,api]"

test:
	pytest -q

smoke:
	python -m compileall -q leafroute
	pytest -q

artifact:
	leafroute compile examples/sample_financial.md -o examples/sample_financial.leaf

benchmark: artifact
	leafroute benchmark examples/sample_financial.leaf benchmarks/sample_cases.json -o benchmark-report.json

api: artifact
	leafroute serve examples/sample_financial.leaf
