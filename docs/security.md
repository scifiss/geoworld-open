# Security Design Notes

GeoWorld Open is offline-first. The workflow itself makes no network requests and requires no credentials. The local Streamlit demo reads only repository example YAML and writes each run to a temporary local directory.

Repository safeguards include:

- a deny-oriented `.gitignore` for environment files, credentials, databases, archives, run directories, and large scientific binaries;
- a placeholder-only `.env.example`;
- a local pre-commit secret scan and matching CI job;
- dependency review for pull requests;
- tests that reject imports from the private `geoworld` package and common production service dependencies.

These controls reduce risk but do not replace review. Before publishing a change, inspect the complete staged diff, run the scanner, and verify that fixtures and images contain no private or licensed data.

