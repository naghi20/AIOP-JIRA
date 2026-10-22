variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "project_name" {
  type    = string
  default = "aiops-rag"
}

variable "jira_project_key" {
  type    = string
  default = "IT"
}

variable "jira_issue_type" {
  type    = string
  default = "Task"
}

variable "jira_domain" {
  type    = string
  default = "https://ahmedaalnaghi.atlassian.net"
}

variable "jira_user_email" {
  type = string
}

variable "jira_api_token" {
  type      = string
  sensitive = true
}

variable "grafana_webhook_token" {
  type      = string
  sensitive = true
}

variable "approval_email" {
  type = string
}

variable "bedrock_embedding_model_id" {
  type    = string
  default = "amazon.titan-embed-text-v2:0"
}

variable "bedrock_llm_model_id" {
  type    = string
  default = "anthropic.claude-3-5-sonnet-20240620-v1:0"
}

variable "embedding_dimension" {
  type    = number
  default = 1024
}

variable "lambda_ingest_zip" {
  type    = string
  default = "lambda/aiops_ingest.zip"
}

variable "lambda_authorizer_zip" {
  type    = string
  default = "lambda/api_authorizer.zip"
}

variable "lambda_runbook_ingester_zip" {
  type    = string
  default = "lambda/runbook_ingester.zip"
}

variable "lambda_remediation_zip" {
  type    = string
  default = "lambda/remediation_orchestrator.zip"
}

variable "tags" {
  type = map(string)
  default = {
    Project   = "aiops-rag"
    ManagedBy = "terraform"
  }
}
