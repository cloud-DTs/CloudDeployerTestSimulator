FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY simulator/ simulator/
EXPOSE 5000
HEALTHCHECK --interval=5s --timeout=3s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000', timeout=2)" || exit 1

ENTRYPOINT ["python", "/app/main.py"]