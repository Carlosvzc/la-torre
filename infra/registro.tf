# Registro de imágenes del servidor (ECR). force_delete permite que "destroy" lo borre
# aunque tenga imágenes: así no quedan recursos huérfanos que sigan cobrando.
resource "aws_ecr_repository" "servidor" {
  name                 = "torre-server"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

# GitHub Actions publica en ECR con OIDC: el pipeline pide credenciales temporales,
# no hay llaves guardadas como secretos (lo que el PDF recomienda para producción).
resource "aws_iam_openid_connect_provider" "github" {
  count           = var.crear_oidc_github ? 1 : 0
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

data "aws_iam_openid_connect_provider" "github" {
  count = var.crear_oidc_github ? 0 : 1
  url   = "https://token.actions.githubusercontent.com"
}

locals {
  oidc_github_arn = var.crear_oidc_github ? aws_iam_openid_connect_provider.github[0].arn : data.aws_iam_openid_connect_provider.github[0].arn
}

resource "aws_iam_role" "github" {
  name = "${local.nombre}-github-actions"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = local.oidc_github_arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = { "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com" }
        StringLike   = { "token.actions.githubusercontent.com:sub" = "repo:${var.repo_github}:ref:refs/heads/main" }
      }
    }]
  })
}

resource "aws_iam_role_policy" "github_ecr" {
  name = "publicar-en-ecr"
  role = aws_iam_role.github.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["ecr:GetAuthorizationToken"], Resource = "*" },
      {
        Effect = "Allow"
        Action = ["ecr:BatchCheckLayerAvailability", "ecr:InitiateLayerUpload", "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload", "ecr:PutImage", "ecr:BatchGetImage", "ecr:DescribeImages"]
        Resource = aws_ecr_repository.servidor.arn
      }
    ]
  })
}
