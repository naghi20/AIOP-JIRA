resource "aws_apigatewayv2_api" "grafana" {
  name          = "${var.project_name}-grafana-api"
  protocol_type = "HTTP"
  tags          = var.tags
}

resource "aws_iam_role" "apigateway_sqs" {
  name = "${var.project_name}-apigateway-sqs-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "apigateway.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy" "apigateway_sqs" {
  name = "${var.project_name}-apigateway-sqs-send"
  role = aws_iam_role.apigateway_sqs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "sqs:SendMessage"
        Resource = aws_sqs_queue.grafana_alerts.arn
      }
    ]
  })
}

resource "aws_apigatewayv2_integration" "grafana_to_sqs" {
  api_id                 = aws_apigatewayv2_api.grafana.id
  integration_type       = "AWS_PROXY"
  integration_subtype    = "SQS-SendMessage"
  credentials_arn        = aws_iam_role.apigateway_sqs.arn
  payload_format_version = "1.0"

  request_parameters = {
    QueueUrl       = aws_sqs_queue.grafana_alerts.url
    MessageBody    = "$request.body"
    MessageGroupId = "grafana-alerts"
  }
}

resource "aws_apigatewayv2_authorizer" "token" {
  api_id                            = aws_apigatewayv2_api.grafana.id
  authorizer_type                   = "REQUEST"
  authorizer_uri                    = aws_lambda_function.api_authorizer.invoke_arn
  identity_sources                  = ["$request.header.X-Aiops-Token"]
  name                              = "aiops-token-authorizer"
  authorizer_payload_format_version = "2.0"
  authorizer_result_ttl_in_seconds  = 0
  enable_simple_responses           = true
}

resource "aws_lambda_permission" "authorizer_invoke" {
  statement_id  = "AllowAPIGatewayInvokeAuthorizer"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api_authorizer.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.grafana.execution_arn}/*/*"
}

resource "aws_apigatewayv2_route" "grafana_alerts" {
  api_id             = aws_apigatewayv2_api.grafana.id
  route_key          = "POST /alerts"
  target             = "integrations/${aws_apigatewayv2_integration.grafana_to_sqs.id}"
  authorization_type = "CUSTOM"
  authorizer_id      = aws_apigatewayv2_authorizer.token.id
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.grafana.id
  name        = "$default"
  auto_deploy = true
}
