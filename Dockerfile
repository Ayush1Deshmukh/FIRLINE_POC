FROM python:3.13-slim

# Install system dependencies
RUN apt-get update && apt-get install -y curl git libpq-dev gcc

# Install Temporal CLI
RUN curl -sSf https://temporal.download/cli.sh | sh

WORKDIR /app

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Application Code
COPY . .

# Permissions
RUN chmod +x start.sh

# Environment Defaults
ENV PORT=10000

# Start Command
CMD ["./start.sh"]
