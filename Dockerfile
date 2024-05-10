# 1
FROM gcr.io/distroless/python3

# 2
RUN pip install flask gunicorn firebase_admin bs4 flask-cors google-cloud-firestore

# 3
COPY src/ /app
WORKDIR /app

# 4
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", "main:app"]
