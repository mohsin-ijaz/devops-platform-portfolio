#!/bin/bash
# Kafka Metrics Query Helper
# Usage: ./query-kafka-metrics.sh [metric_name]

GRAFANA_URL="https://monitoring-dev.acme.com"
API_KEY="<GRAFANA_SERVICE_ACCOUNT_TOKEN>"
PROMETHEUS_UID="prometheus"

# Function to query Prometheus
query_prometheus() {
    local query="$1"
    local time_range="${2:-now-6h}"

    echo "Querying: $query"
    echo "Time range: $time_range"
    echo ""

    curl -s -G \
        -H "Authorization: Bearer $API_KEY" \
        --data-urlencode "query=$query" \
        "${GRAFANA_URL}/api/datasources/proxy/uid/${PROMETHEUS_UID}/api/v1/query" \
        | python3 -m json.tool
}

# Predefined queries
case "${1:-help}" in
    consumer-lag)
        echo "=== Kafka Consumer Lag ==="
        query_prometheus 'kafka_consumergroup_lag{topic!=""}'
        ;;

    under-replicated)
        echo "=== Under-Replicated Partitions ==="
        query_prometheus 'kafka_server_replicamanager_underreplicatedpartitions'
        ;;

    offline-partitions)
        echo "=== Offline Partitions ==="
        query_prometheus 'kafka_controller_kafkacontroller_offlinepartitionscount'
        ;;

    active-brokers)
        echo "=== Active Brokers ==="
        query_prometheus 'count(up{job=~".*kafka.*"})'
        ;;

    isr-shrinks)
        echo "=== ISR Shrinks (Rate) ==="
        query_prometheus 'rate(kafka_server_replicamanager_isrshrinkspersec[5m])'
        ;;

    consumer-groups)
        echo "=== All Consumer Groups ==="
        query_prometheus 'count by (consumergroup) (kafka_consumergroup_lag)'
        ;;

    custom)
        if [ -z "$2" ]; then
            echo "Usage: $0 custom 'your_prometheus_query'"
            exit 1
        fi
        query_prometheus "$2"
        ;;

    help|*)
        echo "Kafka Metrics Query Helper"
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  consumer-lag        - Show consumer lag for all topics"
        echo "  under-replicated    - Show under-replicated partitions"
        echo "  offline-partitions  - Show offline partitions count"
        echo "  active-brokers      - Show number of active brokers"
        echo "  isr-shrinks         - Show ISR shrink rate"
        echo "  consumer-groups     - List all consumer groups"
        echo "  custom 'query'      - Run custom Prometheus query"
        echo ""
        echo "Examples:"
        echo "  $0 consumer-lag"
        echo "  $0 custom 'kafka_server_replicamanager_leadercount'"
        ;;
esac
