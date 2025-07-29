# Use official Python base image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Collect static files (optional, useful in prod)
RUN python manage.py collectstatic --noinput

# Run Django app
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

