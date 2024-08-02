# Use a specific OpenJDK version base image
FROM openjdk:11.0.11-jre-slim

# Set the working directory in the container
WORKDIR /app

# Copy the JAR file into the container
COPY target/kafka_streams_app-1.0-SNAPSHOT.jar /app/kafka-streams-app.jar

# Specify the command to run the application
CMD ["java", "-jar", "/app/kafka-streams-app.jar"]

