FROM maven:3.9-eclipse-temurin-11 AS build
WORKDIR /app
COPY pom.xml .
RUN mvn dependency:go-offline

COPY src ./src
RUN mvn package -DskipTests

FROM gcr.io/dataflow-templates-base/java11-template-launcher-base
ENV FLEX_TEMPLATE_JAVA_MAIN_CLASS="com.gcp.pipeline.segment.transform.MainframeSegmentPipeline"
ENV FLEX_TEMPLATE_JAVA_CLASSPATH="/app/mainframe-segment-transform-java.jar"

COPY --from=build /app/target/mainframe-segment-transform-java-1.0-SNAPSHOT.jar /app/mainframe-segment-transform-java.jar
