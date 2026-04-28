FROM debian:buster-20210111-slim AS builder

LABEL maintainer="Acme Platform Team <devops@<GCP_PROJECT_DOMAIN>>"

RUN apt-get update && apt-get install -y wget

RUN wget https://github.com/percona/proxysql_exporter/releases/download/v1.1.0/proxysql_exporter-1.1.0.linux-amd64.tar.gz -O proxysql_exporter-1.1.0.linux-amd64.tar.gz

RUN tar zxvf proxysql_exporter-1.1.0.linux-amd64.tar.gz && cd proxysql_exporter-1.1.0.linux-amd64


FROM debian:buster-20210111-slim 

LABEL maintainer="Acme Platform Team <devops@<GCP_PROJECT_DOMAIN>>"

COPY --from=builder /proxysql_exporter-1.1.0.linux-amd64/proxysql_exporter .

ENTRYPOINT [ "./proxysql_exporter" ]

