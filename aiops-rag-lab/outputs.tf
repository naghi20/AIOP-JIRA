output "grafana_api_webhook_url" {
  description = "Recommended Grafana webhook URL: API Gateway -> SQS FIFO -> aiops-rag-ingest Lambda"
  value       = "${aws_apigatewayv2_api.grafana.api_endpoint}/alerts"
}

output "grafana_direct_lambda_url" {
  description = "Direct aiops-rag-ingest Lambda Function URL; testing/rollback only"
  value       = aws_lambda_function_url.aiops_ingest.function_url
}

output "grafana_sqs_queue_url" {
  value = aws_sqs_queue.grafana_alerts.url
}

output "grafana_sqs_dlq_url" {
  value = aws_sqs_queue.grafana_alerts_dlq.url
}

output "s3_bucket" {
  value = aws_s3_bucket.runbooks.bucket
}

output "opensearch_collection_endpoint" {
  value = aws_opensearchserverless_collection.vector.collection_endpoint
}

output "opensearch_index_name" {
  value = "aiops-runbooks"
}

output "jira_project_key" {
  value = var.jira_project_key
}

output "jira_secret_name" {
  value = aws_secretsmanager_secret.jira.name
}

output "approval_topic_arn" {
  value = aws_sns_topic.approvals.arn
}

output "remediation_function_name" {
  value = aws_lambda_function.aiops_remediation.function_name
}

output "ingest_function_name" {
  value = aws_lambda_function.aiops_ingest.function_name
}

output "runbook_ingester_function_name" {
  value = aws_lambda_function.aiops_runbook_ingester.function_name
}
