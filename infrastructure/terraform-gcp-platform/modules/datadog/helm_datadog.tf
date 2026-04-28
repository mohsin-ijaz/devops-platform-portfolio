locals {
  is_production = var.datadog_environment == "prod"
  is_gcp        = var.cloud_provider == "gcp"
  is_aws        = var.cloud_provider == "aws"
}

provider "helm" {
  kubernetes = {
    host                   = var.cluster_endpoint != null ? "https://${var.cluster_endpoint}" : null
    token                  = local.is_gcp ? var.cluster_access_token : null
    cluster_ca_certificate = var.cluster_ca_certificate != null ? base64decode(var.cluster_ca_certificate) : null

    exec = local.is_gcp ? {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "gke-gcloud-auth-plugin"
      args        = []
      } : (local.is_aws ? {
        api_version = "client.authentication.k8s.io/v1beta1"
        command     = "aws"
        args        = ["eks", "get-token", "--cluster-name", var.cluster_name]
    } : null)
  }
}

resource "helm_release" "datadog_agent" {
  name       = "datadog-agent"
  chart      = "datadog"
  repository = "https://helm.datadoghq.com"
  version    = var.chart_version
  namespace  = kubernetes_namespace.monitoring.id

  timeout = 600

  set_sensitive = [
    {
      name  = "datadog.apiKey"
      value = var.datadog_api_key
    }
  ]

  set = [
    {
      name  = "datadog.site"
      value = var.datadog_site
    },
    {
      name  = "datadog.logs.enabled"
      value = true
    },
    {
      name  = "datadog.logs.containerCollectAll"
      value = false
    },
    {
      name  = "datadog.leaderElection"
      value = true
    },
    {
      name  = "datadog.collectEvents"
      value = true
    },
    {
      name  = "datadog.apm.portEnabled"
      value = var.datadog_apm_port_enabled
    },
    {
      name  = "datadog.dogstatsd.useHostPort"
      value = true
    },
    {
      name  = "clusterAgent.enabled"
      value = false
    },
    {
      name  = "clusterAgent.metricsProvider.enabled"
      value = false
    },
    {
      name  = "networkMonitoring.enabled"
      value = false
    },
    {
      name  = "systemProbe.enableTCPQueueLength"
      value = false
    },
    {
      name  = "systemProbe.enableOOMKill"
      value = false
    },
    {
      name  = "securityAgent.runtime.enabled"
      value = false
    },
    {
      name  = "datadog.hostVolumeMountPropagation"
      value = "None"
    },
    {
      name  = "clusterName"
      value = var.cluster_name
    },
    {
      name  = "datadog.containerIncludeLogs"
      value = <<EOT
kube_namespace:^ancillary-.*
kube_namespace:^consumer-.*
kube_namespace:^enterprise-.*
EOT
    },
    {
      name  = "datadog.containerExcludeLogs"
      value = <<EOT
kube_namespace:argocd
kube_namespace:^cert-.*
kube_namespace:datadog
kube_namespace:default
kube_namespace:external-secrets
kube_namespace:^gitlab-.*
kube_namespace:^gke-.*
kube_namespace:^gmp-.*
kube_namespace:^istio-.*
kube_namespace:^kiali-.*
kube_namespace:^kube-.*
kube_namespace:observability
EOT
    },
    {
      name  = "datadog.containerExcludeMetrics"
      value = "name:.*"
    },
    {
      name  = "agents.containers.agent.resources.limits.cpu"
      value = var.agent_cpu_limit
    },
    {
      name  = "agents.containers.agent.resources.limits.memory"
      value = var.agent_memory_limit
    },
    {
      name  = "agents.containers.agent.resources.requests.cpu"
      value = var.agent_cpu_request
    },
    {
      name  = "agents.containers.agent.resources.requests.memory"
      value = var.agent_memory_request
    },
  ]

  set_list = [
    {
      name = "datadog.tags"
      value = [
        "infra.cloud-provider:${var.cloud_provider}",
        "infra.orchestrator:kubernetes",
        "infra.env:${var.datadog_environment}",
        "infra.domain:${var.datadog_domain}",
      ]
    },
  ]
}
