# MPCI Q&A System - Docker Deployment
# Build: docker build -t mpci-qa .
# Run:   docker run -d -p 8000:8000 --env-file .env mpci-qa

FROM python:3.12-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir fastapi uvicorn chromadb openai pypdf

# Copy application
COPY mpci_qa/ ./mpci_qa/
COPY pdf_text.txt ./

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Start server
CMD ["python", "-m", "mpci_qa.server"]
