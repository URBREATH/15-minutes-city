# storage_minio.py
import os
import glob
import tempfile
from io import BytesIO
import boto3
import pandas as pd
from botocore.exceptions import ClientError
from scripts.errors import raise_error

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------

def get_s3_client(access_key, secret_key, endpoint_url):
    return boto3.client(
        "s3",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        endpoint_url=endpoint_url,
        region_name="us-east-1",
    )


def minio_file_exists(
    bucket,
    object_key,
    endpoint_url,
    access_key,
    secret_key
):
    try:
        s3 = get_s3_client(access_key, secret_key, endpoint_url)

        s3.head_object(Bucket=bucket, Key=object_key)
        return True

    except ClientError:
        return False
    except Exception:
        return False
        
def minio_copy_prefix(
    bucket,
    source_prefix,
    dest_prefix,
    endpoint_url,
    access_key,
    secret_key
):
    s3 = get_s3_client(access_key, secret_key, endpoint_url)
    
    resp = s3.list_objects_v2(
        Bucket=bucket,
        Prefix=source_prefix
    )

    for obj in resp.get("Contents", []):
        source_key = obj["Key"]
        relative_key = source_key[len(source_prefix):].lstrip("/")
        dest_key = f"{dest_prefix}/{relative_key}"

        s3.copy_object(
            Bucket=bucket,
            CopySource={"Bucket": bucket, "Key": source_key},
            Key=dest_key
        )


def minio_list_poi_categories(
    bucket,
    prefix,
    endpoint_url,
    access_key,
    secret_key
):

    try:
        s3 = get_s3_client(access_key, secret_key, endpoint_url)

        resp = s3.list_objects_v2(
            Bucket=bucket,
            Prefix=prefix
        )

        categories = set()
        for obj in resp.get("Contents", []):
            key = obj["Key"]
            if key.endswith(".csv"):
                category = key.split("/")[-1].replace(".csv", "")
                categories.add(category)

        return categories

    except Exception as e:
        logger.warning(f"Cannot list POI categories from MinIO: {e}")
        return set()

KNOWN_MINIO_BUCKETS = {"urbreath-public-repo"}

def is_minio_path(path: str):
    if not path or "/" not in path:
        return False
    first = path.split("/", 1)[0]
    return first in KNOWN_MINIO_BUCKETS
    

def split_bucket_and_prefix(path: str):
    """
    Split a MinIO path of the form:
    bucket/prefix/...

    Returns:
        bucket (str)
        prefix (str)
    """
    if not path or "/" not in path:
        raise ValueError(f"Invalid MinIO path: {path}")

    parts = path.split("/", 1)
    bucket = parts[0]
    prefix = parts[1] if len(parts) > 1 else ""

    return bucket, prefix

def load_pois_from_minio(
    output_path_bbox,
    access_key,
    secret_key,
    endpoint_url
):
    bucket, prefix = split_bucket_and_prefix(output_path_bbox)

    s3 = get_s3_client(access_key, secret_key, endpoint_url)

    poi_prefixes = [
        f"{prefix}/osm_poi/",
        f"{prefix}/custom_poi/"
    ]

    pois = []
    categories = []

    for p in poi_prefixes:
        resp = s3.list_objects_v2(Bucket=bucket, Prefix=p)
        for obj in resp.get("Contents", []):
            key = obj["Key"]
            if key.endswith(".csv"):
                name = os.path.splitext(os.path.basename(key))[0]
                df = pd.read_csv(BytesIO(
                    s3.get_object(Bucket=bucket, Key=key)["Body"].read()
                ))
                pois.append(df)
                categories.append(name)

    return pois, categories

def split_path(path):
    parts = path.split("/", 1)
    bucket_name = parts[0]
    object_key = parts[1] if len(parts) > 1 else ""
    return bucket_name, object_key

def check_path_exists(path, err_code, endpoint_url, access_key, secret_key):
    if is_minio_path(path):
        bucket, key = split_path(path)

        if not key:
            raise_error(err_code, extra=path)
        

        if not minio_file_exists(
            bucket,
            key,
            endpoint_url,
            access_key,
            secret_key
        ):
            raise_error(err_code, extra=path)
    else:
        if not os.path.exists(path):
            raise_error(err_code, extra=path)
            
def get_folder(local_path, output_minio_path, access_key, secret_key, endpoint_url):

    if os.path.isfile(local_path):
        # solo file singolo
        filename = os.path.basename(local_path)
        filepath = f"{output_minio_path}/{filename}"
        upload_on_minio(local_path, filepath, access_key, secret_key, endpoint_url)
    else:
        # cartella: upload ricorsivo
        for root, dirs, files in os.walk(local_path):
            for file in files:
                local_file = os.path.join(root, file)

                rel_path = os.path.relpath(local_file, os.path.dirname(local_path))

                filepath = f"{output_minio_path}/{rel_path}"

                upload_on_minio(local_file, filepath, access_key, secret_key, endpoint_url)

            
            
def upload_on_minio(local_file, filepath, access_key, secret_key,endpoint_url):

    #bucket_name = "urbreath-public-repo" 

    bucket_name, filepath = split_path(filepath)
    s3 = get_s3_client(access_key, secret_key, endpoint_url)


    #logger.info(f"[INFO] Uploading {local_file} → s3://{bucket_name}/{filepath}")

    # ---- Upload file ----
    s3.upload_file(local_file, bucket_name, filepath)

    logger.info(f"[SUCCESS] Upload on MinIO completed!")