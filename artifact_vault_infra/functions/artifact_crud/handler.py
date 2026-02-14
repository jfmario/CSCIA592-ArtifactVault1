"""
Artifact CRUD Lambda – create, list, get, update, delete artifacts.
Uses placeholder owner_id until auth is implemented. Event-driven; wire to HTTP (e.g. API Gateway) later.
"""

import json
import os
import urllib.parse
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3

PRESIGNED_EXPIRY = 300  # seconds

OWNER_ID_PLACEHOLDER = "default-user"
TABLE_NAME = os.environ["ARTIFACTS_TABLE_NAME"]
BUCKET_NAME = os.environ["ARTIFACTS_BUCKET_NAME"]
dynamo = boto3.resource("dynamodb")
s3 = boto3.client("s3")

# CORS headers for API Gateway (browser / front-end)
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Credentials": "true",
}


def _owner_id(event: dict) -> str:
    """Resolve owner id from Cognito authorizer (sub) or placeholder."""
    ctx = event.get("requestContext") or {}
    auth = ctx.get("authorizer") or {}
    return (
        auth.get("ownerId")
        or auth.get("sub")
        or (auth.get("claims") or {}).get("sub")
        or OWNER_ID_PLACEHOLDER
    )


def _body(event: dict) -> dict:
    raw = event.get("body") or "{}"
    if isinstance(raw, dict):
        return raw
    return json.loads(raw)


def _query_params(event: dict) -> dict:
    return event.get("queryStringParameters") or {}


def _path_id(event: dict) -> str | None:
    params = event.get("pathParameters") or {}
    return params.get("id")


def _path_param(event: dict, name: str) -> str | None:
    params = event.get("pathParameters") or {}
    return params.get(name)


