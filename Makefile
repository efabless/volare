FILE=./requirements.txt

.PHONY: venv-dev venv
venv-dev: FILE=./requirements_dev.txt
venv-dev: venv
venv:
	rm -rf venv
	python3 -m venv ./venv
	./venv/bin/python3 -m pip install wheel
	./venv/bin/python3 -m pip install -r $(FILE)

.PHONY: lint
lint:
	./venv/bin/black --check .
	./venv/bin/flake8 .

.PHONY: veryclean
veryclean: clean
veryclean:
	rm -rf venv/

.PHONY: clean
clean:
	rm -rf build/
	rm -rf logs/
	rm -rf dist/
	rm -rf *.egg-info