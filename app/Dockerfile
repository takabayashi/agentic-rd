# Pinned base image (exact patch, not :latest). Kept in lockstep with the CI
# Python (.github/workflows/ci.yml) and ruff's target-version (ruff.toml) so the
# image, linter, and tests all run the same interpreter.
FROM python:3.12.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

EXPOSE 8080

CMD ["uvicorn", "triage.main:app", "--host", "0.0.0.0", "--port", "8080"]
