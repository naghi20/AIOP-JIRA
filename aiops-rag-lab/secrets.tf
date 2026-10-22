resource "aws_secretsmanager_secret" "jira" {
  name = "${var.project_name}/jira/credentials"
  tags = var.tags
}

resource "aws_secretsmanager_secret_version" "jira" {
  secret_id = aws_secretsmanager_secret.jira.id
  secret_string = jsonencode({
    jira_user  = var.jira_user_email
    jira_token = var.jira_api_token
  })
}
