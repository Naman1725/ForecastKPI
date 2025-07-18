# 1) Base image
FROM python:3.9-slim

# 2) Set working directory
WORKDIR /app

# 3) Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4) Copy application code
COPY . .

# 5) Expose the port Flask runs on
EXPOSE 5000

# 6) Start the Flask app using Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
