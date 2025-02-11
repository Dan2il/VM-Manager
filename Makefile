PY = py.exe

run:
	docker-compose up --build


test:
	$(PY) -m pytest -sv
