# Use an official Python runtime as a parent image
FROM python:3.7-slim

# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --trusted-host pypi.python.org -r requirements.txt

# Build sertificate

# Make port 80 available to the world outside this container
EXPOSE 80

# Define environment variable
#ENV ENV_NAME env_value

# Run bot.py when the container launches
CMD ["python", "app.py"]
