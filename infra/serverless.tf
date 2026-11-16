# Tabla de líderes serverless (práctica 3.5): Lambda + DynamoDB + Function URL.
resource "aws_dynamodb_table" "lideres" {
  name         = "${local.nombre}-lideres"
  billing_mode = "PAY_PER_REQUEST" # se paga por petición: sin jugadores, casi cero
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }
}

data "archive_file" "lideres" {
  type        = "zip"
  source_file = "${path.module}/../serverless/leaderboard/lambda_function.py"
  output_path = "${path.module}/.terraform/lideres.zip"
}

resource "aws_iam_role" "lambda" {
  name = "${local.nombre}-lambda-lideres"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Sin este permiso la función da AccessDenied (lo advierte el PDF)
resource "aws_iam_role_policy" "lambda_dynamo" {
  name = "lideres-dynamodb"
  role = aws_iam_role.lambda.id
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = ["dynamodb:UpdateItem", "dynamodb:Scan"], Resource = aws_dynamodb_table.lideres.arn }]
  })
}

resource "aws_lambda_function" "lideres" {
  function_name    = "${local.nombre}-lideres"
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.12"
  handler          = "lambda_function.lambda_handler"
  filename         = data.archive_file.lideres.output_path
  source_code_hash = data.archive_file.lideres.output_base64sha256
  memory_size      = 256
  timeout          = 10
  environment {
    variables = { TABLA = aws_dynamodb_table.lideres.name }
  }
}

resource "aws_lambda_function_url" "lideres" {
  function_name      = aws_lambda_function.lideres.function_name
  authorization_type = "NONE"
  cors {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST"]
    allow_headers = ["content-type"]
  }
}

resource "aws_cloudwatch_log_group" "lideres" {
  name              = "/aws/lambda/${aws_lambda_function.lideres.function_name}"
  retention_in_days = 3
}
