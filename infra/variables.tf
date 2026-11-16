variable "region" {
  description = "Región de AWS"
  type        = string
  default     = "us-east-2"
}

variable "proyecto" {
  description = "Prefijo de los nombres de los recursos"
  type        = string
  default     = "la-torre"
}

variable "version_kubernetes" {
  # Agones 1.62 soporta 1.34–1.36 y EKS tiene 1.34–1.37 en soporte estándar (16/11/2026).
  # Una versión en soporte EXTENDIDO cobra mucho más por hora de clúster.
  description = "Versión de EKS (debe estar soportada por Agones; ver infra/README.md)"
  type        = string
  default     = "1.35"
}

variable "tipo_nodo" {
  # El plan gratuito de AWS solo deja lanzar tipos "free-tier-eligible" (c7i-flex.large,
  # m7i-flex.large, t3/t4g/t8i small y micro). c7i.large fue rechazado al crear los nodos.
  # c7i-flex.large: optimizada a cómputo, 2 vCPU / 4 GiB, USD 0.08479/h en us-east-2.
  description = "Tipo de instancia de los nodos de juego (optimizada a cómputo)"
  type        = string
  default     = "c7i-flex.large"
}

variable "nodos_min" {
  type    = number
  default = 2
}

variable "nodos_deseados" {
  type    = number
  default = 2
}

variable "nodos_max" {
  description = "Tope del Cluster Autoscaler (la prueba de carga 3.4 lo usa)"
  type        = number
  default     = 8
}

variable "repo_github" {
  description = "Repositorio que puede publicar imágenes en ECR (OIDC, sin llaves)"
  type        = string
  default     = "Carlosvzc/la-torre"
}

variable "crear_oidc_github" {
  description = "Crear el proveedor OIDC de GitHub y el rol de publicación (la SCP del plan gratuito lo prohíbe)"
  type        = bool
  default     = false
}

variable "correo_alerta" {
  description = "Correo para la alerta de presupuesto (vacío = sin alerta por Terraform)"
  type        = string
  default     = ""
}

variable "presupuesto_usd" {
  type    = number
  default = 10
}
