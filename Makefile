.PHONY: test run migrate lint help

help:
	@echo "ZAYVORA MATAB OS — Developer Commands"
	@echo "  make test      Run entire automated test suite"
	@echo "  make migrate   Apply database migrations"
	@echo "  make run       Start the standalone MATAB OS server"

test:
	python3 -m unittest discover -s tests -p "test_*.py" -v

migrate:
	python3 -m matab.database.migrator

run:
	python3 -m matab.server
