# Gunakan Python versi ringan
FROM python:3.10-slim

# Set folder kerja di dalam container
WORKDIR /app

# Copy semua file ke dalam container
COPY . .

# Install library dari requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Jalankan bot
CMD ["python", "daily_bot.py"]
