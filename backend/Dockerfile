FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including shell tools and Node.js
RUN apt-get update && apt-get install -y \
    curl \
    libpq-dev \
    gcc \
    bash \
    coreutils \
    findutils \
    grep \
    sed \
    gawk \
    tar \
    gzip \
    unzip \
    wget \
    git \
    nano \
    vim \
    tree \
    procps \
    net-tools \
    htop \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js and npm using the NodeSource repository
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g npm@latest \
    && echo "ALL ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=development \
    TERM=xterm-256color \
    SHELL=/bin/bash \
    PATH="/usr/local/bin:/usr/bin:/bin:/usr/local/lib/node_modules/npm/bin:${PATH}"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-install data science libraries to ensure they're available system-wide
RUN pip install --no-cache-dir pandas scipy numpy matplotlib

# Copy the application
COPY . .

# Create necessary directories
RUN mkdir -p /app/logs/dev /app/logs/prod /tmp/terminus_workspace

# Set proper permissions for workspace
RUN chmod 755 /tmp/terminus_workspace

# Create custom hosts file to set hostname
RUN echo "127.0.0.1 localhost terminuside" > /etc/hosts.custom && \
    echo "::1 localhost terminuside" >> /etc/hosts.custom

# Create Python startup file to auto-import data science libraries
RUN echo 'try:\n    import pandas as pd\n    import scipy as sp\n    import numpy as np\n    print("Data science libraries loaded: pandas, scipy, numpy")\nexcept ImportError:\n    print("Warning: Some data science libraries could not be loaded")' > /etc/python_startup.py
ENV PYTHONSTARTUP=/etc/python_startup.py

# Expose the port
EXPOSE 8000

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]