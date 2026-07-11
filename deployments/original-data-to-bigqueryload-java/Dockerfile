# Runtime image for the ingestion Beam pipeline (Cloud Run Job, Tier-3a demo).
# Expects the shaded fat jar to be built first:
#   mvn -f deployments/original-data-to-bigqueryload-java/pom.xml package -DskipTests
# (The deployment depends on unpublished Culvert 0.1.0 libraries, so the jar is
# built in the reactor context, not inside this image.)
FROM eclipse-temurin:21-jre
WORKDIR /app
COPY target/original-data-to-bigqueryload-java-0.1.0.jar /app/app.jar
# Args (runner/cloud + ingestion request) are supplied at Cloud Run Job execution.
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
