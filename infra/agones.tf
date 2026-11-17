# Helm dentro de Terraform: Agones y el Cluster Autoscaler se instalan con el mismo "apply".
provider "helm" {
  kubernetes {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name, "--region", var.region]
    }
  }
}

resource "helm_release" "agones" {
  name             = "agones"
  repository       = "https://agones.dev/chart/stable"
  chart            = "agones"
  version          = "1.62.0" # soporta Kubernetes 1.34–1.36
  namespace        = "agones-system"
  create_namespace = true
  timeout          = 900

  # El chart crea por defecto balanceadores de carga (allocator y ping) que cobran por hora
  # y que "terraform destroy" no borra (los crea Kubernetes, no Terraform). No los usamos:
  # la asignación se hace con kubectl (GameServerAllocation) y los jugadores entran directo
  # a la IP pública del nodo y al puerto del GameServer.
  set {
    name  = "agones.allocator.service.serviceType"
    value = "ClusterIP"
  }
  set {
    name  = "agones.ping.install"
    value = "false"
  }
  depends_on = [module.eks]
}

resource "helm_release" "cluster_autoscaler" {
  name       = "cluster-autoscaler"
  repository = "https://kubernetes.github.io/autoscaler"
  chart      = "cluster-autoscaler"
  namespace  = "kube-system"

  set {
    name  = "autoDiscovery.clusterName"
    value = module.eks.cluster_name
  }
  set {
    name  = "awsRegion"
    value = var.region
  }
  set {
    name  = "rbac.serviceAccount.name"
    value = "cluster-autoscaler"
  }

  depends_on = [module.eks]
}
