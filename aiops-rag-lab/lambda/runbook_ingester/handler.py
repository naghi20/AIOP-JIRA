import json
import os
from urllib.parse import unquote_plus, urlparse

import boto3
import requests
from botocore.config import Config
from requests_aws4auth import AWS4Auth


# These are intentionally different:
# - Titan embeddings: Oregon
# - S3/Lambda/OpenSearch: Virginia
EMBEDDING_REGION = os.environ.get("EMBEDDING_REGION", "us-west-2")
OPENSEARCH_REGION = os.environ.get("OPENSEARCH_REGION", "us-east-1")

session = boto3.Session()
s3 = session.client("s3")

bedrock = session.client(
    "bedrock-runtime",
    region_name=EMBEDDING_REGION,
    config=Config(
        connect_timeout=5,
        read_timeout=30,
        retries={
            "mode": "standard",
            "total_max_attempts": 4,
        },
    ),
)

endpoint = os.environ["OPENSEARCH_HOST"].strip().rstrip("/")
if "://" not in endpoint:
    endpoint = f"https://{endpoint}"

parsed_endpoint = urlparse(endpoint)
if (
    parsed_endpoint.scheme != "https"
    or not parsed_endpoint.netloc
    or parsed_endpoint.path not in ("", "/")
):
    raise ValueError("OPENSEARCH_HOST must be an HTTPS collection endpoint")

index = os.environ["INDEX_NAME"]
model_id = os.environ["BEDROCK_MODEL_ID"]
dimension = int(os.environ.get("EMBEDDING_DIMENSION", "1024"))

if dimension not in (256, 512, 1024):
    raise ValueError("Unsupported Titan V2 embedding dimension")

doc_url = f"{endpoint}/{index}/_doc"


def log(event_name, **fields):
    print(json.dumps({"event": event_name, **fields}))


def opensearch_auth():
    # Build the signer from the current credentials for each request.
    credentials = session.get_credentials()
    if credentials is None:
        raise RuntimeError("No AWS credentials available")

    frozen = credentials.get_frozen_credentials()

    return AWS4Auth(
        frozen.access_key,
        frozen.secret_key,
        OPENSEARCH_REGION,
        "aoss",
        session_token=frozen.token,
    )


def chunk_text(text, size=3500, overlap=300):
    if not 0 <= overlap < size:
        raise ValueError("Overlap must be smaller than chunk size")

    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        yield text[start:end]

        if end == len(text):
            break

        start = end - overlap


def embed(text):
    log(
        "embedding_request",
        region=bedrock.meta.region_name,
        endpoint=bedrock.meta.endpoint_url,
        model=model_id,
        characters=len(text),
        requested_dimensions=dimension,
    )

    response = bedrock.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "inputText": text,
            "dimensions": dimension,
            "normalize": True,
        }),
    )

    stream = response["body"]
    try:
        result = json.loads(stream.read())
    finally:
        stream.close()

    vector = result["embedding"]

    if len(vector) != dimension:
        raise ValueError(
            f"Expected {dimension} dimensions, received {len(vector)}"
        )

    log(
        "embedding_success",
        dimensions=len(vector),
        input_tokens=result.get("inputTextTokenCount"),
        request_id=response.get("ResponseMetadata", {}).get("RequestId"),
    )

    return vector


def index_document(document):
    response = requests.post(
        doc_url,
        auth=opensearch_auth(),
        json=document,
        headers={"Content-Type": "application/json"},
        timeout=(5, 30),
    )

    if not response.ok:
        log(
            "opensearch_index_failed",
            status=response.status_code,
            response_body=response.text[:1500],
        )

    response.raise_for_status()

    result = response.json()
    log(
        "document_indexed",
        document_id=result.get("_id"),
        result=result.get("result"),
    )


def lambda_handler(event, context):
    records = event.get("Records")
    if not isinstance(records, list) or not records:
        raise ValueError("Expected a non-empty S3 Records array")

    log(
        "ingestion_started",
        request_id=getattr(context, "aws_request_id", None),
        records=len(records),
        embedding_region=EMBEDDING_REGION,
        opensearch_region=OPENSEARCH_REGION,
        model=model_id,
    )

    results = []

    for record in records:
        if record.get("eventSource") != "aws:s3":
            raise ValueError("Expected an S3 event")

        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])

        if not key.startswith("runbooks/") or not key.lower().endswith(
            (".txt", ".md")
        ):
            log("object_skipped", bucket=bucket, key=key)
            continue

        source = f"s3://{bucket}/{key}"

        obj = s3.get_object(Bucket=bucket, Key=key)
        stream = obj["Body"]
        try:
            text = stream.read().decode("utf-8-sig")
        finally:
            stream.close()

        if not text.strip():
            raise ValueError(f"Runbook is empty: {source}")

        created = 0

        for chunk_number, chunk in enumerate(chunk_text(text)):
            vector = embed(chunk)

            document = {
                "content": chunk,
                "embedding": vector,
                "title": key,
                "source": source,
                "doc_type": "runbook",
                "created_at": obj["LastModified"].isoformat(),
            }

            index_document(document)
            created += 1

            log(
                "chunk_ingested",
                source=source,
                chunk_number=chunk_number,
            )

        log(
            "runbook_ingested",
            source=source,
            chunks_created=created,
            cleanup_performed=False,
        )

        results.append({
            "source": source,
            "chunks_created": created,
        })

    return {
        "statusCode": 200,
        "body": json.dumps({"results": results}),
    }