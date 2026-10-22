<img width="1408" height="768" alt="image_822ac06c" src="https://github.com/user-attachments/assets/e09904e6-70ce-418f-b6ba-b9efac83d406" />

Full Flow
Grafana alert → aiops-ingest Lambda (your existing code) → duplicate check → Jira ticket
(project IT) → invokes aiops-remediation Lambda aiops-remediation Lambda → Bedrock Titan
embed incident → OpenSearch k-NN retrieve runbook chunks → Bedrock Claude diagnosis → Low
severity + low risk → SSM automated remediation → Medium/High severity → SNS human approval
→ Jira AI comment with sources


# AIOps RAG Lab: Grafana to Jira and AI-Assisted Remediation

> Status: learning lab under development. End-to-end validation is incomplete.
> Current blocker: Bedrock Titan Text Embeddings V2 returns `ThrottlingException`
> from both the AWS CLI and the runbook-ingestion Lambda in `us-west-2`.
> Do not enable automated remediation until the trainer has reviewed the code,
> target mapping, IAM permissions, and allowed actions.

## 1. Project goal

Connect infrastructure monitoring to incident tracking and runbook-based AI diagnosis:

1. Prometheus collects infrastructure metrics.
2. Grafana evaluates alert rules and sends webhook notifications.
3. API Gateway authenticates the webhook before buffering it in SQS FIFO.
4. An ingestion Lambda creates a Jira Task and performs episode-label deduplication.
5. A remediation Lambda retrieves relevant runbook context and requests a Claude diagnosis.
6. A severity/risk policy routes proposals to human review or restricted SSM remediation.

This is the intended architecture, not a claim that every stage currently works.

## 2. Architecture

```text
Existing EC2 / node_exporter
          |
     Prometheus
          |
       Grafana
          | HTTPS POST /alerts + X-Aiops-Token
          v
API Gateway HTTP API ----> Lambda token authorizer
          |                  allow/deny
          v
     SQS FIFO -----------------> SQS dead-letter queue
          |
          v
 aiops-rag-ingest
          | Jira episode search / create Task
          | asynchronous invocation
          v
 aiops-rag-remediation
          | Titan query embedding
          | OpenSearch k-NN runbook retrieval
          | Claude diagnosis
          v
   Severity + risk + validated action/target
          |                         |
          v                         v
 Restricted SSM action       SNS human-review notification
          |                         |
          +----------> Jira comments / audit evidence

Runbook ingestion (separate path):
S3 runbooks/*.md or *.txt
          |
          v
aiops-rag-runbook-ingester
          | read -> chunk -> Titan embedding
          v
OpenSearch Serverless: aiops-runbooks
```

The SQS FIFO/DLQ path buffers Grafana alerts. It is not the retry queue for
S3-triggered runbook ingestion. SNS currently sends a notification; it does not
implement a verified approval-and-resume workflow.

## 3. Current verified status

Based on the deployment session on 22-23 October 2026:

| Component/check | Status |
|---|---|
| Existing Grafana, Prometheus, and two EC2 VMs | Retained; do not recreate |
| Terraform backend resources | User reported successful creation |
| Grafana webhook contact-point test | Succeeded after configuring Extra Headers |
| OpenSearch `aiops-runbooks` creation | Acknowledged; actual mapping should be inspected |
| Ingester Python dependencies | Import errors resolved |
| OpenSearch endpoint normalization | Double `https://` issue resolved |
| Ingester embedding destination | Logs confirm Titan V2 in `us-west-2` |
| Standalone Titan embedding | Initially succeeded with 1024 dimensions |
| Subsequent CLI and Lambda embedding calls | Throttled, including a minimal no-retry CLI test |
| Ingester async function-error retries | Temporarily set to 0 |
| Runbook documents indexed | Not verified |
| Jira ticket + RAG diagnosis comment | Full chain not verified |
| Claude model invocation | Not verified |
| EC2 SSM management and remediation | Not verified |

