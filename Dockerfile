# Gunakan Python 3.10 Slim (Ringan & Stabil)
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy semua file codingan
COPY . .

# Environment Variable agar log Python langsung muncul di Console Railway (PENTING)
ENV PYTHONUNBUFFERED=1

# Jalankan bot
CMD ["python", "daily_bot.py"]
