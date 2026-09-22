KAVITA_VERSION = 0.9.1.4
KAVITA_BASE_URL = https://raw.githubusercontent.com/Kareadita/Kavita/
KAVITA_DEV_BRANCH = develop
KAVITA_IMAGE ?= jvmilazz0/kavita:latest
PYENV_DIR = ./.venv
TEST_REPORT ?= reports/junit.xml
SCHEMATHESIS_STATE ?= /tmp/schemathesis-state.json

.PHONY: help clean build-nightly build test test-fix_spec test-nightly test-release \
	schemathesis-release schemathesis-nightly sphinx-html gh-pages

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' Makefile | sort | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-30s\033[0m %s\n", $$1, $$2}'

clean:  ## Clean build
	rm -rf kavita_$(KAVITA_VERSION).json \
			kavita_$(KAVITA_VERSION).fixed.json \
			$(KAVITA_VERSION)-fixed
	rm -rf kavita_DEV.json \
			DEV

kavita_DEV.json:
	wget -nv -O $@ \
		$(KAVITA_BASE_URL)/refs/heads/$(KAVITA_DEV_BRANCH)/openapi.json \
		|| { rc=$? ; rm -f "$@" ; exit $rc ; }
  
kavita_$(KAVITA_VERSION).json:
	wget -nv -O $@ \
		$(KAVITA_BASE_URL)/v$(KAVITA_VERSION)/openapi.json \
		|| { rc=$? ; rm -f "$@" ; exit $rc ; }

kavita_$(KAVITA_VERSION).fixed.json: kavita_$(KAVITA_VERSION).json fix_spec.py kavita_quirks.yaml
	./pys.sh fix_spec.py kavita_$(KAVITA_VERSION).json $@ $(KAVITA_VERSION)

DEV/kavita-client/pyproject.toml: \
	kavita_DEV.json openapi-client-config.yml
	mkdir -p "DEV"
	rm -rf "$(dir $@)"
	( cd DEV && ../pys.sh openapi-python-client generate \
		--path ../kavita_DEV.json \
 		--config ../openapi-client-config.yml )
	
build-nightly: DEV/kavita-client/pyproject.toml	## Builds a unpatched version of the project

$(KAVITA_VERSION)-fixed/kavita-client/pyproject.toml: \
	kavita_$(KAVITA_VERSION).fixed.json openapi-client-config.yml
	mkdir -p "$(KAVITA_VERSION)-fixed"
	rm -rf "$(dir $@)"
	( cd $(KAVITA_VERSION)-fixed && ../pys.sh openapi-python-client generate \
		--path ../kavita_$(KAVITA_VERSION).fixed.json \
 		--config ../openapi-client-config.yml )

build: $(KAVITA_VERSION)-fixed/kavita-client/pyproject.toml	## Builds a patched version of the project

#~ kavita-client/pyproject.toml: kavita_$(KAVITA_VERSION).fixed.json openapi-client-config.yml
#~ 	@rm -rf kavita-client
#~ 	./pys.sh openapi-python-client generate \
#~ 		--path kavita_$(KAVITA_VERSION).fixed.json \
#~ 		--config openapi-client-config.yml

test-fix_spec:  ## Run the offline unit tests (no docker needed)
	./pys.sh -m pytest tests/test_fix_spec.py tests/test_fix_spec_cli.py tests/test_fix_spec_regression.py

test-nightly:	## Run nightly snapshot tests
	./pys.sh pip install --force-reinstall --no-deps "./DEV/kavita-client"
	mkdir -p $(dir $(TEST_REPORT))
	KAVITA_MODE=nightly KAVITA_IMAGE=$(KAVITA_IMAGE) ./pys.sh -m pytest --junitxml=$(TEST_REPORT)
	./pys.sh pip uninstall -y kavita-client

test-release:	## Run release tests
	./pys.sh pip install --force-reinstall --no-deps "./$(KAVITA_VERSION)-fixed/kavita-client"
	mkdir -p $(dir $(TEST_REPORT))
	KAVITA_MODE=release KAVITA_IMAGE=$(KAVITA_IMAGE) ./pys.sh -m pytest --junitxml=$(TEST_REPORT)
	./pys.sh pip uninstall -y kavita-client

sphinx-html:	## HTML API documentation (via sphinx)
	./pys.sh make -C sphinx html KAVITA_VERSION=$(KAVITA_VERSION)

schemathesis-release: ## Schemathesis canary: patched spec vs the stable image
	mkdir -p reports
	./pys.sh schemathesis_stack.py up $(SCHEMATHESIS_STATE) --image $(KAVITA_IMAGE)
	trap './pys.sh schemathesis_stack.py down $(SCHEMATHESIS_STATE)' EXIT; \
	./pys.sh schemathesis_canary.py kavita_$(KAVITA_VERSION).fixed.json release \
		$(SCHEMATHESIS_STATE) reports/schemathesis-junit.xml

schemathesis-nightly: kavita_DEV.json ## Schemathesis canary: raw dev spec vs the nightly image
	mkdir -p reports
	./pys.sh schemathesis_stack.py up $(SCHEMATHESIS_STATE) --image jvmilazz0/kavita:nightly
	trap './pys.sh schemathesis_stack.py down $(SCHEMATHESIS_STATE)' EXIT; \
	./pys.sh schemathesis_canary.py kavita_DEV.json nightly \
		$(SCHEMATHESIS_STATE) reports/schemathesis-nightly-junit.xml

gh-pages: sphinx-html ## Local site build (docs/ + status pages) into gh-pages/
	./pys.sh pages/build_site.py --version $(KAVITA_VERSION)
