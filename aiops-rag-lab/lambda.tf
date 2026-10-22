resource "aws_lambda_function" "aiops_ingest" {
  function_name = "${var.project_name}-ingest"
  role          = aws_iam_role.aiops_ingest.arn
  runtime       = "python3.12"
  handler       = "handler.lambda_handler"
  filename      = var.lambda_ingest_zip
  timeout       = 60
  memory_size   = 256

  environment {
    variables = {
      JIRA_DOMAIN               = var.jira_domain
      JIRA_PROJECT              = var.jira_project_key
      JIRA_SECRET_NAME          = aws_secretsmanager_secret.jira.name
      REMEDIATION_FUNCTION_NAME = aws_lambda_function.aiops_remediation.function_name
      AIOPS_WEBHOOK_TOKEN       = var.grafana_webhook_token
    }
  }

  tags = var.tags
}

resource "aws_lambda_function_url" "aiops_ingest" {
  function_name      = aws_lambda_function.aiops_ingest.function_name
  authorization_type = "NONE"
}

resource "aws_lambda_function" "api_authorizer" {
  function_name = "${var.project_name}-api-authorizer"
  role          = aws_iam_role.api_authorizer.arn
  runtime       = "python3.12"
  handler       = "handler.lambda_handler"
  filename      = var.lambda_authorizer_zip
  timeout       = 10
  memory_size   = 128

  environment {
    variables = {
      AIOPS_WEBHOOK_TOKEN = var.grafana_webhook_token
    }
  }

  tags = var.tags
}

resource "aws_lambda_function" "aiops_runbook_ingester" {
  function_name = "${var.project_name}-runbook-ingester"
  role          = aws_iam_role.aiops_runbook_ingester.arn
  runtime       = "python3.12"
  handler       = "handler.lambda_handler"
  filename      = var.lambda_runbook_ingester_zip
  timeout       = 120
  memory_size   = 512

  environment {
    variables = {
      OPENSEARCH_HOST     = aws_opensearchserverless_collection.vector.collection_endpoint
      INDEX_NAME          = "aiops-runbooks"
      BEDROCK_MODEL_ID    = var.bedrock_embedding_model_id
      EMBEDDING_DIMENSION = tostring(var.embedding_dimension)
    }
  }

  tags = var.tags
}

resource "aws_lambda_function" "aiops_remediation" {
  function_name = "${var.project_name}-remediation"
  role          = aws_iam_role.aiops_remediation.arn
  runtime       = "python3.12"
  handler       = "handler.lambda_handler"
  filename      = var.lambda_remediation_zip
  timeout       = 120
  memory_size   = 512

  environment {
    variables = {
      OPENSEARCH_HOST     = aws_opensearchserverless_collection.vector.collection_endpoint
      INDEX_NAME          = "aiops-runbooks"
      BEDROCK_MODEL_ID    = var.bedrock_embedding_model_id
      EMBEDDING_DIMENSION = tostring(var.embedding_dimension)
      LLM_MODEL_ID        = var.bedrock_llm_model_id
      JIRA_DOMAIN         = var.jira_domain
      JIRA_PROJECT        = var.jira_project_key
      JIRA_SECRET_NAME    = aws_secretsmanager_secret.jira.name
      APPROVAL_TOPIC_ARN  = aws_sns_topic.approvals.arn
    }
  }

  tags = var.tags
}

resource "aws_lambda_permission" "s3_invoke_ingester" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.aiops_runbook_ingester.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.runbooks.arn
}

resource "aws_s3_bucket_notification" "runbooks" {
  bucket = aws_s3_bucket.runbooks.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.aiops_runbook_ingester.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "runbooks/"
    filter_suffix       = ".txt"
  }

  lambda_function {
    lambda_function_arn = aws_lambda_function.aiops_runbook_ingester.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "runbooks/"
    filter_suffix       = ".md"
  }

  depends_on = [aws_lambda_permission.s3_invoke_ingester]
}
