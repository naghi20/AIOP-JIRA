resource "aws_sqs_queue" "grafana_alerts_dlq" {
  name                        = "${var.project_name}-grafana-alerts-dlq.fifo"
  fifo_queue                  = true
  content_based_deduplication = true
  visibility_timeout_seconds  = 120
  message_retention_seconds   = 1209600
  tags                        = var.tags
}

resource "aws_sqs_queue" "grafana_alerts" {
  name                        = "${var.project_name}-grafana-alerts.fifo"
  fifo_queue                  = true
  content_based_deduplication = true
  visibility_timeout_seconds  = 120
  message_retention_seconds   = 345600

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.grafana_alerts_dlq.arn
    maxReceiveCount     = 3
  })

  tags = var.tags
}

resource "aws_lambda_event_source_mapping" "grafana_alerts" {
  event_source_arn = aws_sqs_queue.grafana_alerts.arn
  function_name    = aws_lambda_function.aiops_ingest.arn
  batch_size       = 1
  enabled          = true
}
