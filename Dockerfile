# Use multi-stage build to keep image small and secure
FROM python:3.11-slim-bookworm as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    protobuf-compiler \
    libprotobuf-dev \
    build-essential \
    git \
    bison \
    flex \
    libnl-route-3-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install nsjail
RUN git clone https://github.com/google/nsjail.git /nsjail \
    && cd /nsjail \
    && make \
    && cp nsjail /usr/bin/

# Install python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.11-slim-bookworm

# Copy nsjail from builder
COPY --from=builder /usr/bin/nsjail /usr/bin/nsjail

# Install runtime dependencies for nsjail
# We install libprotobuf-dev to ensure compatible shared libraries are present without guessing the version suffix
RUN apt-get update && apt-get install -y \
    libprotobuf-dev \
    libnl-route-3-200 \
    && rm -rf /var/lib/apt/lists/*

# Copy python packages from builder
COPY --from=builder /root/.local /home/appuser/.local

# Create non-root user
RUN useradd -m -u 1000 appuser
USER appuser
WORKDIR /home/appuser

# Add local bin to path
ENV PATH=/home/appuser/.local/bin:$PATH

# Copy application code
COPY --chown=appuser:appuser app.py nsjail.cfg ./

# Expose port
EXPOSE 8080

# Run application
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]
