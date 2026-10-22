import os, json, hmac

def lambda_handler(event, context):
    headers = event.get("headers") or {}
    token = headers.get("x-aiops-token") or headers.get("X-Aiops-Token")
    expected = os.environ.get("AIOPS_WEBHOOK_TOKEN")
    if token and expected and hmac.compare_digest(token, expected):
        return {"isAuthorized": True, "context": {}}
    return {"isAuthorized": False}
