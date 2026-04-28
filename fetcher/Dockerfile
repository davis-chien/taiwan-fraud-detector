FROM python:3.11-slim

WORKDIR /app

# iptables: network egress policy (Layer 5 defense-in-depth)
# gosu: privilege drop in entrypoint (applies iptables as root, then execs uvicorn as appuser)
RUN apt-get update && apt-get install -y --no-install-recommends \
    whois \
    iptables \
    gosu \
    && rm -rf /var/lib/apt/lists/*

COPY fetcher/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only the four pipeline modules this worker needs.
# Use a stub __init__.py — the real one pulls in anthropic/chromadb/voyageai
# which are not needed here.
COPY pipeline/scraper.py pipeline/scraper.py
COPY pipeline/unshortener.py pipeline/unshortener.py
COPY pipeline/enricher.py pipeline/enricher.py
COPY pipeline/validator.py pipeline/validator.py
RUN touch pipeline/__init__.py

COPY fetcher/main.py main.py
COPY fetcher/entrypoint.sh entrypoint.sh
RUN chmod +x entrypoint.sh

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app

# Run as root so the entrypoint can apply iptables rules; the entrypoint
# drops to appuser via gosu before exec-ing uvicorn.
EXPOSE 8080

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gosu", "appuser", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
