import requests

print("--- QDRANT ---")
try:
    resp = requests.get("http://localhost:6333/collections", timeout=2)
    if resp.status_code == 200:
        collections = resp.json().get("result", {}).get("collections", [])
        if not collections:
            print("No collections found in Qdrant.")
        for c in collections:
            c_name = c["name"]
            c_info = requests.get(f"http://localhost:6333/collections/{c_name}").json()
            points = c_info.get("result", {}).get("points_count", 0)
            print(f"Collection '{c_name}': {points} points (vectors).")
    else:
        print(f"Failed to fetch collections: {resp.status_code} - {resp.text}")
except requests.exceptions.ConnectionError:
    print("Qdrant is not running on localhost:6333.")
except Exception as e:
    print(f"Error checking Qdrant: {e}")

print("\n--- MINIO ---")
import sys
import subprocess

try:
    import boto3
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "boto3", "-q"])
    import boto3

try:
    s3 = boto3.client(
        "s3",
        endpoint_url="http://localhost:9000",
        aws_access_key_id="admin",
        aws_secret_access_key="password123",
        region_name="us-east-1"
    )
    buckets = s3.list_buckets().get("Buckets", [])
    if not buckets:
        print("No buckets found in MinIO.")
    for b in buckets:
        b_name = b["Name"]
        objs = s3.list_objects_v2(Bucket=b_name).get("Contents", [])
        print(f"Bucket '{b_name}': {len(objs)} objects.")
        for o in objs[:5]:
            print(f"  - {o['Key']} ({o['Size']} bytes)")
        if len(objs) > 5:
            print(f"  - ... and {len(objs) - 5} more.")
except Exception as e:
    if "Connection refused" in str(e) or "Max retries exceeded" in str(e):
        print("MinIO is not running on localhost:9000.")
    else:
        print(f"Error checking MinIO: {e}")