A successful Terraform apply, webhook HTTP response, or Lambda END/REPORT line
is not proof of downstream processing success.

## 4. Regions and configuration

| Setting | Current lab configuration |
|---|---|
| Terraform / Lambda / S3 / OpenSearch Region | `us-east-1` |
| Titan embedding Region | `us-west-2` |
| OpenSearch signing service | `aoss` |
| OpenSearch signing Region | `us-east-1` |
| Collection | `aiops-rag-vector`, type `VECTORSEARCH` |
| Index | `aiops-runbooks` |
| Embedding model | `amazon.titan-embed-text-v2:0` |
| Embedding dimensions | `1024` |
| Embedding normalization | `true` |
| Jira project / issue type | `IT` / `Task` |
| Runbook prefix | `runbooks/` |
| Lambda runtime | Python 3.12 |

The split Region configuration is intentional: the original account reported
zero Titan V2 RPM in Virginia and 6000 RPM in Oregon. The quota is not proof of
successful inference; subsequent Oregon calls still throttled.

Use your own account-specific endpoints, bucket, Jira site, emails, and secrets.
Do not copy another student's credentials or account ARNs.

### Terraform inputs

Review `variables.tf` and the actual local source before deployment. Example:

```hcl
# terraform.tfvars.example - placeholders only
aws_region            = "us-east-1"
project_name          = "aiops-rag"
jira_domain           = "https://YOUR-SITE.atlassian.net"
jira_project_key      = "IT"
jira_issue_type       = "Task"
jira_user_email       = "you@example.com"
jira_api_token        = "REPLACE_LOCALLY"
grafana_webhook_token = "REPLACE_WITH_RANDOM_SECRET"
approval_email        = "reviewer@example.com"
```

Never commit the real `terraform.tfvars`. Sensitive Terraform values can also be
stored in state and saved plans; excluding variable files alone is insufficient.

### Ingester environment

```text
OPENSEARCH_HOST=https://<collection-id>.us-east-1.aoss.amazonaws.com
INDEX_NAME=aiops-runbooks
BEDROCK_MODEL_ID=amazon.titan-embed-text-v2:0
EMBEDDING_DIMENSION=1024
EMBEDDING_REGION=us-west-2
OPENSEARCH_REGION=us-east-1
```

The latest conversation-supplied handler defaults to these two Regions. If using
environment overrides, add them to Terraform too. Do not change Lambda's
`AWS_REGION` to move the embedding client.

Both authorizer and ingest receive `AIOPS_WEBHOOK_TOKEN` from
`var.grafana_webhook_token`. Jira credentials use Secrets Manager in the intended
configuration. Verify that the actual Terraform and handlers agree.

## 5. Source layout and build discipline

Suggested canonical layout (reconcile with the files actually committed):

```text
aiops-rag-lab/
  *.tf
  .terraform.lock.hcl
  terraform.tfvars.example
  lambda/
    aiops_ingest/handler.py
    api_authorizer/handler.py
    runbook_ingester/handler.py
    remediation_orchestrator/handler.py
  requirements.txt
  high-cpu.md
  docs/
  CURRENT_STATUS.md
  README.md
```

Older flat handlers such as `lambda/handler_runbook_ingester.py` may coexist with
folder-based handlers. This previously caused old code to be packaged. Choose
one canonical handler per function and make build instructions use that path.

Historical project ZIPs, `tfs.txt`, and older PDFs may contain stale architecture
or bugs. They are not the source of truth for the current deployment.

## 6. Implementation guide

Proceed one checkpoint at a time. Record the account, resource status and results
before continuing. In the original lab, keep the existing monitoring VMs.

### Step 1 - Check identity and Bedrock before provisioning paid resources

