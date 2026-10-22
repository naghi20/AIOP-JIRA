import json, os, base64, re
import boto3
import requests
from requests_aws4auth import AWS4Auth

bedrock = boto3.client("bedrock-runtime")
ssm = boto3.client("ssm")
sns = boto3.client("sns")
secrets = boto3.client("secretsmanager")
session = boto3.Session()
credentials = session.get_credentials()
region = session.region_name or "us-east-1"
host = os.environ["OPENSEARCH_HOST"].replace("https://", "").replace("http://", "").rstrip("/")
index = os.environ["INDEX_NAME"]
embed_model = os.environ["BEDROCK_MODEL_ID"]
llm_model = os.environ["LLM_MODEL_ID"]
jira_domain = os.environ["JIRA_DOMAIN"]
approval_topic = os.environ["APPROVAL_TOPIC_ARN"]
dimension = int(os.environ.get("EMBEDDING_DIMENSION", "1024"))
auth = AWS4Auth(credentials.access_key, credentials.secret_key, region, "aoss", session_token=credentials.token)

SAFE_COMMANDS = {
    "restart_service": "sudo systemctl restart {service}",
    "clear_disk_cache": "sudo sync && sudo sysctl -w vm.drop_caches=3"
}
SERVICE_RE = re.compile(r"^[a-zA-Z0-9_.@-]+$")

def embed(text):
    response = bedrock.invoke_model(modelId=embed_model,
        body=json.dumps({"inputText": text, "dimensions": dimension, "normalize": True}))
    return json.loads(response["body"].read())["embedding"]

def retrieve_runbooks(question, k=5):
    vector = embed(question)
    response = requests.post(f"https://{host}/{index}/_search", auth=auth, timeout=30,
        json={"size": k, "query": {"knn": {"embedding": {"vector": vector, "k": k}}}})
    response.raise_for_status()
    return [{"source": h["_source"].get("source"), "content": h["_source"].get("content")}
            for h in response.json()["hits"]["hits"]]

def jira_auth():
    secret = secrets.get_secret_value(SecretId=os.environ["JIRA_SECRET_NAME"])
    creds = json.loads(secret["SecretString"])
    return base64.b64encode(f"{creds['jira_user']}:{creds['jira_token']}".encode()).decode()

def jira_comment(issue_key, text):
    response = requests.post(f"{jira_domain}/rest/api/3/issue/{issue_key}/comment", timeout=30,
        headers={"Authorization": f"Basic {jira_auth()}", "Content-Type": "application/json"},
        json={"body": {"type": "doc", "version": 1, "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": text}]}]}})
    response.raise_for_status()
    return response.json()

def jira_add_label(issue_key, label):
    response = requests.post(f"{jira_domain}/rest/api/3/issue/{issue_key}", timeout=30,
        headers={"Authorization": f"Basic {jira_auth()}", "Content-Type": "application/json"},
        json={"update": {"labels": {"add": [{"name": label}]}}})
    response.raise_for_status()

def has_label(issue_key, label):
    search = requests.post(f"{jira_domain}/rest/api/3/search/jql", timeout=30,
        headers={"Authorization": f"Basic {jira_auth()}", "Content-Type": "application/json"},
        json={"jql": f'issue = {issue_key} AND labels = "{label}"',
              "maxResults": 1, "fields": ["summary"]})
    search.raise_for_status()
    return bool(search.json().get("issues"))

def ask_claude(alert, contexts):
    context_text = "\n\n---\n\n".join(f"Source: {c['source']}\n{c['content']}" for c in contexts)
    prompt = f"""You are an AIOps incident assistant.
Alert: {json.dumps(alert)}
Runbook context:
{context_text}
Return JSON only:
{{"likely_cause": "...", "checks": ["..."], "remediation_action": "restart_service|clear_disk_cache|none",
"service": "service-name-or-empty", "risk": "low|medium|high", "explanation": "...", "sources": ["..."]}}"""
    response = bedrock.invoke_model(modelId=llm_model, body=json.dumps({
        "anthropic_version": "bedrock-2023-05-31", "max_tokens": 1500,
        "messages": [{"role": "user", "content": prompt}]}))
    return json.loads(response["body"].read())["content"][0]["text"]

def lambda_handler(event, context):
    alert = event["alert"]
    jira_key = event.get("jira_key")
    if jira_key and has_label(jira_key, f"aiops-remediated-{jira_key}"):
        return {"statusCode": 200, "body": f"Already remediated: {jira_key}"}
    if jira_key and has_label(jira_key, f"aiops-approval-sent-{jira_key}"):
        return {"statusCode": 200, "body": f"Approval already requested: {jira_key}"}
    labels = alert.get("labels", {})
    severity = labels.get("severity", "unknown").lower()
    instance = labels.get("instance", "")
    question = f"{labels.get('alertname','')} on {instance}. {alert.get('annotations',{}).get('description','')}"
    contexts = retrieve_runbooks(question)
    analysis = ask_claude(alert, contexts)
    try:
        plan = json.loads(analysis)
    except Exception:
        plan = {"risk": "high", "remediation_action": "none", "explanation": analysis}
    risk = plan.get("risk", "high")
    action = plan.get("remediation_action", "none")
    service = plan.get("service", "")
    service_safe = bool(SERVICE_RE.match(service)) if service else True

    if severity in ("low", "info") and risk == "low" and action in SAFE_COMMANDS and service_safe:
        command = SAFE_COMMANDS[action].format(service=service)
        response = ssm.send_command(
            Targets=[{"Key": "InstanceIds", "Values": [instance]}] if instance.startswith("i-") else
                    [{"Key": "tag:Name", "Values": [instance]}],
            DocumentName="AWS-RunShellScript",
            Comment=f"AIOps automated remediation for {jira_key}",
            Parameters={"commands": [command]})
        command_id = response["Command"]["CommandId"]
        result = f"Automated remediation executed. SSM CommandId: {command_id}\n\n{analysis}"
        if jira_key:
            jira_comment(jira_key, result)
            jira_add_label(jira_key, f"aiops-remediated-{jira_key}")
    else:
        sns.publish(TopicArn=approval_topic,
            Subject=f"Approval needed: {jira_key} {labels.get('alertname','')}",
            Message=f"Incident {jira_key} requires approval.\n\n{analysis}\n\nApprove manually before SSM remediation.")
        result = f"Human approval required before remediation.\n\n{analysis}"
        if jira_key:
            # Post comment BEFORE marking approval-sent, so a failed comment is retried
            jira_comment(jira_key, result)
            jira_add_label(jira_key, f"aiops-approval-sent-{jira_key}")
    return {"statusCode": 200, "body": result}
