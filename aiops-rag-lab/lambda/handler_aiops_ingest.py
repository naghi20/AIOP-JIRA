import base64, hashlib, json, os, urllib.error, urllib.request
from datetime import datetime, timezone
import boto3

def jira_request(domain, auth_header, path, payload):
    request = urllib.request.Request(f"{domain}{path}", data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Authorization": f"Basic {auth_header}", "Content-Type": "application/json", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=8) as response:
        return json.loads(response.read().decode("utf-8"))

def process_alert(item, notification, domain, project, auth_header):
    raw_status = item.get("status", notification.get("status", "unknown"))
    status = {"alerting": "firing", "ok": "resolved", "no_data": "resolved", "firing": "firing", "resolved": "resolved"}.get(str(raw_status).lower(), raw_status)
    if status == "resolved":
        return {"result": "resolved_skipped"}
    if status != "firing":
        raise ValueError(f"Unsupported alert status: {raw_status}")
    labels = item.get("labels", {})
    fingerprint = item.get("fingerprint") or hashlib.sha256(json.dumps(labels, sort_keys=True).encode()).hexdigest()
    starts_at = item.get("startsAt") or notification.get("startsAt") or datetime.now(timezone.utc).isoformat()
    annotations = item.get("annotations", {})
    alert_name = labels.get("alertname", "GrafanaAlert")
    severity = labels.get("severity", "unknown")
    instance = labels.get("instance", "Not supplied")
    episode_hash = hashlib.sha256(f"grafana|{fingerprint}|{starts_at}".encode()).hexdigest()
    episode_label = f"aiops-episode-{episode_hash}"
    search_result = jira_request(domain, auth_header, "/rest/api/3/search/jql", {
        "jql": f"project = {json.dumps(project)} AND labels = {json.dumps(episode_label)}",
        "maxResults": 1, "fields": ["summary"]})
    issues = search_result.get("issues", [])
    if issues:
        return {"result": "duplicate", "jira_key": issues[0]["key"], "episode_label": episode_label}
    summary = annotations.get("summary") or notification.get("title") or f"{alert_name} on {instance}"
    description = "\n".join([f"Alert: {alert_name}", f"Status: {status}", f"Severity: {severity}", f"Instance: {instance}",
        f"Started at: {starts_at}", f"Fingerprint: {fingerprint}", f"Episode label: {episode_label}", "", "Details:",
        annotations.get("description") or "No description supplied.", "", "Source: Grafana webhook"])
    issue = jira_request(domain, auth_header, "/rest/api/2/issue", {"fields": {
        "project": {"key": project}, "summary": summary[:255], "description": description,
        "labels": ["aiops", episode_label], "issuetype": {"name": "Task"}, "priority": {"name": "High"}}})
    return {"result": "created", "jira_key": issue["key"], "episode_label": episode_label}

def webhook_handler(event, context, verify_token=True):
    if verify_token:
        expected = os.environ.get("AIOPS_WEBHOOK_TOKEN")
        headers = event.get("headers", {}) or {}
        incoming = headers.get("X-Aiops-Token") or headers.get("x-aiops-token")
        if expected and incoming != expected:
            return {"statusCode": 401, "body": json.dumps({"error": "Unauthorized"})}
    try:
        raw_body = event["body"]
        if event.get("isBase64Encoded"):
            raw_body = base64.b64decode(raw_body).decode("utf-8")
        notification = json.loads(raw_body)
        alerts = notification.get("alerts")
        if not isinstance(alerts, list) or not alerts or not all(isinstance(i, dict) for i in alerts):
            raise ValueError("Request must contain a non-empty alerts array")
    except (KeyError, TypeError, ValueError) as error:
        return {"statusCode": 400, "body": json.dumps({"error": str(error)})}
    try:
        domain = os.environ["JIRA_DOMAIN"].rstrip("/")
        project = os.environ["JIRA_PROJECT"]
        secret_name = os.environ["JIRA_SECRET_NAME"]
        secret = boto3.client("secretsmanager").get_secret_value(SecretId=secret_name)
        credentials = json.loads(secret["SecretString"])
        auth_header = base64.b64encode(f"{credentials['jira_user']}:{credentials['jira_token']}".encode()).decode()
        results = []
        remediation_fn = os.environ.get("REMEDIATION_FUNCTION_NAME")
        lambda_client = boto3.client("lambda")
        for item in alerts:
            result = process_alert(item, notification, domain, project, auth_header)
            if result.get("result") == "created" and remediation_fn:
                try:
                    lambda_client.invoke(FunctionName=remediation_fn, InvocationType="Event",
                        Payload=json.dumps({"alert": item, "jira_key": result["jira_key"]}))
                    result["remediation"] = "invoked"
                except Exception:
                    result["remediation"] = "invoke_failed"
            results.append(result)
        return {"statusCode": 200, "body": json.dumps({"results": results})}
    except urllib.error.HTTPError as error:
        return {"statusCode": 502, "body": json.dumps({"error": "Jira API request failed", "jira_status": error.code,
            "details": error.read().decode("utf-8", errors="replace")})}
    except ValueError as error:
        return {"statusCode": 400, "body": json.dumps({"error": str(error)})}
    except Exception as error:
        print(json.dumps({"event": "processing_failed", "error_type": type(error).__name__}))
        return {"statusCode": 500, "body": json.dumps({"error": "Processing failed", "error_type": type(error).__name__})}

def lambda_handler(event, context):
    if "Records" not in event:
        return webhook_handler(event, context, verify_token=True)
    records = event["Records"]
    if not records:
        raise ValueError("Empty SQS batch")
    for record in records:
        if record.get("eventSource") != "aws:sqs":
            raise ValueError("Unsupported event source")
        result = webhook_handler({"body": record["body"], "isBase64Encoded": False}, context, verify_token=False)
        if not 200 <= result.get("statusCode", 500) < 300:
            raise RuntimeError("SQS message processing failed")
    return {"processed_records": len(records)}
