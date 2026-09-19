# Used by `sam build` (BuildMethod: makefile) for the Lambda function. SAM runs this from a copy of
# this directory; see scripts/build_lambda.py for what goes into the package.
PYTHON ?= python3

build-ApiFunction:
	$(PYTHON) scripts/build_lambda.py "$(ARTIFACTS_DIR)"
