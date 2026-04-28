#!/bin/bash
#
# Mimir Rules Sync Script
# Syncs recording rules from mimir-rules-all.yaml to Mimir ruler API
#
# Prerequisites:
#   - kubectl access to the cluster
#   - yq (https://github.com/mikefarah/yq)
#   - Port-forward must be active OR run from within cluster
#
# Usage:
#   ./sync-rules.sh [--port-forward]
#
# Options:
#   --port-forward    Automatically set up port-forward (requires kubectl)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RULES_FILE="${SCRIPT_DIR}/mimir-rules-all.yaml"
MIMIR_RULER_URL="${MIMIR_RULER_URL:-http://localhost:8082}"
TENANT_ID="${MIMIR_TENANT_ID:-<YOUR_TENANT_ID>}"
NAMESPACE="${K8S_NAMESPACE:-lgtm-stack}"
SERVICE="${MIMIR_RULER_SERVICE:-mimir-prod-ruler}"
PORT="${MIMIR_RULER_PORT:-8080}"
LOCAL_PORT="${LOCAL_PORT:-8082}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check dependencies
check_deps() {
    if ! command -v yq &> /dev/null; then
        log_error "yq is required but not installed. Install with: brew install yq"
        exit 1
    fi
    if ! command -v curl &> /dev/null; then
        log_error "curl is required but not installed."
        exit 1
    fi
}

# Set up port-forward
setup_port_forward() {
    log_info "Setting up port-forward to ${SERVICE} in ${NAMESPACE}..."
    kubectl port-forward -n "${NAMESPACE}" "svc/${SERVICE}" "${LOCAL_PORT}:${PORT}" &
    PF_PID=$!
    sleep 3
    
    # Verify port-forward is working
    if ! kill -0 "$PF_PID" 2>/dev/null; then
        log_error "Port-forward failed to start"
        exit 1
    fi
    
    trap "kill $PF_PID 2>/dev/null || true" EXIT
    log_info "Port-forward established (PID: $PF_PID)"
}

# Get list of rule namespaces from Mimir
get_existing_namespaces() {
    curl -s -X GET \
        -H "X-Scope-OrgID: ${TENANT_ID}" \
        "${MIMIR_RULER_URL}/prometheus/config/v1/rules" | \
        yq -r 'keys | .[]' 2>/dev/null || echo ""
}

# Deploy a single rule namespace
deploy_rule_namespace() {
    local namespace="$1"
    local groups_yaml="$2"
    
    log_info "Deploying rules to namespace: ${namespace}"
    
    # Create the Prometheus-format rules YAML
    local rules_yaml
    rules_yaml=$(echo "$groups_yaml" | yq -y '{groups: .}')
    
    local response
    local http_code
    
    # Use a temp file to capture both response body and status code
    response=$(curl -s -w "\n%{http_code}" -X POST \
        -H "X-Scope-OrgID: ${TENANT_ID}" \
        -H "Content-Type: application/yaml" \
        --data-raw "$rules_yaml" \
        "${MIMIR_RULER_URL}/prometheus/config/v1/rules/${namespace}")
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    if [[ "$http_code" == "202" ]]; then
        log_info "  ✓ Successfully deployed ${namespace}"
        return 0
    else
        log_error "  ✗ Failed to deploy ${namespace} (HTTP ${http_code})"
        log_error "  Response: ${body}"
        return 1
    fi
}

# Delete a rule namespace
delete_rule_namespace() {
    local namespace="$1"
    
    log_warn "Deleting rule namespace: ${namespace}"
    
    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE \
        -H "X-Scope-OrgID: ${TENANT_ID}" \
        "${MIMIR_RULER_URL}/prometheus/config/v1/rules/${namespace}")
    
    if [[ "$http_code" == "202" ]]; then
        log_info "  ✓ Deleted ${namespace}"
    else
        log_warn "  ✗ Failed to delete ${namespace} (HTTP ${http_code})"
    fi
}

# Main sync function
sync_rules() {
    log_info "Starting rules sync..."
    log_info "Tenant: ${TENANT_ID}"
    log_info "Rules file: ${RULES_FILE}"
    
    if [[ ! -f "$RULES_FILE" ]]; then
        log_error "Rules file not found: ${RULES_FILE}"
        exit 1
    fi
    
    # Extract tenant rules from the YAML
    local tenant_rules
    tenant_rules=$(yq -r ".namespaces[\"${TENANT_ID}\"]" "$RULES_FILE")
    
    if [[ "$tenant_rules" == "null" || -z "$tenant_rules" ]]; then
        log_error "No rules found for tenant: ${TENANT_ID}"
        exit 1
    fi
    
    # Get namespaces defined in the file
    local file_namespaces
    file_namespaces=$(yq -r ".namespaces[\"${TENANT_ID}\"] | keys | .[]" "$RULES_FILE")
    
    log_info "Found rule namespaces in file:"
    echo "$file_namespaces" | while read -r ns; do
        echo "  - $ns"
    done
    
    # Deploy each namespace
    local failed=0
    while read -r ns; do
        if [[ -z "$ns" ]]; then continue; fi
        
        # Extract groups for this namespace
        local groups
        groups=$(yq -y ".namespaces[\"${TENANT_ID}\"][\"${ns}\"]" "$RULES_FILE")
        
        if ! deploy_rule_namespace "$ns" "$groups"; then
            ((failed++))
        fi
    done <<< "$file_namespaces"
    
    if [[ $failed -gt 0 ]]; then
        log_error "Sync completed with ${failed} failures"
        exit 1
    fi
    
    log_info "Sync completed successfully!"
}

# Verify rules are loaded
verify_rules() {
    log_info "Verifying rules are loaded..."
    
    local rules
    rules=$(curl -s -X GET \
        -H "X-Scope-OrgID: ${TENANT_ID}" \
        "${MIMIR_RULER_URL}/prometheus/config/v1/rules")
    
    log_info "Currently loaded rule namespaces:"
    echo "$rules" | yq -r 'keys | .[]' | while read -r ns; do
        local group_count
        group_count=$(echo "$rules" | yq -r ".[\"$ns\"] | length")
        echo "  - ${ns}: ${group_count} groups"
    done
}

# Parse arguments
SETUP_PORT_FORWARD=false
VERIFY_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --port-forward)
            SETUP_PORT_FORWARD=true
            shift
            ;;
        --verify)
            VERIFY_ONLY=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --port-forward    Set up kubectl port-forward before syncing"
            echo "  --verify          Only verify current rules, don't sync"
            echo "  --help, -h        Show this help message"
            echo ""
            echo "Environment variables:"
            echo "  MIMIR_RULER_URL     Mimir ruler URL (default: http://localhost:8082)"
            echo "  MIMIR_TENANT_ID     Tenant ID (default: <YOUR_TENANT_ID>)"
            echo "  K8S_NAMESPACE       Kubernetes namespace (default: lgtm-stack)"
            echo "  MIMIR_RULER_SERVICE Ruler service name (default: mimir-prod-ruler)"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Main
check_deps

if [[ "$SETUP_PORT_FORWARD" == "true" ]]; then
    setup_port_forward
fi

if [[ "$VERIFY_ONLY" == "true" ]]; then
    verify_rules
else
    sync_rules
    echo ""
    verify_rules
fi
