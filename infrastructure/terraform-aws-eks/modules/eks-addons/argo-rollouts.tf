# Argo Rollouts
# Progressive delivery controller for Kubernetes

resource "helm_release" "argo_rollouts" {
  count = var.enable_argo_rollouts ? 1 : 0

  name             = "argo-rollouts"
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-rollouts"
  version          = var.argo_rollouts_version
  namespace        = "argo-rollouts"
  create_namespace = true

  values = [var.argo_rollouts_values]

  depends_on = [helm_release.aws_lb_controller]
}
