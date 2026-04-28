# LGTM Production Node Pools - Set to 0 for Testing
# Uncomment and apply when ready to scale up

# NOTE: These are configured as separate resources
# You may need to integrate these into your existing GKE cluster terraform

# Data source for existing cluster
data "google_container_cluster" "lgtm_cluster" {
  name     = var.cluster_name
  location = var.cluster_location
  project  = var.project_id
}

# ============================================================================
# NODE POOL 1: INGESTER (CRITICAL - On-Demand)
# ============================================================================

resource "google_container_node_pool" "lgtm_ingester_prod" {
  name       = "lgtm-ingester-prod"
  cluster    = data.google_container_cluster.lgtm_cluster.name
  location   = var.cluster_location
  project    = var.project_id
  
  # Autoscaling enabled - initial_node_count removed (will use min_node_count)
  
  autoscaling {
    min_node_count = # TODO: set min nodes  # Set to 0 for testing
    max_node_count = # TODO: set max nodes
  }
  
  node_config {
    machine_type = "<MACHINE_TYPE>"  # TODO: choose based on workload  # 8 vCPU, 32GB RAM
    disk_size_gb = # TODO: set disk size
    disk_type    = "pd-ssd"
    service_account = "<GCP_SERVICE_ACCOUNT>"
    
    # On-Demand (not preemptible) for production ingesters
    preemptible = false
    
    labels = {
      workload    = "ingester"
      stateful    = "true"
      pool-type   = "critical"
      lgtm-role   = "ingester"
      env         = "production"
    }
    
    taint {
      key    = "workload"
      value  = "ingester"
      effect = "NO_SCHEDULE"
    }
    
    tags = ["lgtm-ingester-prod", "critical-workload"]
    
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
    
    metadata = {
      disable-legacy-endpoints = "true"
    }
  }
  
  management {
    auto_repair  = true
    auto_upgrade = true
  }
}

# ============================================================================
# NODE POOL 2: QUERY (Spot-Friendly)
# ============================================================================

resource "google_container_node_pool" "lgtm_query_prod" {
  name       = "lgtm-query-prod"
  cluster    = data.google_container_cluster.lgtm_cluster.name
  location   = var.cluster_location
  project    = var.project_id
  
  # Autoscaling enabled - initial_node_count removed (will use min_node_count)
  
  autoscaling {
    min_node_count = # TODO: set min nodes  # Set to 0 for testing
    max_node_count = # TODO: set max nodes
  }
  
  node_config {
    machine_type = "<MACHINE_TYPE>"  # TODO: choose based on workload  # 4 vCPU, 16GB RAM
    disk_size_gb = # TODO: set disk size
    disk_type    = "pd-standard"
    service_account = "<GCP_SERVICE_ACCOUNT>"
    
    preemptible = true  # Spot OK for queries
    
    labels = {
      workload    = "query"
      spot        = "true"
      pool-type   = "query"
      lgtm-role   = "query"
      env         = "production"
    }
    
    taint {
      key    = "workload"
      value  = "query"
      effect = "NO_SCHEDULE"
    }
    
    tags = ["lgtm-query-prod", "spot-workload"]
    
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
    
    metadata = {
      disable-legacy-endpoints = "true"
    }
  }
  
  management {
    auto_repair  = true
    auto_upgrade = true
  }
}

# ============================================================================
# NODE POOL 3: GENERAL (Spot-Friendly)
# ============================================================================

resource "google_container_node_pool" "lgtm_general_prod" {
  name       = "lgtm-general-prod"
  cluster    = data.google_container_cluster.lgtm_cluster.name
  location   = var.cluster_location
  project    = var.project_id
  
  # Autoscaling enabled - initial_node_count removed (will use min_node_count)
  
  autoscaling {
    min_node_count = # TODO: set min nodes  # Set to 0 for testing
    max_node_count = # TODO: set max nodes
  }
  
  node_config {
    machine_type = "<MACHINE_TYPE>"  # TODO: choose based on workload  # 4 vCPU, 16GB RAM
    disk_size_gb = # TODO: set disk size
    disk_type    = "pd-standard"
    service_account = "<GCP_SERVICE_ACCOUNT>"
    
    preemptible = false  # On-demand for distributors (critical for writes)
    
    labels = {
      workload    = "general"
      spot        = "true"
      pool-type   = "general"
      lgtm-role   = "distributor-compactor"
      env         = "production"
    }
    
    # No taints - general purpose
    
    tags = ["lgtm-general-prod", "spot-workload"]
    
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
    
    metadata = {
      disable-legacy-endpoints = "true"
    }
  }
  
  management {
    auto_repair  = true
    auto_upgrade = true
  }
}

# ============================================================================
# NODE POOL 4: CACHE (Spot-Friendly)
# ============================================================================

resource "google_container_node_pool" "lgtm_cache_prod" {
  name       = "lgtm-cache-prod"
  cluster    = data.google_container_cluster.lgtm_cluster.name
  location   = var.cluster_location
  project    = var.project_id
  
  # Autoscaling enabled - initial_node_count removed (will use min_node_count)
  
  autoscaling {
    min_node_count = # TODO: set min nodes  # Set to 0 for testing
    max_node_count = # TODO: set max nodes
  }
  
  node_config {
    machine_type = "<MACHINE_TYPE>"  # TODO: choose based on workload  # 2 vCPU, 8GB RAM
    disk_size_gb = # TODO: set disk size
    disk_type    = "pd-standard"
    service_account = "<GCP_SERVICE_ACCOUNT>"
    
    preemptible = true  # Spot OK for memcached
    
    labels = {
      workload    = "cache"
      spot        = "true"
      pool-type   = "cache"
      lgtm-role   = "memcached"
      env         = "production"
    }
    
    taint {
      key    = "workload"
      value  = "cache"
      effect = "NO_SCHEDULE"
    }
    
    tags = ["lgtm-cache-prod", "spot-workload"]
    
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
    
    metadata = {
      disable-legacy-endpoints = "true"
    }
  }
  
  management {
    auto_repair  = true
    auto_upgrade = true
  }
}

# ============================================================================
# NODE POOL 5: SYSTEM (On-Demand for Grafana/Prometheus)
# ============================================================================

resource "google_container_node_pool" "lgtm_system_prod" {
  name       = "lgtm-system-prod"
  cluster    = data.google_container_cluster.lgtm_cluster.name
  location   = var.cluster_location
  project    = var.project_id
  
  # Autoscaling enabled - initial_node_count removed (will use min_node_count)
  
  autoscaling {
    min_node_count = # TODO: set min nodes  # Set to 0 for testing
    max_node_count = # TODO: set max nodes
  }
  
  node_config {
    machine_type = "<MACHINE_TYPE>"  # TODO: choose based on workload  # 2 vCPU, 8GB RAM
    disk_size_gb = # TODO: set disk size
    disk_type    = "pd-standard"
    service_account = "<GCP_SERVICE_ACCOUNT>"
    
    preemptible = false  # On-demand for Grafana
    
    labels = {
      workload    = "system"
      pool-type   = "system"
      lgtm-role   = "grafana-system"
      env         = "production"
    }
    
    # No taints for system components
    
    tags = ["lgtm-system-prod", "system-workload"]
    
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
    
    metadata = {
      disable-legacy-endpoints = "true"
    }
  }
  
  management {
    auto_repair  = true
    auto_upgrade = true
  }
}
