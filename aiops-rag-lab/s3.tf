data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "runbooks" {
  bucket = "${var.project_name}-runbooks-${data.aws_caller_identity.current.account_id}"
  tags   = var.tags
}

resource "aws_s3_bucket_public_access_block" "runbooks" {
  bucket = aws_s3_bucket.runbooks.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_object" "runbooks_prefix" {
  bucket = aws_s3_bucket.runbooks.id
  key    = "runbooks/"
}
