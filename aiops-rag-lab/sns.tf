resource "aws_sns_topic" "approvals" {
  name = "${var.project_name}-high-severity-approvals"
  tags = var.tags
}

resource "aws_sns_topic_subscription" "approval_email" {
  topic_arn = aws_sns_topic.approvals.arn
  protocol  = "email"
  endpoint  = var.approval_email
}
