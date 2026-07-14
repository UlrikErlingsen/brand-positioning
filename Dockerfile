FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src \
    ARROW_DEFAULT_MEMORY_POOL=system

WORKDIR /app

# Keep dependency installation in a reusable layer when only application code changes.
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY . .

# PositionSignal does not need root privileges at runtime.
RUN useradd --create-home --uid 10001 positionsignal \
    && chown -R positionsignal:positionsignal /app
USER positionsignal

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=3)"

CMD ["python", "-m", "streamlit", "run", "app.py", "--server.headless=true", "--server.address=0.0.0.0", "--server.port=8501", "--browser.gatherUsageStats=false"]
