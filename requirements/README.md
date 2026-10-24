# M00 dependency policy

Status: `NOT_RUN` on CloudStudio. Use only Python venv + pip and pytest for this PoC.
`m00.in` contains provisional compatibility ranges, not exact versions or a verified lock.
Only the isolated PoC dependencies are declared. No frontend or FastAPI project is created.
Node/npm/SQLite CLI are checked as toolchain prerequisites for later approved work;
this batch installs no JavaScript dependencies and therefore has no npm lock file.

After installation and real cloud tests, capture all resolved versions with
`python -m pip freeze --all > var/m00/requirements.cloudstudio.txt`.
Send the sanitized environment report, candidate lock, commit and test results back
for review. Only then commit a calibrated `requirements/m00.lock.txt` and demonstrate
a fresh venv installation using `python -m pip install -r requirements/m00.lock.txt`.
The candidate snapshot alone is not proof of reproducibility. Platform/Python version
and package source are part of the replay record. Do not share private index URLs.