```bash
aws sts get-caller-identity --no-cli-pager

aws service-quotas get-service-quota \
  --service-code bedrock --quota-code L-26C560CE \
  --region us-west-2 --no-cli-pager

AWS_MAX_ATTEMPTS=1 aws bedrock-runtime invoke-model \
  --region us-west-2 \
  --model-id amazon.titan-embed-text-v2:0 \
  --content-type application/json --accept application/json \
  --body '{"inputText":"test","dimensions":1024,"normalize":true}' \
  --cli-binary-format raw-in-base64-out \
  /tmp/aiops-embedding-test.json --no-cli-pager
```

If successful:

```bash
python3 - <<'PY'
import json
with open('/tmp/aiops-embedding-test.json') as f:
    result = json.load(f)
print('Dimensions:', len(result.get('embedding', [])))
PY
```

Expected length: 1024. If the minimal request persistently throttles, stop and
investigate with AWS rather than creating an upload loop. The current lab is
blocked at this gate despite one earlier success.

### Step 2 - Install Debian build tools

```bash
sudo apt update
sudo apt install -y python3 python3-venv zip unzip git
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
```

Use a virtual environment rather than modifying Debian's system Python. Record
and pin the dependency versions tested for Python 3.12. The ingester/remediation
imports include `requests` and `requests-aws4auth`; inspect all imports before
finalizing requirements. Do not assume development and Lambda platforms match
if adding native extensions.

### Step 3 - Build the ingester archive

From the folder containing the Terraform files:

```bash
.venv/bin/python -m pip install --target build/runbook_ingester \
  requests requests-aws4auth
cp lambda/runbook_ingester/handler.py build/runbook_ingester/handler.py
python3 -m py_compile lambda/runbook_ingester/handler.py

python3 - <<'PY'
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
package = Path('build/runbook_ingester')
assert (package / 'handler.py').is_file()
assert (package / 'requests').is_dir()
assert (package / 'requests_aws4auth').is_dir()
with ZipFile('lambda/runbook_ingester.zip', 'w', ZIP_DEFLATED) as z:
    for p in package.rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts:
            z.write(p, p.relative_to(package))
print('Built lambda/runbook_ingester.zip')
PY
```

`handler.py` and dependency directories must be at the archive root. Use separate
build directories for the other handlers to avoid packaging the wrong handler.
Build all Terraform-referenced ZIPs before planning; inspect each function's
imports rather than blindly reusing one archive. The example above builds only
the ingester, not all four functions.

For each Lambda, use matching path/hash inputs:

```hcl
filename         = var.lambda_runbook_ingester_zip
source_code_hash = filebase64sha256(var.lambda_runbook_ingester_zip)
```

Use the corresponding `lambda_ingest_zip`, `lambda_authorizer_zip`, and
`lambda_remediation_zip` variables in the other resources. Check actual variable
defaults and overrides. A root-level archive and `lambda/<archive>.zip` are not
the same file. Reconcile any manual CLI deployment with Terraform before apply.

### Step 4 - Review Terraform security and deploy

Before applying, verify:

- Network policy JSON is an array; encryption policy JSON is an object.
- Data-access principals belong to the collection's account. Avoid stale IDs.
- Reuse a single `aws_caller_identity.current` data source for dynamic account IDs.
- Collection rule is `collection/aiops-rag-vector`; index rule is
  `index/aiops-rag-vector/*` when using the default project name.
- IAM `aoss:APIAccessAll`, collection data permissions, and network access are
  separate requirements. Dashboards does not bypass these controls.
- Authorizer uses its own ZIP, payload format 2.0, simple responses enabled,
  and a nonempty token checked with constant-time comparison.
- Route has `authorization_type = "CUSTOM"` and the correct `authorizer_id`.
- Direct Function URL exposure is independently reviewed or removed after a
  deliberate migration; it does not inherit API Gateway authorization.
- No unexpected changes to existing Grafana/Prometheus/EC2 resources.

```bash
terraform init
terraform fmt
terraform validate
terraform plan -out=tfplan
# Review the full plan; only then:
terraform apply tfplan
```

Do not grant blanket administrator permissions as the normal deployment design.
Use an approved deployment identity and reviewed least-privilege policies.

