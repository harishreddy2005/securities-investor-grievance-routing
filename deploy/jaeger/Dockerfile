FROM jaegertracing/jaeger:2.22.0 AS upstream
FROM alpine:3.21.3
COPY --from=upstream /cmd/jaeger/jaeger-linux /usr/local/bin/jaeger
RUN mkdir -p /data && chown 10001:10001 /data
USER 10001
ENTRYPOINT ["/usr/local/bin/jaeger"]
