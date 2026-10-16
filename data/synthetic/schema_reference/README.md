# Reviewed upstream schema references

These are exact source copies fetched read-only from htmw/F2026-Team3,
branch feature/backend-integration, on October 14, 2026. They are not replacements
for backend/ and are not a Git checkout. Do not execute seed_data.py.

- models.py Git blob: 55baede2fb80a489dd192fed7fe218679ae88945
- seed_data.py Git blob: 8e01bedef06fa6ba589f6e088a349d798f86fc52

The validator imports models.py in an isolated module and parses seed_data.py using
AST without importing/executing it. SHA-256 and exact Git blob identities are checked.
Local backend source and PostgreSQL remain untouched. Import approval requires a real
target checkout and schema synchronization/migration review; this snapshot does not do that.