### Step 5 - Create and inspect the index

First confirm the collection is Active. In an authorized OpenSearch Dashboards
Dev Tools session, inspect whether the index already exists. Do not recreate the
original lab's existing index or delete its data blindly.

For a fresh deployment only:

```json
PUT /aiops-runbooks
{
  "settings": {"index": {"knn": true}},
  "mappings": {
    "properties": {
      "content": {"type": "text"},
      "embedding": {
        "type": "knn_vector",
        "dimension": 1024,
        "method": {
          "name": "hnsw",
          "engine": "faiss",
          "space_type": "cosinesimil"
        }
      },
      "title": {"type": "text"},
      "source": {"type": "keyword"},
      "doc_type": {"type": "keyword"},
      "created_at": {"type": "date"}
    }
  }
}
```

Check support for the selected method/engine in your collection, and inspect the
resulting mapping. Ingestion and retrieval must use the same embedding model and
dimension. Equal dimensions alone do not make different models compatible.

### Step 6 - Configure Grafana

Edit the existing webhook contact point:

```text
URL: value of terraform output -raw grafana_api_webhook_url
HTTP method: POST
Extra Headers:
  X-Aiops-Token: <same raw value as grafana_webhook_token>
```

The output already includes `/alerts`; do not append it again. Do not use the
Authorization/Bearer credentials field for this custom header. Do not include
quotes or a Bearer prefix in its value. Preserve unrelated existing settings.

Test missing and wrong tokens: neither should enqueue a message. Test the valid
token with an appropriate payload, then independently verify downstream logs.
An active consumer may remove queue messages quickly; do not require a visible
queue depth of exactly one to conclude delivery occurred.

### Step 7 - Upload once and verify ingestion

Only after Bedrock inference works:

```bash
aws s3 cp high-cpu.md \
  "s3://$(terraform output -raw s3_bucket)/runbooks/high-cpu.md" \
  --region us-east-1

aws logs tail /aws/lambda/aiops-rag-runbook-ingester \
  --region us-east-1 --since 2m --follow
```

Expected diagnostic events in the latest handler:

```text
ingestion_started
embedding_request
embedding_success
document_indexed
chunk_ingested
runbook_ingested
```

Press Ctrl+C before typing another command into that terminal.

Verify documents in Dev Tools, using your own bucket name:

```json
GET /aiops-runbooks/_search
{
  "size": 5,
  "_source": ["title", "source", "doc_type", "content"],
  "query": {
    "term": {"source": "s3://YOUR-BUCKET/runbooks/high-cpu.md"}
  }
}
```

The latest ingester intentionally removes unsupported `_delete_by_query`.
It does not implement cleanup or write idempotency. Repeated uploads, partial
failures and duplicate notifications can create duplicate chunks. Implement a
reviewed supported document lifecycle before repeated ingestion or production use.

### Step 8 - Configure and test RAG independently

The remediation handler needs a separate Oregon embedding client and an
independently configured Claude client. Verify Claude availability and invocation
before claiming the diagnosis path works. Normalize OpenSearch endpoints and
retain Virginia SigV4 signing. Inspect current source before patching.

Start with a sandbox high-severity/diagnostic-only alert after reviewing routing;
verify Jira Task, episode label, retrieved source, diagnosis comment and SNS email.
Do not use a low-severity alert as the first full-chain test because it may reach
an automatic command path. SNS subscription must be confirmed by its recipient.

### Step 9 - Enable remediation only after review

Check the existing application VM's SSM Agent, IAM instance profile, required
network connectivity and managed-node status. Being in the same account does not
automatically enable SSM. Map exporter labels such as `ip:9100` to an explicitly
approved instance; do not use that exporter address as an SSM instance ID.

Planned policy: low/info severity + low AI risk + approved action + approved target
may automate; medium/high severity and uncertain plans go to human review.
AI risk classification and command-name allow-lists alone are not sufficient.
Validate exact services/targets and constrain IAM. Do not treat arbitrary service
restarts or cache clearing as universally safe high-CPU fixes.

