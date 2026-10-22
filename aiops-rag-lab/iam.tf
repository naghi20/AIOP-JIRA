data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "aiops_ingest" {
  name               = "${var.project_name}-ingest-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
  tags               = var.tags
}

resource "aws_iam_role" "aiops_runbook_ingester" {
  name               = "${var.project_name}-runbook-ingester-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
  tags               = var.tags
}

resource "aws_iam_role" "aiops_remediation" {
  name               = "${var.project_name}-remediation-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
  tags               = var.tags
}

resource "aws_iam_role" "api_authorizer" {
  name               = "${var.project_name}-api-authorizer-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
  tags               = var.tags
}

data "aws_iam_policy_document" "common" {
  statement {
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
    resources = ["*"]
  }

  statement {
    actions   = ["aoss:APIAccessAll"]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "common" {
  name   = "${var.project_name}-lambda-common"
  policy = data.aws_iam_policy_document.common.json
}

resource "aws_iam_role_policy_attachment" "ingest_common" {
  role       = aws_iam_role.aiops_ingest.name
  policy_arn = aws_iam_policy.common.arn
}

resource "aws_iam_role_policy_attachment" "runbook_common" {
  role       = aws_iam_role.aiops_runbook_ingester.name
  policy_arn = aws_iam_policy.common.arn
}

resource "aws_iam_role_policy_attachment" "remediation_common" {
  role       = aws_iam_role.aiops_remediation.name
  policy_arn = aws_iam_policy.common.arn
}

resource "aws_iam_role_policy_attachment" "authorizer_common" {
  role       = aws_iam_role.api_authorizer.name
  policy_arn = aws_iam_policy.common.arn
}

data "aws_iam_policy_document" "ingest" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.jira.arn]
  }

  statement {
    actions = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes"
    ]
    resources = [aws_sqs_queue.grafana_alerts.arn]
  }

  statement {
    actions   = ["lambda:InvokeFunction"]
    resources = [aws_lambda_function.aiops_remediation.arn]
  }
}

resource "aws_iam_policy" "ingest" {
  name   = "${var.project_name}-ingest"
  policy = data.aws_iam_policy_document.ingest.json
}

resource "aws_iam_role_policy_attachment" "ingest_extra" {
  role       = aws_iam_role.aiops_ingest.name
  policy_arn = aws_iam_policy.ingest.arn
}

data "aws_iam_policy_document" "runbook" {
  statement {
    actions = [
      "s3:GetObject",
      "s3:ListBucket"
    ]
    resources = [
      aws_s3_bucket.runbooks.arn,
      "${aws_s3_bucket.runbooks.arn}/*"
    ]
  }

  statement {
    actions   = ["bedrock:InvokeModel"]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "runbook" {
  name   = "${var.project_name}-runbook-ingester"
  policy = data.aws_iam_policy_document.runbook.json
}

resource "aws_iam_role_policy_attachment" "runbook_extra" {
  role       = aws_iam_role.aiops_runbook_ingester.name
  policy_arn = aws_iam_policy.runbook.arn
}

data "aws_iam_policy_document" "remediation" {
  statement {
    actions   = ["bedrock:InvokeModel"]
    resources = ["*"]
  }

  statement {
    actions = [
      "ssm:SendCommand",
      "ssm:GetCommandInvocation",
      "ssm:DescribeInstanceInformation"
    ]
    resources = ["*"]
  }

  statement {
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.approvals.arn]
  }

  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.jira.arn]
  }
}

resource "aws_iam_policy" "remediation" {
  name   = "${var.project_name}-remediation"
  policy = data.aws_iam_policy_document.remediation.json
}

resource "aws_iam_role_policy_attachment" "remediation_extra" {
  role       = aws_iam_role.aiops_remediation.name
  policy_arn = aws_iam_policy.remediation.arn
}
