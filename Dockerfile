FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir -e ".[test]"
COPY tests ./tests
COPY conftest.py ./
CMD ["pytest", "-q"]