Verify command completion and exit status, monitoring recovery, and Jira evidence.
A SendCommand response only confirms submission. Automatic recovery closure and
human-approval resume are not verified features of this lab.

## 7. Retry configuration during debugging

```hcl
resource "aws_lambda_function_event_invoke_config" "runbook_ingester" {
  function_name          = aws_lambda_function.aiops_runbook_ingester.function_name
  maximum_retry_attempts = 0
}
```

This belongs on async invoke configuration, not the SQS event-source mapping.
It controls retries after function errors, not retries inside Boto3. Invocation
throttling/system failures and duplicate source delivery are distinct concerns.
Without failure capture, failed events may be discarded. After debugging, review
an on-failure destination and restore retries (normally 2) with idempotency.

## 8. Troubleshooting history

| Symptom | Finding / action |
|---|---|
| `No module named requests` | Bundle dependencies at ZIP root |
| DNS lookup for host `https` | Double URL scheme; normalize the endpoint once |
| `_delete_by_query` 404 | Unsupported Serverless operation; not proof of an empty index |
| Old code still executes | Duplicate handlers and archive paths; inspect deployed ZIP |
| Cross-account policy validation error | Stale hardcoded principal; derive deployment account |
| Grafana 401 | Configure custom Extra Header, not Bearer authorization |
| CLI and Lambda Bedrock throttle | Same account/Region confirmed; persistent blocker unresolved |

AWS support handoff: provide model, Region, account privately, quota code/value,
UTC timestamps, minimal reproducer and sanitized service request IDs. Do not share
root keys, tokens, or raw signed debug output. A Lambda invocation ID is not a
Bedrock service request ID.

## 9. GitHub and credential safety

Use a private repository for trainer review first. Never commit:

```gitignore
.terraform/
*.tfstate
*.tfstate.*
*.tfplan
tfplan*
*.tfvars
*.tfvars.json
!terraform.tfvars.example
.env
.env.*
!.env.example
.aws/
*.pem
*.key
*.zip
package/
build/
.venv/
venv/
__pycache__/
*.pyc
*.log
tfs.txt
```

Commit `.terraform.lock.hcl`. Review example files and source for hardcoded
secrets: extension filters are not secret scanners. `.gitignore` does not remove
tracked files or old history. Rotate exposed secrets and remediate history before
sharing. Use a non-root routine development identity; do not pass root credentials
to classmates or place static credentials inside Lambda code.

If using the suggested sharing repository layout, place this README at repository
root and adjust commands to first `cd aiops-rag-lab`. Otherwise place it beside the
Terraform files and run the commands there.

## 10. Completion criteria and cost controls

Do not call the project complete until evidence exists for authentication,
runbook indexing, retrieval, Claude diagnosis, Jira comments, duplicate handling,
confirmed human-review notification, sandbox SSM execution and monitoring recovery.

OpenSearch and EC2 may keep accruing charges while Bedrock is blocked. Review
billing and intentionally manage lab lifetime. Never run a blanket destroy against
shared monitoring infrastructure without reviewing exactly what it will remove.

## 11. References and scope

This README describes the latest conversation-reported configuration, not a
certified audit of every committed file. Reconcile source, Terraform plans and
live resources before deployment.

- [Bedrock API troubleshooting](https://docs.aws.amazon.com/bedrock/latest/userguide/troubleshooting-api-error-codes.html)
- [Titan embedding parameters](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-titan-embed-text.html)
- [OpenSearch Serverless supported operations](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless-genref.html)
- [Lambda async configuration](https://docs.aws.amazon.com/lambda/latest/dg/invocation-async-configuring.html)
- [Lambda async error handling](https://docs.aws.amazon.com/lambda/latest/dg/invocation-async-error-handling.html)
- [Boto3 configuration](https://docs.aws.amazon.com/boto3/latest/guide/configuration.html)
