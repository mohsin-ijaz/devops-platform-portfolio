#!/bin/bash

# Ensure required arguments are provided
if [ $# -lt 2 ]; then
    echo "Usage: $0 <EKS_CLUSTER_NAME> <MFA_TOKEN_CODE>"
    exit 1
fi

# Variables
ROLE_ARN="arn:aws:iam::<AWS_ACCOUNT_ID>:role/eks-suser-role"
SESSION_NAME="EKSDeploymentDeleteSession"
MFA_ARN="arn:aws:iam::<AWS_ACCOUNT_ID>:mfa/aws-ph"
REGION="<AWS_REGION>"
EKS_CLUSTER="$1"
MFA_TOKEN="$2"

# Assume the role with MFA
echo "Assuming role: $ROLE_ARN..."
JSON=$(aws sts assume-role --role-arn "$ROLE_ARN" \
                           --role-session-name "$SESSION_NAME" \
                           --serial-number "$MFA_ARN" \
                           --token-code "$MFA_TOKEN" \
                           --output json)

# Check if the command was successful
if [ $? -ne 0 ]; then
    echo "Error assuming role. Check permissions, AWS credentials, and MFA token."
    exit 1
fi

# Extract credentials using jq and remove quotes
export AWS_ACCESS_KEY_ID=$(echo $JSON | jq -r '.Credentials.AccessKeyId')
export AWS_SECRET_ACCESS_KEY=$(echo $JSON | jq -r '.Credentials.SecretAccessKey')
export AWS_SESSION_TOKEN=$(echo $JSON | jq -r '.Credentials.SessionToken')

# Confirm role assumption
echo "Successfully assumed role: $ROLE_ARN"
aws sts get-caller-identity

# Update kubeconfig for the specified EKS cluster
echo "Updating kubeconfig for EKS cluster: $EKS_CLUSTER..."
aws eks --region "$REGION" update-kubeconfig --name "$EKS_CLUSTER"

# Confirm kubeconfig update
if [ $? -eq 0 ]; then
    echo "Kubeconfig updated successfully for cluster: $EKS_CLUSTER"
else
    echo "Failed to update kubeconfig."
    exit 1
fi
