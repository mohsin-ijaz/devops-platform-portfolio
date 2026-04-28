#!/bin/bash
################################################################################
# Terraform Plan Script
# Usage: ./tf-plan.sh <environment>
# Example: ./tf-plan.sh uat
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

echo -e "${GREEN}Running Terraform plan for environment: ${ENV}${NC}"
echo "Working directory: $WORKING_DIR"
echo ""

cd "$WORKING_DIR"

# Create plan output directory
PLAN_DIR="$PROJECT_ROOT/.terraform-plans"
mkdir -p "$PLAN_DIR"

PLAN_FILE="$PLAN_DIR/${ENV}.tfplan"

# Run terraform plan
echo -e "${YELLOW}Generating plan...${NC}"
terraform plan $VAR_FILES -out="$PLAN_FILE"

echo ""
echo -e "${GREEN}Plan saved to: ${PLAN_FILE}${NC}"
echo ""
echo "To apply this plan, run:"
echo "  terraform apply \"$PLAN_FILE\""
