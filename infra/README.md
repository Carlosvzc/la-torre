# infra/ — La Torre en AWS con Terraform (práctica 3.6)

Todo el entorno se crea y se destruye con código: VPC, EKS (nodos autoescalables + Cluster
Autoscaler), Agones, ECR, DynamoDB + Lambda con Function URL, rol OIDC de GitHub Actions y
alerta de presupuesto. Región por defecto: **us-east-2**.

## Una sola vez: bucket del estado remoto
```powershell
aws login
$cuenta = aws sts get-caller-identity --query Account --output text
aws s3 mb "s3://la-torre-tfstate-$cuenta" --region us-east-2
aws s3api put-bucket-versioning --bucket "la-torre-tfstate-$cuenta" --versioning-configuration Status=Enabled
@"
bucket       = "la-torre-tfstate-$cuenta"
key          = "dev/terraform.tfstate"
region       = "us-east-2"
use_lockfile = true
"@ | Set-Content infra\backend.hcl
```
`use_lockfile = true` bloquea el estado con un archivo en S3 (Terraform ≥ 1.10), sin tabla de DynamoDB.

## Ciclo de trabajo
```powershell
cd infra
terraform init -backend-config=backend.hcl
terraform fmt -check; terraform validate
terraform plan -var correo_alerta=TU_CORREO -out plan.tfplan      # revisar en un pull request
terraform apply plan.tfplan                                         # EKS tarda ~15–20 min
aws eks update-kubeconfig --name la-torre-default --region us-east-2
# ... prácticas 3.3, 3.2, 3.4, 3.5 ...
terraform destroy -var correo_alerta=TU_CORREO                      # AL TERMINAR CADA SESIÓN
```
El clúster se llama `la-torre-<workspace>`: con `terraform workspace new prod` el mismo código
crea `la-torre-prod`.

## Antes de aplicar
- **Versión de Kubernetes:** `version_kubernetes` (1.32 por defecto) debe estar en EKS y ser
  compatible con la versión de Agones que instale Helm. Comprobar con
  `aws eks describe-cluster-versions --query "clusterVersions[].clusterVersion"`.
- Si la cuenta ya tiene el proveedor OIDC de GitHub: `-var crear_oidc_github=false`.
- Tras el apply: poner `rol_github_actions` en la variable **AWS_ROLE_ARN** del repositorio
  (GitHub → Settings → Secrets and variables → Actions → Variables) y `lambda_url` en
  `k8s/config.yaml`.

## Validado sin nube
`terraform init -backend=false && terraform validate` → *Success! The configuration is valid.*

## Apagar sin dejar huérfanos (lo aprendido el 16/11/2026)

1. Borrar primero lo que creó Kubernetes fuera de Terraform: `kubectl delete fleetautoscaler,fleet --all`,
   `kubectl delete -f k8s/locust.yaml` y `helm uninstall monitoreo -n monitoreo`.
2. **Desinstalar Agones antes del destroy**: `helm uninstall agones -n agones-system --no-hooks` y
   `terraform state rm helm_release.agones`. Si Terraform lo intenta, la desinstalación espera a los
   *finalizers* de Agones, se agota el tiempo y el destroy falla a medias (los nodos siguen vivos con IP
   públicas y no se puede soltar el Internet Gateway).
3. `terraform destroy` y luego `scripts/comprobar-huerfanos.ps1`: todo debe salir en "ninguno".