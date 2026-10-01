FROM python:3.13-slim

WORKDIR /app

# Copy dependency specifications
COPY pyproject.toml uv.lock ./

# Install uv and sync dependencies into virtual environment
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev

# Copy application source code
COPY app ./app

# Ensure commands run from the uv virtualenv
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
