FROM python:3.11-slim

WORKDIR /workspace

COPY backend/pyproject.toml backend/pyproject.toml
RUN pip install --no-cache-dir -e backend

COPY backend backend

EXPOSE 8000

CMD ["uvicorn", "backend.app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
