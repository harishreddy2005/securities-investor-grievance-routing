FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 ANONYMIZED_TELEMETRY=False

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY corpus/raw/ ./corpus/raw/
COPY scripts/ ./scripts/
RUN useradd --create-home router && mkdir -p /data/index /home/router/.cache && chown -R router:router /app /data /home/router/.cache
USER router

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
