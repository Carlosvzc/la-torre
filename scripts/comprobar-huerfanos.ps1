# Comprueba que, tras "terraform destroy", no quede nada de La Torre cobrando en AWS (práctica 3.6).
# Uso:  powershell -ExecutionPolicy Bypass -File scripts\comprobar-huerfanos.ps1
$r = "us-east-2"
function Linea($nombre, $valor) {
    if ([string]::IsNullOrWhiteSpace($valor)) { Write-Host ("{0,-28} ninguno" -f $nombre) -ForegroundColor Green }
    else { Write-Host ("{0,-28} {1}" -f $nombre, $valor) -ForegroundColor Yellow }
}
Write-Host "Recursos del proyecto en $r ($(Get-Date -Format 'yyyy-MM-dd HH:mm'))`n"
Linea "Clústeres EKS"            (aws eks list-clusters --region $r --query "clusters" --output text)
Linea "Instancias EC2 del juego" (aws ec2 describe-instances --region $r --filters Name=tag:eks:cluster-name,Values=la-torre-default Name=instance-state-name,Values=pending,running,stopping,stopped --query "Reservations[].Instances[].InstanceId" --output text)
Linea "Balanceadores (ELB)"      ((aws elb describe-load-balancers --region $r --query "LoadBalancerDescriptions[].LoadBalancerName" --output text) + (aws elbv2 describe-load-balancers --region $r --query "LoadBalancers[].LoadBalancerName" --output text))
Linea "Discos EBS sueltos"       (aws ec2 describe-volumes --region $r --filters Name=status,Values=available --query "Volumes[].VolumeId" --output text)
Linea "IP elásticas"             (aws ec2 describe-addresses --region $r --query "Addresses[].PublicIp" --output text)
Linea "VPC 10.40.0.0/16"         (aws ec2 describe-vpcs --region $r --filters Name=cidr,Values=10.40.0.0/16 --query "Vpcs[].VpcId" --output text)
Linea "Repositorios ECR"         (aws ecr describe-repositories --region $r --query "repositories[].repositoryName" --output text)
Linea "Funciones Lambda"         (aws lambda list-functions --region $r --query "Functions[?starts_with(FunctionName,'la-torre')].FunctionName" --output text)
Linea "Tablas DynamoDB"          (aws dynamodb list-tables --region $r --query "TableNames" --output text)
Linea "Grupos de logs"           (aws logs describe-log-groups --region $r --query "logGroups[?contains(logGroupName,'la-torre')].logGroupName" --output text)
Linea "Plantillas de lanzamiento" (aws ec2 describe-launch-templates --region $r --query "LaunchTemplates[].LaunchTemplateName" --output text)
Linea "Roles IAM del proyecto"   (aws iam list-roles --query "Roles[?contains(RoleName,'la-torre') || starts_with(RoleName,'juego-eks')].RoleName" --output text)
Write-Host "`nSe conserva a propósito: el bucket S3 del estado de Terraform (centavos al mes)."
