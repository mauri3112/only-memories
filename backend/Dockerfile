FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md* ./
COPY only_memories ./only_memories
RUN pip install --no-cache-dir -e .

EXPOSE 8765
CMD ["only-memories-api"]
