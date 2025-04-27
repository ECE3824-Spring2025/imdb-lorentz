# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

# Expose the port your app runs on (default Flask port)
EXPOSE 8080

# Define environment variable
ENV FLASK_APP=app.py

# Run the application
CMD ["python", "app.py"]
