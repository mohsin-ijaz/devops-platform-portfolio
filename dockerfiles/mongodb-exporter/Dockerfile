FROM alpine:3.7

LABEL maintainer="Acme Platform Team <devops@<GCP_PROJECT_DOMAIN>>"

RUN mkdir ./mongodb-exporter && \
    cd mongodb-exporter && \
    wget https://github.com/percona/mongodb_exporter/releases/download/v0.10.0/mongodb_exporter-0.10.0.linux-amd64.tar.gz && \
    tar xvzf mongodb_exporter-0.10.0.linux-amd64.tar.gz && \
    rm mongodb_exporter-0.10.0.linux-amd64.tar.gz CHANGELOG.md LICENSE README.md

EXPOSE 9216

CMD ["/mongodb-exporter/mongodb_exporter"]