#!/bin/bash
################################################################################
# Terraform Apply Script
# Usage: ./tf-apply.sh <environment> [--auto-approve]
# Example: ./tf-apply.sh uat
################################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

AUTO_APPROVE=""

usage() {
    echo "Usage: $0 <environment> [--auto-approve]"
    echo "Environments: network, uat, prod"
    exit 1
}

if [[ $# -lt 1 ]]; then
    usage
fi

ENV="$1"
shift

# Parse additional arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --auto-approve)
            AUTO_APPROVE="-auto-approve"
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            usage
            ;;
    esac
done

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

# Check for existing plan
PLAN_DIR="$PROJECT_ROOT/.terraform-plans"
PLAN_FILE="$PLAN_DIR/${ENV}.tfplan"

echo -e "${GREEN}Running Terraform apply for environment: ${ENV}${NC}"
echo "Working directory: $WORKING_DIR"
echo ""

cd "$WORKING_DIR"

if [[ -f "$PLAN_FILE" ]]; then
    echo -e "${YELLOW}Found existing plan file: ${PLAN_FILE}${NC}"
    echo ""

    # Apply from plan file
    terraform apply $AUTO_APPROVE "$PLAN_FILE"

    # Remove plan file after successful apply
    rm -f "$PLAN_FILE"
else
    echo -e "${YELLOW}No plan file found, running plan and apply...${NC}"
    echo ""

    # Run plan and apply
    terraform apply $VAR_FILES $AUTO_APPROVE
fi

echo ""
echo -e "${GREEN}Terraform apply completed for ${ENV}${NC}"
