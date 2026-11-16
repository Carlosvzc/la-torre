output "cluster" {
  value = module.eks.cluster_name
}

output "region" {
  value = var.region
}

output "ecr_repositorio" {
  value = aws_ecr_repository.servidor.repository_url
}

output "lambda_url" {
  description = "Function URL de la tabla de líderes (va en el ConfigMap torre-config)"
  value       = aws_lambda_function_url.lideres.function_url
}

output "rol_github_actions" {
  description = "Va en la variable AWS_ROLE_ARN del repositorio de GitHub"
  value       = aws_iam_role.github.arn
}

output "configurar_kubectl" {
  value = "aws eks update-kubeconfig --name ${module.eks.cluster_name} --region ${var.region}"
}
