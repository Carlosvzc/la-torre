# Red: VPC con 2 zonas y solo subredes públicas (sin NAT Gateway, que cobra por hora).
# Los GameServers de Agones necesitan IP pública de nodo para que los jugadores lleguen.
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.13"

  name                    = local.nombre
  cidr                    = "10.40.0.0/16"
  azs                     = local.azs
  public_subnets          = ["10.40.0.0/20", "10.40.16.0/20"]
  map_public_ip_on_launch = true
  enable_nat_gateway      = false
  enable_dns_hostnames    = true

  public_subnet_tags = {
    "kubernetes.io/role/elb" = 1
  }
}
