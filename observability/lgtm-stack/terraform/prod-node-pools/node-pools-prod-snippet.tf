# LGTM Stack PRODUCTION Node Pools Configuration
# To be added to your GKE cluster terraform.tfvars
# Based on: cs-dev-terraform-infra/environments/mgmt/gke/.../terraform.tfvars

# Add these to your node_pools array in terraform.tfvars:

node_pools = [
  # Pool 1: LGTM Ingester Pool (CRITICAL - On-Demand) - PRODUCTION
  {
    name              = "lgtm-ingester-prod"
    node_version      = "1.32.9-gke.1010000"  # Match your cluster version
    machine_type      = "n2-standard-8"  # 8 vCPU, 32GB RAM (upgraded from n2-standard-4)
    disk_size_gb      = 100  # Increased from 50GB
    disk_type         = "pd-ssd"  # SSD for better performance
    min_node_count    = 3
    max_node_count    = 8
    auto_repair       = true
    auto_upgrade      = true
    max_pods_per_node = 32
    preemptible       = false  # NO SPOT for production ingesters
    tags              = ["lgtm-ingester-prod", "critical-workload", "internal-ip-allow", "deny-all"]
    labels = {
      workload    = "ingester"
      stateful    = "true"
      pool-type   = "critical"
      lgtm-role   = "ingester"
      env         = "production"
      cost-center = "platform"
    }
    taints = [{
      key    = "workload"
      value  = "ingester"
      effect = "NO_SCHEDULE"
    }]
  },

  # Pool 2: LGTM Query Pool (Spot-Friendly) - PRODUCTION
  {
    name              = "lgtm-query-prod"
    node_version      = "1.32.9-gke.1010000"
    machine_type      = "n2-standard-4"  # 4 vCPU, 16GB RAM (upgraded from n2-standard-2)
    disk_size_gb      = 50
    disk_type         = "pd-standard"
    min_node_count    = 2
    max_node_count    = 10
    auto_repair       = true
    auto_upgrade      = true
    max_pods_per_node = 32
    preemptible       = true  # Spot OK for queries
    tags              = ["lgtm-query-prod", "spot-workload", "internal-ip-allow", "deny-all"]
    labels = {
      workload    = "query"
      stateful    = "false"
      spot        = "true"
      pool-type   = "query"
      lgtm-role   = "query"
      env         = "production"
      cost-center = "platform"
    }
    taints = [{
      key    = "workload"
      value  = "query"
      effect = "NO_SCHEDULE"
    }]
  },

  # Pool 3: LGTM General Pool (Spot-Friendly) - PRODUCTION
  {
    name              = "lgtm-general-prod"
    node_version      = "1.32.9-gke.1010000"
    machine_type      = "e2-standard-4"  # 4 vCPU, 16GB RAM (upgraded from e2-standard-2)
    disk_size_gb      = 50
    disk_type         = "pd-standard"
    min_node_count    = 2
    max_node_count    = 10
    auto_repair       = true
    auto_upgrade      = true
    max_pods_per_node = 32
    preemptible       = true  # Spot OK
    tags              = ["lgtm-general-prod", "spot-workload", "internal-ip-allow", "deny-all"]
    labels = {
      workload    = "general"
      spot        = "true"
      pool-type   = "general"
      lgtm-role   = "distributor-compactor"
      env         = "production"
      cost-center = "platform"
    }
    taints = []  # No taints - general purpose
  },

  # Pool 4: LGTM Cache Pool (Spot-Friendly) - PRODUCTION
  {
    name              = "lgtm-cache-prod"
    node_version      = "1.32.9-gke.1010000"
    machine_type      = "e2-standard-2"  # 2 vCPU, 8GB RAM (same as dev)
    disk_size_gb      = 30
    disk_type         = "pd-standard"
    min_node_count    = 3  # Minimum 3 for 3 memcached instances
    max_node_count    = 6
    auto_repair       = true
    auto_upgrade      = true
    max_pods_per_node = 16
    preemptible       = true  # Spot OK for memcached
    tags              = ["lgtm-cache-prod", "spot-workload", "internal-ip-allow", "deny-all"]
    labels = {
      workload    = "cache"
      spot        = "true"
      pool-type   = "cache"
      lgtm-role   = "memcached"
      env         = "production"
      cost-center = "platform"
    }
    taints = [{
      key    = "workload"
      value  = "cache"
      effect = "NO_SCHEDULE"
    }]
  },

  # Pool 5: LGTM System Pool (On-Demand) - PRODUCTION
  {
    name              = "lgtm-system-prod"
    node_version      = "1.32.9-gke.1010000"
    machine_type      = "e2-standard-2"  # 2 vCPU, 8GB RAM (upgraded from e2-small)
    disk_size_gb      = 50
    disk_type         = "pd-standard"
    min_node_count    = 2  # HA for Grafana
    max_node_count    = 3
    auto_repair       = true
    auto_upgrade      = true
    max_pods_per_node = 32
    preemptible       = false  # On-demand for Grafana
    tags              = ["lgtm-system-prod", "system-workload", "internal-ip-allow", "deny-all"]
    labels = {
      workload    = "system"
      pool-type   = "system"
      lgtm-role   = "grafana-system"
      env         = "production"
      cost-center = "platform"
    }
    taints = []  # No taints for system components
  }
]

# Estimated Monthly Cost:
# - lgtm-ingester-prod:  n2-standard-8 x 3-8 nodes = $600-1,600/month
# - lgtm-query-prod:     n2-standard-4 x 2-10 nodes (spot) = $120-360/month
# - lgtm-general-prod:   e2-standard-4 x 2-10 nodes (spot) = $80-240/month
# - lgtm-cache-prod:     e2-standard-2 x 3-6 nodes (spot) = $75-150/month
# - lgtm-system-prod:    e2-standard-2 x 2-3 nodes = $60-90/month
#
# TOTAL ESTIMATED: $935-2,440/month (depending on autoscaling)
