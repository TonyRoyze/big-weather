# Report structure

The report body is maintained in `docs/report/content.typ` and shared by both
Typst entry points. `make report` builds `docs/report/main.pdf`.

1. Introduction and project scope — objectives, research scope, and implementation status.
2. Data and analytical methodology — sources, spatial and temporal coverage, and quality rules.
3. Findings — regional analysis, matched coverage, data quality, geographic and
   elevation relationships, aggregation and Spark validation, historical comparison, and limitations.
4. System architecture and data engineering — system flow; reasons for Snowflake,
   data marts, and dbt; ingestion, warehouse models, serving, and reproducibility.
5. Dashboard and user workflows — map controls, query lifecycle, required coverage-aware
   ingestion, and plain-English analysis.
6. Validation and operational requirements — acceptance criteria, performance,
   deployment, and interpretive limitations.
7. Execution and reproducibility — local operation, warehouse integration, and release checks.
