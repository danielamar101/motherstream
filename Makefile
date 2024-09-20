
pip-compile:
	pip-compile requirements.in -o requirements.txt

pip-sync:
	pip-sync requirements.txt