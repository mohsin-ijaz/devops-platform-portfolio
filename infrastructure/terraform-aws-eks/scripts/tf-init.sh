#!/bin/bash
################################################################################
# Terraform Init Script
# Usage: ./tf-init.sh <environment>
# Example: ./tf-init.sh uat
################################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

usage() {
    echo "Usage: $0 <environment>"
    echo "Environments: network, uat, prod"
    echo ""
    echo "Examples:"
    echo "  $0 network    # Initialize network account"
    echo "  $0 uat        # Initialize UAT workload account"
    echo "  $0 prod       # Initialize production workload account"
    exit 1
}

if [[ $# -ne 1 ]]; then
    usage
fi

ENV="$1"

case "$ENV" in
    network)
        WORKING_DIR="$PROJECT_ROOT/live/network"
        BACKEND_CONFIG=""
        ;;
    uat|prod)
        WORKING_DIR="$PROJECT_ROOT/live/workload"
        BACKEND_CONFIG="-backend-config=backend-${ENV}.hcl"
        ;;
    *)
        echo -e "${RED}Error: Unknown environment '$ENV'${NC}"
        usage
        ;;
esac

echo -e "${GREEN}Initializing Terraform for environment: ${ENV}${NC}"
echo "Working directory: $WORKING_DIR"
echo ""

cd "$WORKING_DIR"

# Run terraform init
if [[ -n "$BACKEND_CONFIG" ]]; then
    echo -e "${YELLOW}Using backend config: ${BACKEND_CONFIG}${NC}"
    terraform init -reconfigure $BACKEND_CONFIG
else
    terraform init -reconfigure
fi

echo ""
echo -e "${GREEN}Terraform initialized successfully for ${ENV}${NC}"
