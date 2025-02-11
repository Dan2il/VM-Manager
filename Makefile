PY = py.exe

RUN_DB:
	cd .\src\
	docker-compose up -d


test:
	$(PY) -m pytest -sv
