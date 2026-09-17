# Reference analysis code

These three files are unchanged copies from
[KaumindiHerath/Big_Data_Geospatial_Project](https://github.com/KaumindiHerath/Big_Data_Geospatial_Project/tree/75aa5b3b00cbe3630833ad49902026171a054332/src),
commit `75aa5b3b00cbe3630833ad49902026171a054332`:

- `ml_pipeline.py`: geographic/time feature preparation and metric evaluation.
- `regression.py`: OLS with standard errors clustered by location.
- `data_quality.py`: original plausibility-screen definitions.

The new runner (`../replicate_findings.py`) imports these helpers. It does not run
their original `main()` functions, whose fixed paths, dates and six-site narrative
are inappropriate for the expanded dataset. The unmodified source is retained for
attribution and comparison; its comments are not findings for the new data.

Use `reports/replication/requirements-lock.txt` to recreate the environment used
for the results. Method changes are documented in `reports/replication/README.md`.
