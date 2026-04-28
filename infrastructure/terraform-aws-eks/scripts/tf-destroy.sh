#!/bin/bash
################################################################################
# Terraform Destroy Script
# Usage: ./tf-destroy.sh <environment>
# Example: ./tf-destroy.sh uat
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
    exit 1
}

if [[ $# -ne 1 ]]; then
    usage
fi

ENV="$1"

# Block production destroy without explicit confirmation
if [[ "$ENV" == "prod" ]]; then
    echo -e "${RED}WARNING: You are about to destroy PRODUCTION infrastructure!${NC}"
    echo ""
    read -p "Type 'destroy-production' to confirm: " CONFIRM
    if [[ "$CONFIRM" != "destroy-production" ]]; then
        echo "Aborted."
        exit 1
    fi
fi

case "$ENV" in
    network)
        WORKING_DIR="$PROJECT_ROOT/live/network"
        VAR_FILES="-var-file=$PROJECT_ROOT/live/network/terraform.tfvars"
        ;;
    uat|prod)
        WORKING_DIR="$PROJECT_ROOT/live/workload"
        VAR_FILES="-var-file=$PROJECT_ROOT/environments/_common.tfvars -var-file=$PROJECT_ROOT/environments/${ENV}.tfvars"
        ;;
    *)
        echo -e "${RED}Error: Unknown environment '$ENV'${NC}"
        usage
        ;;
esac

echo -e "${RED}Running Terraform destroy for environment: ${ENV}${NC}"
echo "Working directory: $WORKING_DIR"
echo ""

cd "$WORKING_DIR"

terraform destroy $VAR_FILES

echo ""
echo -e "${GREEN}Terraform destroy completed for ${ENV}${NC}"
