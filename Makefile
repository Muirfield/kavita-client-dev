KAVITA_VERSION = 0.9.1.4
KAVITA_BASE_URL = https://raw.githubusercontent.com/Kareadita/Kavita/
PYENV_DIR = ./.venv

.PHONY: help clean gen-api

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' Makefile | sort | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-30s\033[0m %s\n", $$1, $$2}'

clean:  ## Clean build
	rm -rf kavita_$(KAVITA_VERSION).json kavita_$(KAVITA_VERSION).fixed.json \
		kavita-client $(PYENV_DIR)/.kavita-client.tstamp

kavita_$(KAVITA_VERSION).json:
	wget -nv -O $@ \
		$(KAVITA_BASE_URL)/v$(KAVITA_VERSION)/openapi.json \
		|| { rc=$? ; rm -f "$@" ; exit $rc ; }

kavita_$(KAVITA_VERSION).fixed.json: kavita_$(KAVITA_VERSION).json fix_spec.py
	./pys.sh fix_spec.py kavita_$(KAVITA_VERSION).json $@

kavita-client/pyproject.toml: kavita_$(KAVITA_VERSION).fixed.json openapi-client-config.yml
	@rm -rf kavita-client
	./pys.sh openapi-python-client generate \
		--path kavita_$(KAVITA_VERSION).fixed.json \
		--config openapi-client-config.yml


build: kavita-client/pyproject.toml
#~ $(PYENV_DIR)/.kavita-client.tstamp: kavita-client/pyproject.toml
#~ 	./pys.sh pip install ./kavita-client \
#~ 		|| { rc=$? ; rm -f "$@" ; exit $rc ; }
#~ 	touch "$@"

#~ init: $(PYENV_DIR)/.kavita-client.tstamp	## Initialize environment

#~ fetch-spec: kavita_$(KAVITA_VERSION).json ## Fetch OpenAPI specs

#~ gen-api: kavita-client/pyproject.toml ## Generate Kavita client API

#~ $(PYENV_PKGDIR)/kavita_client-$(KAVITA_VERSION).dist-info/METADATA: kavita-client/pyproject.toml
#~ 	ls $(PYENV_PKGDIR)/kavita_client-$(KAVITA_VERSION).dist-info

	  
