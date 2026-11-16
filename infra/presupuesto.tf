# Alerta de presupuesto (el PDF pide USD 10 antes de la primera práctica).
# Avisa por correo al 50 % real y al 100 % pronosticado del mes.
resource "aws_budgets_budget" "alerta" {
  count        = var.correo_alerta == "" ? 0 : 1
  name         = "${local.nombre}-presupuesto"
  budget_type  = "COST"
  limit_amount = tostring(var.presupuesto_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 50
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.correo_alerta]
  }
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.correo_alerta]
  }
}
