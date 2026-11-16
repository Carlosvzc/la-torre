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
# APAGADO por defecto: la SCP de la organización del plan gratuito prohíbe
# iam:CreateOpenIDConnectProvider. En una cuenta normal: -var=crear_oidc_github=true.
resource "aws_iam_openid_connect_provider" "github" {
  count           = var.crear_oidc_github ? 1 : 0
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

resource "aws_iam_role" "github" {
  count = var.crear_oidc_github ? 1 : 0
  name  = "${local.nombre}-github-actions"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = aws_iam_openid_connect_provider.github[0].arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = { "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com" }
        StringLike   = { "token.actions.githubusercontent.com:sub" = "repo:${var.repo_github}:ref:refs/heads/main" }
      }
    }]
  })
}

resource "aws_iam_role_policy" "github_ecr" {
  count = var.crear_oidc_github ? 1 : 0
  name  = "publicar-en-ecr"
  role  = aws_iam_role.github[0].id
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