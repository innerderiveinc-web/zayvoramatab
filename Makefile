.PHONY: test test-unit test-integration test-e2e migrate seed run package help

help:
	@echo "ZAYVORA MATAB OS — Developer Commands"
	@echo "  make test             Run full automated test suite"
	@echo "  make test-unit        Run unit test suite"
	@echo "  make test-integration Run integration test suite"
	@echo "  make test-e2e         Run end-to-end smoke test"
	@echo "  make migrate          Apply database schema migrations"
	@echo "  make seed             Seed synthetic development dataset"
	@echo "  make run              Start the standalone MATAB OS server"
	@echo "  make package          Create clean, secret-free release ZIP distribution"

package:
	@rm -f zayvora_matab_os_latest.zip zayvora_matab_os_distribution.zip
	@zip -q -r zayvora_matab_os_latest.zip . \
		-x "*.git*" ".venv/*" "node_modules/*" "apps/mobile/node_modules/*" "apps/mobile/.expo/*" "*.pyc" "**/__pycache__/*" \
		   "*.db*" "backups/*" "*.backup_*" "*.DS_Store" "*__MACOSX*" \
		   ".env*" "!.env.example" ".matab_secret*" "*.zip" "test_cds_unit_*" ".system_generated/*"
	@echo "Created clean release package: zayvora_matab_os_latest.zip"

test:
	python3 -m unittest discover -s tests -p "test_*.py" -v

test-unit:
	python3 -m unittest discover -s tests/unit -p "test_*.py" -v

test-integration:
	python3 -m unittest discover -s tests/integration -p "test_*.py" -v

test-e2e:
	python3 -m unittest discover -s tests/e2e -p "test_*.py" -v

migrate:
	python3 -m apps.api.database.migrator

seed:
	python3 -m apps.api.database.seed

run:
	./start_matab.sh
