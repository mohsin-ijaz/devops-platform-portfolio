FROM debezium/connect:1.9
LABEL maintainer="Acme Platform Team <<MAINTAINER_EMAIL>>"
ENV KAFKA_CONNECT_CASSANDRA_DIR=$KAFKA_CONNECT_PLUGINS_DIR/kafka-connect-cassandra
ENV KAFKA_CONNECT_JDBC_DIR=$KAFKA_CONNECT_PLUGINS_DIR/kafka-connect-jdbc

RUN mkdir $KAFKA_CONNECT_CASSANDRA_DIR && \
    cd $KAFKA_CONNECT_CASSANDRA_DIR && \
    curl -L https://github.com/lensesio/stream-reactor/releases/download/3.0.1/kafka-connect-cassandra-3.0.1-2.5.0-all.tar.gz > kafka-connect-cassandra.tar.gz && \
    tar -xvf kafka-connect-cassandra.tar.gz && \
    rm kafka-connect-cassandra.tar.gz LICENSE

RUN mkdir $KAFKA_CONNECT_JDBC_DIR
COPY kafka-connect-jdbc-10.3.1/* $KAFKA_CONNECT_JDBC_DIR/