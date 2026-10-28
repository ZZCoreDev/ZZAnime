FROM python:3.11-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg rubberband-cli espeak-ng libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/zzdub
COPY requirements*.txt ./
RUN pip install --no-cache-dir -r requirements-gpu.txt
COPY dubpipe ./dubpipe
COPY config.yml sources.yml ./
COPY glossary ./glossary
CMD ["python", "-m", "dubpipe.cli", "doctor"]
