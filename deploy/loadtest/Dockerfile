FROM python:3.11-slim
WORKDIR /load
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY requirements-load.txt .
RUN pip install --no-cache-dir -r requirements-load.txt
COPY loadtests/ ./loadtests/
COPY locustfile.py .
RUN useradd --create-home loadtester && mkdir /results && chown loadtester:loadtester /results
USER loadtester
ENTRYPOINT ["locust"]
