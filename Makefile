REQ_FILES = ./requirements_dev.txt ./requirements.txt
REQ_FILES_PFX = $(addprefix -r ,$(REQ_FILES))

all: dist

.PHONY: dist
dist: venv/manifest.txt
	./venv/bin/python3 setup.py sdist bdist_wheel

.PHONY: lint
lint: venv/manifest.txt
	./venv/bin/black --check .
	./venv/bin/flake8 .
	./venv/bin/mypy .

venv: venv/manifest.txt
venv/manifest.txt: $(REQ_FILES)
	rm -rf venv
	python3 -m venv ./venv
	PYTHONPATH= ./venv/bin/python3 -m pip install --upgrade pip
	PYTHONPATH= ./venv/bin/python3 -m pip install --upgrade wheel
	PYTHONPATH= ./venv/bin/python3 -m pip install --upgrade $(REQ_FILES_PFX)
	PYTHONPATH= ./venv/bin/python3 -m pip freeze > $@

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