def _safe_filename(filename: str) -> str:
    """Use basename only to avoid path traversal; allow only printable chars."""
    base = os.path.basename(filename).strip()
    return "".join(c for c in base if c.isprintable() and c not in ("/", "\\")) or "file"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _item_to_artifact(item: dict) -> dict:
    """Map DynamoDB item to API-style artifact (id, title, description, tags, status, timestamps, owner_id, file_keys)."""
    return {
        "id": item.get("id"),
        "owner_id": item.get("owner_id"),
        "title": item.get("title"),
        "description": item.get("description"),
        "tags": item.get("tags", []),
        "status": item.get("status"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "file_keys": item.get("file_keys", []),
    }


def create(event: dict, owner_id: str) -> dict:
    body = _body(event)
    artifact_id = str(uuid.uuid4())
    now = _now()
    title = body.get("title", "").strip()
    description = (body.get("description") or "").strip()
    tags = body.get("tags")
    if tags is not None and not isinstance(tags, list):
        tags = [t.strip() for t in str(tags).split(",") if t.strip()]
    tags = tags or []
    status = (body.get("status") or "draft").strip()
    file_keys = body.get("file_keys")
    if file_keys is not None and not isinstance(file_keys, list):
        file_keys = [file_keys] if file_keys else []
    file_keys = file_keys or []

    item = {
        "owner_id": owner_id,
        "id": artifact_id,
        "title": title,
        "description": description,
        "tags": tags,
        "status": status,
        "created_at": now,
        "updated_at": now,
        "file_keys": file_keys,
    }
    table = dynamo.Table(TABLE_NAME)
    table.put_item(Item=item)
    return {"statusCode": 201, "body": json.dumps(_item_to_artifact(item))}


def list_artifacts(event: dict, owner_id: str) -> dict:
    params = _query_params(event)
    table = dynamo.Table(TABLE_NAME)
    q = table.query(KeyConditionExpression="owner_id = :oid", ExpressionAttributeValues={":oid": owner_id})
    items = q.get("Items", [])

    # Optional filters
    tags_filter = params.get("tags")
    if tags_filter:
        want = {t.strip() for t in str(tags_filter).split(",") if t.strip()}
        items = [i for i in items if want and set(i.get("tags", [])) & want]

    status_filter = params.get("status")
    if status_filter:
        items = [i for i in items if i.get("status") == status_filter.strip()]

    date_from = params.get("date_from", "").strip()
    date_to = params.get("date_to", "").strip()
    if date_from or date_to:
        items = [
            i
            for i in items
            if (not date_from or (i.get("created_at") or "") >= date_from)
            and (not date_to or (i.get("created_at") or "") <= date_to)
        ]

    artifacts = [_item_to_artifact(i) for i in items]
    return {"statusCode": 200, "body": json.dumps({"artifacts": artifacts})}


def get_artifact(event: dict, owner_id: str) -> dict:
    artifact_id = _path_id(event)
    if not artifact_id:
        return {"statusCode": 400, "body": json.dumps({"error": "Missing artifact id"})}
    table = dynamo.Table(TABLE_NAME)
    r = table.get_item(Key={"owner_id": owner_id, "id": artifact_id})
    item = r.get("Item")
    if not item:
        return {"statusCode": 404, "body": json.dumps({"error": "Artifact not found"})}
    return {"statusCode": 200, "body": json.dumps(_item_to_artifact(item))}


def update_artifact(event: dict, owner_id: str) -> dict:
    artifact_id = _path_id(event)
    if not artifact_id:
        return {"statusCode": 400, "body": json.dumps({"error": "Missing artifact id"})}
    body = _body(event)
    table = dynamo.Table(TABLE_NAME)
    r = table.get_item(Key={"owner_id": owner_id, "id": artifact_id})
    if not r.get("Item"):
        return {"statusCode": 404, "body": json.dumps({"error": "Artifact not found"})}

    now = _now()
    updates = ["updated_at = :now"]
    values = {":now": now}
    for key in ("title", "description", "status", "file_keys"):
        if key in body:
            if key == "tags":
                continue
            updates.append(f"{key} = :{key}")
            values[f":{key}"] = body[key]
    if "tags" in body:
        tags = body["tags"]
        if not isinstance(tags, list):
            tags = [t.strip() for t in str(tags).split(",") if t.strip()]
        updates.append("tags = :tags")
        values[":tags"] = tags

    resp = table.update_item(
        Key={"owner_id": owner_id, "id": artifact_id},
        UpdateExpression="SET " + ", ".join(updates),
        ExpressionAttributeValues=values,
        ReturnValues="ALL_NEW",
    )
    return {"statusCode": 200, "body": json.dumps(_item_to_artifact(resp["Attributes"]))}


def delete_artifact(event: dict, owner_id: str) -> dict:
    artifact_id = _path_id(event)
    if not artifact_id:
        return {"statusCode": 400, "body": json.dumps({"error": "Missing artifact id"})}
    table = dynamo.Table(TABLE_NAME)
    r = table.get_item(Key={"owner_id": owner_id, "id": artifact_id})
    item = r.get("Item")
    if not item:
        return {"statusCode": 404, "body": json.dumps({"error": "Artifact not found"})}

    prefix = f"{owner_id}/{artifact_id}/"
    file_keys = item.get("file_keys", [])
    for key in file_keys:
        if isinstance(key, str) and key.startswith(prefix):
            try:
                s3.delete_object(Bucket=BUCKET_NAME, Key=key)
            except Exception:
                pass
    try:
        list_result = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
        for obj in list_result.get("Contents", []):
            s3.delete_object(Bucket=BUCKET_NAME, Key=obj["Key"])
    except Exception:
        pass

    table.delete_item(Key={"owner_id": owner_id, "id": artifact_id})
    return {"statusCode": 204, "body": ""}


def get_upload_urls(event: dict, owner_id: str) -> dict:
    """Return presigned PUT URLs for one or more files; store keys in DynamoDB."""
    artifact_id = _path_id(event)
    if not artifact_id:
        return {"statusCode": 400, "body": json.dumps({"error": "Missing artifact id"})}
    body = _body(event)
    filenames = body.get("filenames")
    if not filenames:
        return {"statusCode": 400, "body": json.dumps({"error": "Missing filenames (array of strings)"})}
    if not isinstance(filenames, list):
        filenames = [str(filenames).strip()] if str(filenames).strip() else []
    filenames = [f for f in filenames if isinstance(f, str) and f.strip()]

    table = dynamo.Table(TABLE_NAME)
    r = table.get_item(Key={"owner_id": owner_id, "id": artifact_id})
    item = r.get("Item")
    if not item:
        return {"statusCode": 404, "body": json.dumps({"error": "Artifact not found"})}

    prefix = f"{owner_id}/{artifact_id}/"
    existing_keys = set(item.get("file_keys", []))
    upload_urls = []
    new_keys = list(existing_keys)

    for raw_name in filenames:
        safe_name = _safe_filename(raw_name)
        key = f"{prefix}{safe_name}"
        url = s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": BUCKET_NAME,
                "Key": key,
                "ContentType": "application/octet-stream",
            },
            ExpiresIn=PRESIGNED_EXPIRY,
        )
        upload_urls.append({"filename": safe_name, "key": key, "url": url, "expires_in": PRESIGNED_EXPIRY, "content_type": "application/octet-stream"})
        if key not in existing_keys:
            new_keys.append(key)

    if new_keys != list(existing_keys):
        now = _now()
        table.update_item(
            Key={"owner_id": owner_id, "id": artifact_id},
            UpdateExpression="SET file_keys = :keys, updated_at = :now",
            ExpressionAttributeValues={":keys": new_keys, ":now": now},
        )

    return {
        "statusCode": 200,
        "body": json.dumps({"upload_urls": upload_urls}),
    }


