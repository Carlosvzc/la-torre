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

  # La cuenta del plan gratuito pertenece a una organización de AWS cuya política (SCP)
  # prohíbe iam:CreateOpenIDConnectProvider, así que no hay IRSA (ver README).
  enable_irsa = false

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.public_subnets

  eks_managed_node_groups = {
    juego = {
      instance_types = [var.tipo_nodo]
      min_size       = var.nodos_min
      desired_size   = var.nodos_deseados
      max_size       = var.nodos_max
      labels         = { rol = "juego" }
      # Sin IRSA, el Cluster Autoscaler toma los permisos del rol de los nodos
      iam_role_additional_policies = { autoscaler = aws_iam_policy.autoscaler.arn }
    }
  }

  # Puertos de los GameServers (rango por defecto de Agones) abiertos a internet
  node_security_group_additional_rules = {
    # El plano de control llama al webhook de Agones (pods agones-extensions, puerto 8081).
    # Sin esta regla, crear una Fleet falla con "failed calling webhook mutations.agones.dev".
    agones_webhook = {
      description                   = "Plano de control hacia el webhook de Agones"
      protocol                      = "tcp"
      from_port                     = 8081
      to_port                       = 8081
      type                          = "ingress"
      source_cluster_security_group = true
    }
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
# Lo ideal es IRSA (un rol solo para su cuenta de servicio), pero la SCP de la organización
# prohíbe crear el proveedor OIDC del clúster. Alternativa: esta política va en el rol de los
# nodos y las acciones que cambian el tamaño solo valen para grupos con la etiqueta del clúster.
resource "aws_iam_policy" "autoscaler" {
  name = "${local.nombre}-cluster-autoscaler"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["autoscaling:DescribeAutoScalingGroups", "autoscaling:DescribeAutoScalingInstances",
          "autoscaling:DescribeLaunchConfigurations", "autoscaling:DescribeScalingActivities",
          "autoscaling:DescribeTags", "ec2:DescribeImages", "ec2:DescribeInstanceTypes",
          "ec2:DescribeLaunchTemplateVersions", "ec2:GetInstanceTypesFromInstanceRequirements",
        "eks:DescribeNodegroup"]
        Resource = "*"
      },
      {
        Effect    = "Allow"
        Action    = ["autoscaling:SetDesiredCapacity", "autoscaling:TerminateInstanceInAutoScalingGroup"]
        Resource  = "*"
        Condition = { StringEquals = { "aws:ResourceTag/k8s.io/cluster-autoscaler/${local.nombre}" = "owned" } }
      }
    ]
  })
}