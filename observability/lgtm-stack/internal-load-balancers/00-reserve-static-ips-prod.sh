#!/bin/bash
# Reserve static internal IPs for LGTM Production Internal Load Balancers

PROJECT="<GCP_MGMT_PROJECT>"
REGION="<GCP_REGION>"
SUBNET="<GCP_SUBNET>"

echo "Reserving static IPs for LGTM PRODUCTION Internal Load Balancers..."

# Reserve IP for Mimir Production
echo "1. Creating static IP for Mimir ILB (Production)..."
gcloud compute addresses create mimir-ilb-ip-prod \
  --region=$REGION \
  --subnet=$SUBNET \
  --project=$PROJECT \
  --purpose=SHARED_LOADBALANCER_VIP

# Reserve IP for Loki Production
echo "2. Creating static IP for Loki ILB (Production)..."
gcloud compute addresses create loki-ilb-ip-prod \
  --region=$REGION \
  --subnet=$SUBNET \
  --project=$PROJECT \
  --purpose=SHARED_LOADBALANCER_VIP

# Reserve IP for Tempo Production
echo "3. Creating static IP for Tempo ILB (Production)..."
gcloud compute addresses create tempo-ilb-ip-prod \
  --region=$REGION \
  --subnet=$SUBNET \
  --project=$PROJECT \
  --purpose=SHARED_LOADBALANCER_VIP

echo ""
echo "Static IPs created! Getting IP addresses..."
echo ""

# Get the reserved IPs
MIMIR_IP=$(gcloud compute addresses describe mimir-ilb-ip-prod --region=$REGION --project=$PROJECT --format="value(address)")
LOKI_IP=$(gcloud compute addresses describe loki-ilb-ip-prod --region=$REGION --project=$PROJECT --format="value(address)")
TEMPO_IP=$(gcloud compute addresses describe tempo-ilb-ip-prod --region=$REGION --project=$PROJECT --format="value(address)")

echo "Reserved Production IPs:"
echo "  Mimir:  $MIMIR_IP"
echo "  Loki:   $LOKI_IP"
echo "  Tempo:  $TEMPO_IP"
echo ""
echo "Next: Deploy the production ILB YAMLs"
