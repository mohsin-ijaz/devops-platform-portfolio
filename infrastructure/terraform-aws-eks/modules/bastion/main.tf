# Bastion Module

# AMI - Ubuntu 24.04 LTS

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

# IAM Role

resource "aws_iam_role" "bastion" {
  name = "${var.name}-bastion-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "bastion_ssm" {
  role       = aws_iam_role.bastion.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy_attachment" "bastion_cloudwatch" {
  role       = aws_iam_role.bastion.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

# EKS access policy
resource "aws_iam_role_policy" "bastion_eks" {
  name = "eks-full-access"
  role = aws_iam_role.bastion.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "eks:*"
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_instance_profile" "bastion" {
  name = "${var.name}-bastion-profile"
  role = aws_iam_role.bastion.name

  tags = var.tags
}

# EC2 Instance

resource "aws_instance" "bastion" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type
  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = var.security_group_ids
  iam_instance_profile        = aws_iam_instance_profile.bastion.name
  associate_public_ip_address = var.associate_public_ip
  monitoring                  = var.enable_monitoring

  # SSM only, no SSH
  key_name = null

  root_block_device {
    volume_size           = var.root_volume_size
    volume_type           = "gp3"
    encrypted             = true
    delete_on_termination = true

    tags = merge(var.tags, {
      Name = "${var.name}-bastion-root"
    })
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required" # IMDSv2
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "enabled"
  }

  user_data = base64encode(<<-EOF
#!/bin/bash
set -e

# Install SSM agent FIRST
snap install amazon-ssm-agent --classic
snap start amazon-ssm-agent

# Install packages
apt-get update -qq
apt-get install -y -qq vim htop wget curl jq unzip git tree

# Install kubectl
curl -sO https://s3.us-west-2.amazonaws.com/amazon-eks/1.31.0/2024-09-12/bin/linux/amd64/kubectl
chmod +x kubectl && mv kubectl /usr/local/bin/

# Install AWS CLI v2
curl -s "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip -q awscliv2.zip && ./aws/install && rm -rf awscliv2.zip aws

# Install Helm
curl -s https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Configure kubectl for EKS
mkdir -p /root/.kube
/usr/local/bin/aws eks update-kubeconfig --region ${var.aws_region} --name ${var.eks_cluster_name} --kubeconfig /root/.kube/config 2>/dev/null || true

# Setup ubuntu user
mkdir -p /home/ubuntu/.kube
cp /root/.kube/config /home/ubuntu/.kube/config 2>/dev/null || true
chown -R ubuntu:ubuntu /home/ubuntu/.kube

# Setup ssm-user
id ssm-user &>/dev/null || useradd -m -s /bin/bash ssm-user
mkdir -p /home/ssm-user/.kube /home/ssm-user/Downloads
cp /root/.kube/config /home/ssm-user/.kube/config 2>/dev/null || true
chown -R ssm-user:ssm-user /home/ssm-user

# Add aliases
cat >> /etc/profile.d/kubectl.sh << 'ALIASES'
export PATH=$PATH:/usr/local/bin
alias k='kubectl'
alias kgp='kubectl get pods'
alias kgn='kubectl get nodes'
alias kga='kubectl get all'
alias ll='ls -la'
ALIASES

echo "Base setup complete" > /var/log/bastion-setup.log

# Create GitLab Runner installation script
cat > /opt/install-gitlab-runner.sh << 'SCRIPT'
#!/bin/bash
LOG="/var/log/gitlab-runner-install.log"
exec > >(tee -a $LOG) 2>&1

echo "$(date): Starting GitLab Runner installation"

# Variables (replaced by Terraform)
REGION="__REGION__"
CLUSTER_NAME="__CLUSTER_NAME__"
GITLAB_URL="__GITLAB_URL__"
GITLAB_TOKEN="__GITLAB_TOKEN__"
RUNNER_TAG="__RUNNER_TAG__"

# Wait for EKS cluster (max 30 minutes)
echo "$(date): Waiting for EKS cluster..."
MAX_ATTEMPTS=60
ATTEMPT=0
while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
  ATTEMPT=$((ATTEMPT + 1))
  echo "$(date): Attempt $ATTEMPT - Checking EKS cluster..."

  /usr/local/bin/aws eks update-kubeconfig --region $REGION --name $CLUSTER_NAME --kubeconfig /root/.kube/config 2>&1

  if kubectl get nodes 2>&1; then
    echo "$(date): EKS cluster is ready!"
    break
  fi

  echo "$(date): Cluster not ready, waiting 30s..."
  sleep 30
done

if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
  echo "$(date): ERROR - Timeout waiting for EKS cluster"
  exit 1
fi

# Copy kubeconfig for other users
cp /root/.kube/config /home/ubuntu/.kube/config 2>/dev/null || true
cp /root/.kube/config /home/ssm-user/.kube/config 2>/dev/null || true
chown -R ubuntu:ubuntu /home/ubuntu/.kube 2>/dev/null || true
chown -R ssm-user:ssm-user /home/ssm-user/.kube 2>/dev/null || true

# Add Helm repo
echo "$(date): Adding GitLab Helm repo..."
helm repo add gitlab https://charts.gitlab.io
helm repo update

# Install GitLab Runner
echo "$(date): Installing GitLab Runner..."
kubectl create namespace gitlab-runner --dry-run=client -o yaml | kubectl apply -f -

# Create values file for GitLab Runner with tags
cat > /tmp/gitlab-runner-values.yaml << 'RUNNER_VALUES'
gitlabUrl: __GITLAB_URL__
runnerToken: __GITLAB_TOKEN__
rbac:
  create: true
serviceAccount:
  create: true
runners:
  privileged: true
  config: |
    [[runners]]
      tags = ["__RUNNER_TAG__"]
      [runners.kubernetes]
        image = "alpine"
        privileged = true
        namespace = "gitlab-runner"
RUNNER_VALUES

sed -i "s|__GITLAB_URL__|$GITLAB_URL|g" /tmp/gitlab-runner-values.yaml
sed -i "s|__GITLAB_TOKEN__|$GITLAB_TOKEN|g" /tmp/gitlab-runner-values.yaml
sed -i "s|__RUNNER_TAG__|$RUNNER_TAG|g" /tmp/gitlab-runner-values.yaml

helm upgrade --install gitlab-runner gitlab/gitlab-runner \
  --namespace gitlab-runner \
  -f /tmp/gitlab-runner-values.yaml \
  --wait --timeout 5m

echo "$(date): GitLab Runner installation complete!"
echo "done" > /var/log/gitlab-runner-complete
SCRIPT

# Replace placeholders
sed -i "s|__REGION__|${var.aws_region}|g" /opt/install-gitlab-runner.sh
sed -i "s|__CLUSTER_NAME__|${var.eks_cluster_name}|g" /opt/install-gitlab-runner.sh
sed -i "s|__GITLAB_URL__|${var.gitlab_runner_url}|g" /opt/install-gitlab-runner.sh
sed -i "s|__GITLAB_TOKEN__|${var.gitlab_runner_token}|g" /opt/install-gitlab-runner.sh
sed -i "s|__RUNNER_TAG__|${var.gitlab_runner_tag}|g" /opt/install-gitlab-runner.sh

chmod +x /opt/install-gitlab-runner.sh

# Run in background
nohup /opt/install-gitlab-runner.sh &

echo "GitLab Runner installation started in background" >> /var/log/bastion-setup.log
EOF
  )

  tags = merge(var.tags, {
    Name = "${var.name}-bastion"
  })

  lifecycle {
    ignore_changes = [ami]
  }
}
