FILE=./requirements_dev.txt

all: dist

.PHONY: dist
dist: venv/created
	./setup.py sdist bdist_wheel

venv: venv/created
venv/created: $(FILE)
	rm -rf venv
	python3 -m venv ./venv
	./venv/bin/python3 -m pip install wheel
	./venv/bin/python3 -m pip install -r $(FILE)
	touch venv/created

.PHONY: lint
lint: venv/created
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