import json, os
import boto3
import requests
from requests_aws4auth import AWS4Auth

s3 = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime")
session = boto3.Session()
credentials = session.get_credentials()
region = session.region_name or "us-east-1"
host = os.environ["OPENSEARCH_HOST"].replace("https://", "").replace("http://", "").rstrip("/").replace("https://", "").replace("http://", "").rstrip("/")
index = os.environ["INDEX_NAME"]
model_id = os.environ["BEDROCK_MODEL_ID"]
dimension = int(os.environ.get("EMBEDDING_DIMENSION", "1024"))
auth = AWS4Auth(credentials.access_key, credentials.secret_key, region, "aoss", session_token=credentials.token)
doc_url = f"https://{host}/{index}/_doc"
delete_url = f"https://{host}/{index}/_delete_by_query"

def chunk_text(text, size=3500, overlap=300):
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return chunks

def embed(text):
    response = bedrock.invoke_model(modelId=model_id,
        body=json.dumps({"inputText": text, "dimensions": dimension, "normalize": True}))
    return json.loads(response["body"].read())["embedding"]

def delete_old_chunks(source):
    response = requests.post(delete_url, auth=auth, timeout=60, json={
        "query": {"term": {"source": source}}})
    response.raise_for_status()
    return response.json().get("deleted", 0)

def lambda_handler(event, context):
    bucket = event["Records"][0]["s3"]["bucket"]["name"]
    key = event["Records"][0]["s3"]["object"]["key"]
    if not key.lower().endswith((".txt", ".md")):
        return {"statusCode": 200, "body": f"Skipped: {key}"}
    source = f"s3://{bucket}/{key}"
    deleted = delete_old_chunks(source)
    obj = s3.get_object(Bucket=bucket, Key=key)
    text = obj["Body"].read().decode("utf-8")
    created = 0
    for chunk in chunk_text(text):
        doc = {"content": chunk, "embedding": embed(chunk), "title": key,
               "source": source, "doc_type": "runbook",
               "created_at": obj["LastModified"].isoformat()}
        response = requests.post(doc_url, auth=auth, json=doc,
            headers={"Content-Type": "application/json"}, timeout=30)
        response.raise_for_status()
        created += 1
    return {"statusCode": 200,
            "body": f"Ingested {created} chunks from {key} (deleted {deleted} old chunks)"}
