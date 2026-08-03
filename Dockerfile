FROM python:3.14-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        aria2 \
        nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py config.py hwaccel.py r2.py ./
COPY templates/ templates/
COPY static/ static/
COPY cookies/README.md cookies/

RUN mkdir -p temp

ENV HOST=0.0.0.0 \
    PORT=5000

EXPOSE 5000

VOLUME ["/app/temp"]

CMD ["python", "app.py"]
