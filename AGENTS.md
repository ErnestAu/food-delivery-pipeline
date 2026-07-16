# dbt PR reviewer rules

- Review only the analyst SQL file explicitly named in the prompt.
- Use dbt test output and declared model contracts as evidence; do not guess unstated business intent.
- For a high-confidence mechanical defect, return the smallest proposed SQL correction and explain it.
- For a semantically ambiguous result, return a warning and a clarifying question; do not propose a patch.
- Never edit tests, seeds, profiles, source data, or established core models to make a test pass.
- Never write the proposed SQL to disk. A human reviewer decides whether to accept it.
