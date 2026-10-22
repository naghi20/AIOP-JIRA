# AIOps RAG Lab — Terraform (corrected v3)

Production flow: Grafana -> API Gateway (CUSTOM token authorizer) -> SQS FIFO (+DLQ) -> aiops-ingest -> Jira -> aiops-remediation -> SSM/SNS -> Jira comment.

Fixes in this version:
- Authorizer Lambda uses its own ZIP (lambda/api_authorizer.zip) via lambda_authorizer_zip variable.
- Route has authorization_type = "CUSTOM" and authorizer_id set.
- Authorizer uses enable_simple_responses = true (simple isAuthorized response).
- Authorizer uses hmac.compare_digest for token comparison.
- JQL label values are quoted to handle hyphens.
- OpenSearch collection resource pattern has no trailing wildcard.
- Approval path: Jira comment is posted BEFORE the approval-sent label, so a failed comment is retried.
- tfs.txt (old combined draft) is excluded from the deploy folder.

Known limitations (documented):
- SSM targeting: Grafana instance label is ip:9100; map to instance ID or Name tag.
- Recovery alerts skipped; tickets not auto-closed.
- SNS approval is notification-only; resume needs Step Functions waitForTaskToken.
- Fixed MessageGroupId: one poison message blocks group until DLQ.

## Deploy
```bash
cp terraform.tfvars.example terraform.tfvars
terraform init && terraform plan && terraform apply
```
Use grafana_api_webhook_url in Grafana: <api>/alerts with header X-Aiops-Token.
