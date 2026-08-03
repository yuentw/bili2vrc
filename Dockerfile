FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        aria2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py config.py hwaccel.py ./
COPY templates/ templates/
COPY cookies/README.md cookies/

RUN mkdir -p temp cookies

ENV HOST=0.0.0.0 \
    PORT=5000

EXPOSE 5000

VOLUME ["/app/cookies", "/app/temp"]

CMD ["python", "app.py"]
