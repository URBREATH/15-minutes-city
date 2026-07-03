# storage_minio.py
import os
from io import BytesIO

import boto3
import pandas as pd
from botocore.exceptions import ClientError

from scripts.errors import raise_error
from scripts.logger import logger
#Boto3 è il client AWS S3 
KNOWN_MINIO_BUCKETS = {"urbreath-public-repo"}


# Crea il client S3 che serve alle varie funzioni

# ---------- interni ----------
def _get_s3(access_key, secret_key, endpoint_url):
    return boto3.client(
        "s3",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        endpoint_url=endpoint_url,
        region_name="us-east-1",
    )


# Generatorw che elenca tutt i file remoti sotto un prefisso. suffix opzionale per filtrare (es. solo .tif).
def _list_keys(s3, bucket, prefix, suffix=None):
    resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
    for obj in resp.get("Contents", []):
        key = obj["Key"]
        if suffix is None or key.endswith(suffix):
            yield key


# ---------- API pubblica ----------
#Esposizione client all'esterno
def get_s3_client(access_key, secret_key, endpoint_url):
    return _get_s3(access_key, secret_key, endpoint_url)

#Divide "urbreath-public-repo/Parma/file.tif" in ("urbreath-public-repo", "Parma/file.tif") → bucket + key.
def is_minio_path(path):
    if not path or "/" not in path:
        return False
    return path.split("/", 1)[0] in KNOWN_MINIO_BUCKETS


def split_path(path):
    parts = path.split("/", 1)
    return parts[0], (parts[1] if len(parts) > 1 else "")


# ---------- existence ----------
# head_object è il modo standard per testare l'esistenza di un file su S3.
def minio_file_exists(bucket, object_key, endpoint_url, access_key, secret_key):
    try:
        s3 = _get_s3(access_key, secret_key, endpoint_url)
        s3.head_object(Bucket=bucket, Key=object_key)
        return True
    except Exception:
        return False


def check_path_exists(path, err_code, endpoint_url, access_key, secret_key):
    if is_minio_path(path):
        bucket, key = split_path(path)
        if not key or not minio_file_exists(bucket, key, endpoint_url, access_key, secret_key):
            raise_error(err_code, extra=path)
    elif not os.path.exists(path):
        raise_error(err_code, extra=path)


def check_folder_exists(path, err_code, endpoint_url, access_key, secret_key):
    bucket, prefix = split_path(path)
    if not prefix:
        raise_error(err_code, extra=path)
    try:
        s3 = _get_s3(access_key, secret_key, endpoint_url)
        prefix_norm = prefix.rstrip("/") + "/"
        resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix_norm, MaxKeys=1)
        if "Contents" not in resp:
            raise_error(err_code, extra=path)
    except Exception:
        raise_error(err_code, extra=path)


# ---------- low-level I/O (interni a sync_minio) ----------
def _upload_file(local_file, minio_path, access_key, secret_key, endpoint_url):
    bucket, key = split_path(minio_path)
    s3 = _get_s3(access_key, secret_key, endpoint_url)
    s3.upload_file(local_file, bucket, key)


def _upload_folder(local_folder, minio_path, access_key, secret_key, endpoint_url):
    base = os.path.dirname(local_folder)
    for root, _, files in os.walk(local_folder):
        for f in files:
            local_file = os.path.join(root, f)
            rel = os.path.relpath(local_file, base)
            _upload_file(local_file, f"{minio_path}/{rel}",
                         access_key, secret_key, endpoint_url)


def _download_file(minio_path, local_dest, access_key, secret_key, endpoint_url):
    bucket, key = split_path(minio_path)
    s3 = _get_s3(access_key, secret_key, endpoint_url)
    os.makedirs(os.path.dirname(local_dest) or ".", exist_ok=True)
    obj = s3.get_object(Bucket=bucket, Key=key)
    with open(local_dest, "wb") as f:
        f.write(obj["Body"].read())


def _download_folder(minio_path, local_dest, access_key, secret_key, endpoint_url):
    bucket, prefix = split_path(minio_path)
    prefix_n = prefix.rstrip("/") + "/"
    os.makedirs(local_dest, exist_ok=True)
    s3 = _get_s3(access_key, secret_key, endpoint_url)
    for key in _list_keys(s3, bucket, prefix_n):
        rel = key[len(prefix_n):]
        if not rel:
            continue
        dest = os.path.join(local_dest, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        obj = s3.get_object(Bucket=bucket, Key=key)
        with open(dest, "wb") as f:
            f.write(obj["Body"].read())


# ---------- UNICA API che usano i chiamanti ----------
def sync_minio(direction, local_path, minio_path,
               access_key, secret_key, endpoint_url):
    """
    direction = "upload" (locale -> MinIO) | "download" (MinIO -> locale)
    Funziona sia per file singoli che per cartelle.
    No-op se mancano credenziali o minio_path non valido.
    """
    if not (access_key and secret_key and endpoint_url):
        return
    if not minio_path or not is_minio_path(minio_path):
        return
#Decide automaticamente se è file o cartella e chiama l'helper giusto
    if direction == "upload":
        if not os.path.exists(local_path):
            logger.warning(f"sync_minio upload: missing {local_path}")
            return
        if os.path.isfile(local_path):
            _upload_file(local_path, minio_path,
                         access_key, secret_key, endpoint_url)
        else:
            _upload_folder(local_path, minio_path,
                           access_key, secret_key, endpoint_url)
        return

    if direction == "download":
        bucket, key = split_path(minio_path)
        s3 = _get_s3(access_key, secret_key, endpoint_url)
        try:
            s3.head_object(Bucket=bucket, Key=key)
            is_file = True
        except Exception:
            is_file = False

        if is_file:
            _download_file(minio_path, local_path,
                           access_key, secret_key, endpoint_url)
        else:
            _download_folder(minio_path, local_path,
                             access_key, secret_key, endpoint_url)
        return

    raise ValueError(f"sync_minio: invalid direction {direction!r}")
    