def get_download_url(event: dict, owner_id: str) -> dict:
    """Return a presigned GET URL for one file of the artifact."""
    artifact_id = _path_id(event)
    filename = _path_param(event, "filename")
    if not artifact_id or not filename:
        return {"statusCode": 400, "body": json.dumps({"error": "Missing artifact id or filename"})}
    filename = urllib.parse.unquote(filename)
    safe_name = _safe_filename(filename)
    prefix = f"{owner_id}/{artifact_id}/"
    built_key = f"{prefix}{safe_name}"

    params = _query_params(event)
    key_param = (params.get("key") or "").strip()
    if key_param:
        key_param = urllib.parse.unquote(key_param)
        if key_param.startswith(prefix) and key_param not in ("", prefix):
            built_key = key_param

    table = dynamo.Table(TABLE_NAME)
    r = table.get_item(Key={"owner_id": owner_id, "id": artifact_id})
    item = r.get("Item")
    if not item:
        return {"statusCode": 404, "body": json.dumps({"error": "Artifact not found"})}

    file_keys = list(item.get("file_keys", []))
    key = built_key
    if key not in file_keys:
        for k in file_keys:
            if not isinstance(k, str):
                continue
            if k == built_key or k.endswith("/" + safe_name) or os.path.basename(k) == safe_name:
                key = k
                break
        else:
            try:
                s3.head_object(Bucket=BUCKET_NAME, Key=built_key)
                key = built_key
            except Exception:
                return {"statusCode": 404, "body": json.dumps({"error": "File not found for this artifact"})}

    try:
        s3.head_object(Bucket=BUCKET_NAME, Key=key)
    except Exception as e:
        resp = getattr(e, "response", None)
        err_code = (resp.get("Error", {}).get("Code", "") if isinstance(resp, dict) else "") or ""
        if err_code in ("404", "NoSuchKey"):
            new_keys = [k for k in file_keys if k != key]
            if new_keys != file_keys:
                now = _now()
                table.update_item(
                    Key={"owner_id": owner_id, "id": artifact_id},
                    UpdateExpression="SET file_keys = :keys, updated_at = :now",
                    ExpressionAttributeValues={":keys": new_keys, ":now": now},
                )
            return {"statusCode": 404, "body": json.dumps({"error": "File not found (may not have been uploaded yet)"})}
        raise

    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET_NAME, "Key": key},
        ExpiresIn=PRESIGNED_EXPIRY,
    )
    return {
        "statusCode": 200,
        "body": json.dumps({"url": url, "filename": os.path.basename(key), "expires_in": PRESIGNED_EXPIRY}),
    }


def handler(event: dict, context: Any) -> dict:
    """Route by action (create, list, get, update, delete, get_upload_urls, get_download_url)."""
    action = event.get("action")
    if not action and event.get("httpMethod"):
        path = event.get("path", "") or event.get("resource", "")
        params = event.get("pathParameters") or {}
        pid = params.get("id")
        method = (event.get("httpMethod") or "").upper()
        if "upload-urls" in path and method == "POST" and pid:
            action = "get_upload_urls"
        elif params.get("filename") and method == "GET" and pid:
            action = "get_download_url"
        elif method == "POST" and "/artifacts" in path and not pid:
            action = "create"
        elif method == "GET" and pid and not params.get("filename"):
            action = "get"
        elif method == "GET":
            action = "list"
        elif method in ("PUT", "PATCH") and pid:
            action = "update"
        elif method == "DELETE" and pid:
            action = "delete"
    if not action:
        action = (event.get("httpMethod") or "").upper() == "POST" and "create" or "list"

    owner_id = _owner_id(event)
    actions = {
        "create": create,
        "list": list_artifacts,
        "get": get_artifact,
        "update": update_artifact,
        "delete": delete_artifact,
        "get_upload_urls": get_upload_urls,
        "get_download_url": get_download_url,
    }
    fn = actions.get((action or "").lower())
    if not fn:
        return {
            "statusCode": 400,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": f"Unknown action: {action}"}),
        }
    result = fn(event, owner_id)
    result.setdefault("headers", {}).update(CORS_HEADERS)
    return result
