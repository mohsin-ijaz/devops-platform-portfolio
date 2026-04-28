# Security Groups Module

# EKS Cluster Security Group

resource "aws_security_group" "eks_cluster" {
  name        = "${var.name}-eks-cluster-sg"
  description = "Security group for EKS cluster control plane"
  vpc_id      = var.vpc_id

  tags = merge(var.tags, {
    Name = "${var.name}-eks-cluster-sg"
  })

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "eks_cluster_ingress_nodes" {
  description              = "Allow nodes to communicate with cluster API"
  type                     = "ingress"
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.eks_nodes.id
  security_group_id        = aws_security_group.eks_cluster.id
}

resource "aws_security_group_rule" "eks_cluster_ingress_bastion" {
  description              = "Allow bastion to communicate with cluster API"
  type                     = "ingress"
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.bastion.id
  security_group_id        = aws_security_group.eks_cluster.id
}

resource "aws_security_group_rule" "eks_cluster_ingress_argocd" {
  count = length(var.argocd_source_cidrs) > 0 ? 1 : 0

  description       = "Allow ArgoCD from other VPCs to access cluster API"
  type              = "ingress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = var.argocd_source_cidrs
  security_group_id = aws_security_group.eks_cluster.id
}

resource "aws_security_group_rule" "eks_cluster_egress_all" {
  description       = "Allow all outbound traffic"
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.eks_cluster.id
}

# EKS Node Security Group

resource "aws_security_group" "eks_nodes" {
  name        = "${var.name}-eks-nodes-sg"
  description = "Security group for EKS worker nodes"
  vpc_id      = var.vpc_id

  tags = merge(var.tags, {
    Name                                        = "${var.name}-eks-nodes-sg"
    "kubernetes.io/cluster/${var.name}-eks"     = "owned"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# Node to node communication
resource "aws_security_group_rule" "eks_nodes_ingress_self" {
  description              = "Allow nodes to communicate with each other"
  type                     = "ingress"
  from_port                = 0
  to_port                  = 0
  protocol                 = "-1"
  source_security_group_id = aws_security_group.eks_nodes.id
  security_group_id        = aws_security_group.eks_nodes.id
}

# Control plane to nodes (HTTPS)
resource "aws_security_group_rule" "eks_nodes_ingress_cluster_https" {
  description              = "Allow control plane to communicate with nodes (HTTPS)"
  type                     = "ingress"
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.eks_cluster.id
  security_group_id        = aws_security_group.eks_nodes.id
}

# Control plane to nodes (high ports)
resource "aws_security_group_rule" "eks_nodes_ingress_cluster_high_ports" {
  description              = "Allow control plane to communicate with nodes (high ports)"
  type                     = "ingress"
  from_port                = 1025
  to_port                  = 65535
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.eks_cluster.id
  security_group_id        = aws_security_group.eks_nodes.id
}

# Kubelet API
resource "aws_security_group_rule" "eks_nodes_ingress_kubelet" {
  description              = "Allow control plane to access kubelet API"
  type                     = "ingress"
  from_port                = 10250
  to_port                  = 10250
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.eks_cluster.id
  security_group_id        = aws_security_group.eks_nodes.id
}

# ALB health checks
resource "aws_security_group_rule" "eks_nodes_ingress_alb_http" {
  description       = "Allow ALB health checks (HTTP)"
  type              = "ingress"
  from_port         = 80
  to_port           = 80
  protocol          = "tcp"
  cidr_blocks       = [var.vpc_cidr]
  security_group_id = aws_security_group.eks_nodes.id
}

resource "aws_security_group_rule" "eks_nodes_ingress_alb_https" {
  description       = "Allow ALB health checks (HTTPS)"
  type              = "ingress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = [var.vpc_cidr]
  security_group_id = aws_security_group.eks_nodes.id
}

# NodePort range for services
resource "aws_security_group_rule" "eks_nodes_ingress_nodeports" {
  description       = "Allow NodePort services from VPC"
  type              = "ingress"
  from_port         = 30000
  to_port           = 32767
  protocol          = "tcp"
  cidr_blocks       = [var.vpc_cidr]
  security_group_id = aws_security_group.eks_nodes.id
}

# All outbound
resource "aws_security_group_rule" "eks_nodes_egress_all" {
  description       = "Allow all outbound traffic"
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.eks_nodes.id
}

# Bastion Security Group

resource "aws_security_group" "bastion" {
  name        = "${var.name}-bastion-sg"
  description = "Security group for bastion host (SSM access only)"
  vpc_id      = var.vpc_id

  tags = merge(var.tags, {
    Name = "${var.name}-bastion-sg"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# Outbound to VPC
resource "aws_security_group_rule" "bastion_egress_https_vpc" {
  description       = "Allow HTTPS to VPC (SSM endpoints)"
  type              = "egress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = [var.vpc_cidr]
  security_group_id = aws_security_group.bastion.id
}

# Outbound to EKS cluster
resource "aws_security_group_rule" "bastion_egress_eks" {
  description              = "Allow HTTPS to EKS cluster"
  type                     = "egress"
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.eks_cluster.id
  security_group_id        = aws_security_group.bastion.id
}

# Outbound to internet
resource "aws_security_group_rule" "bastion_egress_internet" {
  description       = "Allow outbound internet access via NAT Gateway"
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.bastion.id
}

# Internal ALB Security Group

resource "aws_security_group" "alb_internal" {
  name        = "${var.name}-alb-internal-sg"
  description = "Security group for internal ALB"
  vpc_id      = var.vpc_id

  tags = merge(var.tags, {
    Name = "${var.name}-alb-internal-sg"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# HTTPS from VPC
resource "aws_security_group_rule" "alb_internal_ingress_https_vpc" {
  description       = "Allow HTTPS from VPC"
  type              = "ingress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = [var.vpc_cidr]
  security_group_id = aws_security_group.alb_internal.id
}

# HTTPS from on-premises
resource "aws_security_group_rule" "alb_internal_ingress_https_onprem" {
  count = length(var.onprem_cidrs) > 0 ? 1 : 0

  description       = "Allow HTTPS from on-premises"
  type              = "ingress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = var.onprem_cidrs
  security_group_id = aws_security_group.alb_internal.id
}

# HTTP from VPC (redirect to HTTPS)
resource "aws_security_group_rule" "alb_internal_ingress_http_vpc" {
  description       = "Allow HTTP from VPC (redirect to HTTPS)"
  type              = "ingress"
  from_port         = 80
  to_port           = 80
  protocol          = "tcp"
  cidr_blocks       = [var.vpc_cidr]
  security_group_id = aws_security_group.alb_internal.id
}

# HTTP from on-premises (redirect to HTTPS)
resource "aws_security_group_rule" "alb_internal_ingress_http_onprem" {
  count = length(var.onprem_cidrs) > 0 ? 1 : 0

  description       = "Allow HTTP from on-premises (redirect to HTTPS)"
  type              = "ingress"
  from_port         = 80
  to_port           = 80
  protocol          = "tcp"
  cidr_blocks       = var.onprem_cidrs
  security_group_id = aws_security_group.alb_internal.id
}

# Outbound to EKS nodes
resource "aws_security_group_rule" "alb_internal_egress_nodes" {
  description              = "Allow traffic to EKS nodes"
  type                     = "egress"
  from_port                = 0
  to_port                  = 0
  protocol                 = "-1"
  source_security_group_id = aws_security_group.eks_nodes.id
  security_group_id        = aws_security_group.alb_internal.id
}

# Database Security Group

resource "aws_security_group" "database" {
  name        = "${var.name}-database-sg"
  description = "Security group for RDS databases"
  vpc_id      = var.vpc_id

  tags = merge(var.tags, {
    Name = "${var.name}-database-sg"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# MySQL from EKS nodes
resource "aws_security_group_rule" "database_ingress_mysql" {
  description              = "Allow MySQL from EKS nodes"
  type                     = "ingress"
  from_port                = 3306
  to_port                  = 3306
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.eks_nodes.id
  security_group_id        = aws_security_group.database.id
}

# PostgreSQL from EKS nodes
resource "aws_security_group_rule" "database_ingress_postgresql" {
  description              = "Allow PostgreSQL from EKS nodes"
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.eks_nodes.id
  security_group_id        = aws_security_group.database.id
}

# MySQL from Bastion (for debugging)
resource "aws_security_group_rule" "database_ingress_mysql_bastion" {
  description              = "Allow MySQL from Bastion"
  type                     = "ingress"
  from_port                = 3306
  to_port                  = 3306
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.bastion.id
  security_group_id        = aws_security_group.database.id
}

# PostgreSQL from Bastion (for debugging)
resource "aws_security_group_rule" "database_ingress_postgresql_bastion" {
  description              = "Allow PostgreSQL from Bastion"
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.bastion.id
  security_group_id        = aws_security_group.database.id
}

# No outbound rules for database
