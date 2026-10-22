# Current lab status

Learning lab: end-to-end validation is incomplete.

## Confirmed
- Existing Grafana, Prometheus, and EC2 instances are retained.
- Grafana webhook contact-point test succeeds.
- OpenSearch aiops-runbooks index creation was acknowledged.
- Updated ingester loads dependencies and calls Titan V2 in us-west-2.
- Runbook ingester asynchronous function-error retries are temporarily 0.

## Current blocker
Titan Text Embeddings V2 InvokeModel returns ThrottlingException.
Both CLI and Lambda fail in the same AWS account.
us-west-2 reports 6000 requests/minute; us-east-1 reports zero.
One earlier Oregon CLI test succeeded.

## Not yet verified
- Successful runbook indexing.
- Full RAG retrieval and Claude diagnosis.
- Jira diagnosis comment.
- SSM-managed targets and safe automated remediation.

## Review requirements
- Reconcile duplicate handler sources and ZIP paths before building.
- Match each Lambda filename with its source_code_hash.
- Latest ingester does not deduplicate repeated uploads.
- SNS notification is not an approval-and-resume implementation.
- Do not run automatic remediation before trainer review.
- Use your own AWS/Jira credentials and webhook token.
- Do not deploy historical tfs.txt or assume older PDFs are current.
