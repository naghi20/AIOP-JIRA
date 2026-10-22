resource "aws_lambda_function_event_invoke_config" "runbook_ingester" {
  function_name = aws_lambda_function.aiops_runbook_ingester.function_name

  # Temporary debugging setting: no retries after a function error.
  maximum_retry_attempts = 0
}