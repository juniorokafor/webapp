# Makefile for running and managing the webapp

.PHONY: run install clean

# run the application under gunicorn
run:
	gunicorn -w 4 -b 0.0.0.0:8000 main:app

# install python dependencies into the current venv
install:
	pip install -r requirements.txt

# remove bytecode files
clean:
	find . -name "*.pyc" -delete && find . -name "__pycache__" -type d -exec rm -rf {} +
