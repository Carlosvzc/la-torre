# La Torre — infraestructura completa en AWS (práctica 3.6, variante AWS del PDF).
#
#   terraform init -backend-config=backend.hcl     (estado remoto en S3 con bloqueo)
#   terraform plan -out plan.tfplan                (se revisa en un pull request)
#   terraform apply plan.tfplan
#   terraform destroy                              (al terminar CADA sesión)
#
# Crea: VPC, EKS con nodos autoescalables, Cluster Autoscaler, Agones, ECR, DynamoDB,
# Lambda con Function URL, rol de GitHub Actions (OIDC) y alerta de presupuesto.

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws     = { source = "hashicorp/aws", version = "~> 5.80" }
    helm    = { source = "hashicorp/helm", version = "~> 2.13" }
    archive = { source = "hashicorp/archive", version = "~> 2.4" }
  }
  # Estado remoto: el bucket se crea una sola vez antes de "init" (ver infra/README.md).
  # Los datos (bucket, llave, región) van en backend.hcl para no fijar la cuenta en el código.
  backend "s3" {}
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Proyecto = var.proyecto
      Entorno  = terraform.workspace
      Practica = "unidad-3"
    }
  }
}

data "aws_caller_identity" "actual" {}
data "aws_availability_zones" "disponibles" { state = "available" }

locals {
  nombre = "${var.proyecto}-${terraform.workspace}"
  azs    = slice(data.aws_availability_zones.disponibles.names, 0, 2)
}
