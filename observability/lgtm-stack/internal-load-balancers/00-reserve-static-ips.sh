#!/bin/bash
# Reserve static internal IPs for LGTM Internal Load Balancers

PROJECT="<GCP_MGMT_PROJECT>"
REGION="<GCP_REGION>"
SUBNET="<GCP_SUBNET>"

echo "Reserving static IPs for LGTM Internal Load Balancers..."

# Reserve IP for Mimir
echo "1. Creating static IP for Mimir ILB..."
gcloud compute addresses create mimir-ilb-ip \
  --region=$REGION \
  --subnet=$SUBNET \
  --project=$PROJECT \
  --purpose=SHARED_LOADBALANCER_VIP

# Reserve IP for Loki
echo "2. Creating static IP for Loki ILB..."
gcloud compute addresses create loki-ilb-ip \
  --region=$REGION \
  --subnet=$SUBNET \
  --project=$PROJECT \
  --purpose=SHARED_LOADBALANCER_VIP

# Reserve IP for Tempo
echo "3. Creating static IP for Tempo ILB..."
gcloud compute addresses create tempo-ilb-ip \
  --region=$REGION \
  --subnet=$SUBNET \
  --project=$PROJECT \
  --purpose=SHARED_LOADBALANCER_VIP

echo ""
echo "Static IPs created! Getting IP addresses..."
echo ""

# Get the reserved IPs
MIMIR_IP=$(gcloud compute addresses describe mimir-ilb-ip --region=$REGION --project=$PROJECT --format="value(address)")
LOKI_IP=$(gcloud compute addresses describe loki-ilb-ip --region=$REGION --project=$PROJECT --format="value(address)")
TEMPO_IP=$(gcloud compute addresses describe tempo-ilb-ip --region=$REGION --project=$PROJECT --format="value(address)")

echo "Reserved IPs:"
echo "  Mimir:  $MIMIR_IP"
echo "  Loki:   $LOKI_IP"
echo "  Tempo:  $TEMPO_IP"
echo ""
echo "Next: Update the *-ilb.yaml files with these IPs and apply them"