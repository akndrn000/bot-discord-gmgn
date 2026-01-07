FROM python:3.10-slim

WORKDIR /app

# Install git/tools dasar
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Install library python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy semua kode ke dalam container
COPY . .

# Perintah menjalankan bot
CMD ["python", "daily_bot.py"]
