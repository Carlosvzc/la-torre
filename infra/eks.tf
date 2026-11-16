# Clúster EKS con un grupo de nodos de juego que escala entre nodos_min y nodos_max.
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.31"

  cluster_name                             = local.nombre
  cluster_version                          = var.version_kubernetes
  cluster_endpoint_public_access           = true
  enable_cluster_creator_admin_permissions = true # quien hace "apply" administra el clúster

  # Sin llave KMS propia: al destruir, AWS deja las llaves "pendientes de borrado" 7–30 días
  # y quedarían como recurso huérfano. Para la práctica basta el cifrado por defecto de EKS.
  create_kms_key            = false
  cluster_encryption_config = {}

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.public_subnets

  eks_managed_node_groups = {
    juego = {
      instance_types = [var.tipo_nodo]
      min_size       = var.nodos_min
      desired_size   = var.nodos_deseados
      max_size       = var.nodos_max
      labels         = { rol = "juego" }
    }
  }

  # Puertos de los GameServers (rango por defecto de Agones) abiertos a internet
  node_security_group_additional_rules = {
    agones_juego = {
      description = "Puertos de juego de Agones (WebSocket sobre TCP)"
      protocol    = "tcp"
      from_port   = 7000
      to_port     = 8000
      type        = "ingress"
      cidr_blocks = ["0.0.0.0/0"]
    }
  }
}

# Cluster Autoscaler: agrega nodos cuando hay pods pendientes (tercera capa del autoescalado).
# Usa IRSA: un rol de IAM solo para su cuenta de servicio, sin llaves.
module "irsa_autoscaler" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.48"

  role_name                        = "${local.nombre}-cluster-autoscaler"
  attach_cluster_autoscaler_policy = true
  cluster_autoscaler_cluster_names = [module.eks.cluster_name]

  oidc_providers = {
    eks = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:cluster-autoscaler"]
    }
  }
}
