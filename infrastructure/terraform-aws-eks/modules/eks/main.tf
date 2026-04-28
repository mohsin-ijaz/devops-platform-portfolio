# EKS Module

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}
data "aws_region" "current" {}

locals {
  cluster_name = var.name
  account_id   = data.aws_caller_identity.current.account_id
  partition    = data.aws_partition.current.partition
  region       = data.aws_region.current.name
}

# EKS Cluster IAM Role

resource "aws_iam_role" "cluster" {
  name = "${var.name}-cluster-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "eks.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "cluster_policy" {
  policy_arn = "arn:${local.partition}:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.cluster.name
}

resource "aws_iam_role_policy_attachment" "cluster_vpc_resource_controller" {
  policy_arn = "arn:${local.partition}:iam::aws:policy/AmazonEKSVPCResourceController"
  role       = aws_iam_role.cluster.name
}

# EKS Cluster

resource "aws_eks_cluster" "this" {
  name     = local.cluster_name
  version  = var.cluster_version
  role_arn = aws_iam_role.cluster.arn

  vpc_config {
    subnet_ids              = var.subnet_ids
    endpoint_private_access = var.endpoint_private_access
    endpoint_public_access  = var.endpoint_public_access
    security_group_ids      = var.cluster_security_group_id != null ? [var.cluster_security_group_id] : null
  }

  kubernetes_network_config {
    service_ipv4_cidr = var.service_cidr
    ip_family         = "ipv4"
  }

  # Access config (replaces aws-auth)
  access_config {
    authentication_mode                         = var.authentication_mode
    bootstrap_cluster_creator_admin_permissions = true
  }

  depends_on = [
    aws_iam_role_policy_attachment.cluster_policy,
    aws_iam_role_policy_attachment.cluster_vpc_resource_controller,
  ]

  tags = merge(var.tags, {
    Name = local.cluster_name
  })
}

# EKS Access Entries (use count instead of for_each to handle unknown ARNs at plan time)

resource "aws_eks_access_entry" "admin" {
  count = length(var.cluster_admin_arns)

  cluster_name  = aws_eks_cluster.this.name
  principal_arn = var.cluster_admin_arns[count.index]
  type          = "STANDARD"

  tags = var.tags
}

resource "aws_eks_access_policy_association" "admin" {
  count = length(var.cluster_admin_arns)

  cluster_name  = aws_eks_cluster.this.name
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
  principal_arn = var.cluster_admin_arns[count.index]

  access_scope {
    type = "cluster"
  }

  depends_on = [aws_eks_access_entry.admin]
}

# OIDC Provider for IRSA
# Note: AWS EKS OIDC no longer requires fetching the TLS certificate thumbprint.
# AWS validates the certificate chain internally. Using a placeholder thumbprint.
# See: https://docs.aws.amazon.com/eks/latest/userguide/enable-iam-roles-for-service-accounts.html

resource "aws_iam_openid_connect_provider" "cluster" {
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["9e99a48a9960b14926bb7f3b02e22da2b0ab7280"]
  url             = aws_eks_cluster.this.identity[0].oidc[0].issuer

  tags = merge(var.tags, {
    Name = "${local.cluster_name}-oidc"
  })
}

# Node Group IAM Role

resource "aws_iam_role" "node" {
  name = "${var.name}-node-role"

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

resource "aws_iam_role_policy_attachment" "node_worker_policy" {
  policy_arn = "arn:${local.partition}:iam::aws:policy/AmazonEKSWorkerNodePolicy"
  role       = aws_iam_role.node.name
}

resource "aws_iam_role_policy_attachment" "node_cni_policy" {
  policy_arn = "arn:${local.partition}:iam::aws:policy/AmazonEKS_CNI_Policy"
  role       = aws_iam_role.node.name
}

resource "aws_iam_role_policy_attachment" "node_ecr_policy" {
  policy_arn = "arn:${local.partition}:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
  role       = aws_iam_role.node.name
}

resource "aws_iam_role_policy_attachment" "node_ssm_policy" {
  policy_arn = "arn:${local.partition}:iam::aws:policy/AmazonSSMManagedInstanceCore"
  role       = aws_iam_role.node.name
}

# Managed Node Groups

resource "aws_eks_node_group" "this" {
  for_each = var.node_groups

  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "${var.name}-${each.key}"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = var.subnet_ids

  instance_types = each.value.instance_types
  capacity_type  = each.value.capacity_type
  ami_type       = each.value.ami_type
  disk_size      = each.value.disk_size

  scaling_config {
    min_size     = each.value.min_size
    desired_size = each.value.desired_size
    max_size     = each.value.max_size
  }

  update_config {
    max_unavailable_percentage = 33
  }

  labels = merge(
    {
      "node-group" = each.key
    },
    each.value.labels
  )

  dynamic "taint" {
    for_each = each.value.taints
    content {
      key    = taint.value.key
      value  = taint.value.value
      effect = taint.value.effect
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.node_worker_policy,
    aws_iam_role_policy_attachment.node_cni_policy,
    aws_iam_role_policy_attachment.node_ecr_policy,
    aws_iam_role_policy_attachment.node_ssm_policy,
  ]

  tags = merge(var.tags, {
    Name = "${var.name}-${each.key}"
  })
}

# EKS Addons

resource "aws_eks_addon" "this" {
  for_each = var.cluster_addons

  cluster_name                = aws_eks_cluster.this.name
  addon_name                  = each.key
  addon_version               = each.value.version != "" ? each.value.version : null
  resolve_conflicts_on_update = each.value.resolve_conflicts
  service_account_role_arn    = each.key == "aws-ebs-csi-driver" && var.enable_ebs_csi_irsa ? aws_iam_role.ebs_csi[0].arn : (each.value.service_account_role_arn != "" ? each.value.service_account_role_arn : null)

  depends_on = [aws_eks_node_group.this]

  tags = var.tags
}

# ArgoCD Cross-Cluster Access Role
# This role is created in the target cluster's account and allows ArgoCD from another account to manage this cluster

resource "aws_iam_role" "argocd_access" {
  count = var.enable_argocd_access && var.argocd_source_account_id != "" ? 1 : 0

  name = "${var.name}-argocd-access"

  # Note: ExternalId condition removed because argocd-k8s-auth doesn't pass it correctly
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = "arn:${local.partition}:iam::${var.argocd_source_account_id}:root"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(var.tags, {
    Name = "${var.name}-argocd-access"
  })
}

# Grant ArgoCD role cluster admin access via EKS Access Entry
resource "aws_eks_access_entry" "argocd" {
  count = var.enable_argocd_access && var.argocd_source_account_id != "" ? 1 : 0

  cluster_name  = aws_eks_cluster.this.name
  principal_arn = aws_iam_role.argocd_access[0].arn
  type          = "STANDARD"

  tags = var.tags
}

resource "aws_eks_access_policy_association" "argocd" {
  count = var.enable_argocd_access && var.argocd_source_account_id != "" ? 1 : 0

  cluster_name  = aws_eks_cluster.this.name
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
  principal_arn = aws_iam_role.argocd_access[0].arn

  access_scope {
    type = "cluster"
  }

  depends_on = [aws_eks_access_entry.argocd]
}
