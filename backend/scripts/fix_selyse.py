import uuid, sys, boto3, requests, psycopg2
from botocore.config import Config as BotoCfg

TENANT_ID = "626cddcf-0e25-4b56-9b05-13ad6a95ec8a"
TREE_ID = "ffffffff-0007-4000-a000-000000000001"

s3 = boto3.client("s3", endpoint_url="http://localhost:7002",
    aws_access_key_id="minioadmin", aws_secret_access_key="minioadmin",
    region_name="us-east-1", config=BotoCfg(signature_version="s3v4"))

img = requests.get(
    "https://media.themoviedb.org/t/p/w300/nTeh6QYj4pQc4Jo0HHpDMpHpjJV.jpg",
    timeout=15,
    headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.themoviedb.org/"},
).content
print(f"Downloaded {len(img)} bytes", file=sys.stderr)

conn = psycopg2.connect("postgresql://postgres:postgres@localhost:7000/ourfamroots")
cur = conn.cursor()
cur.execute(
    "SELECT id, photo_url FROM persons WHERE tree_id=%s AND display_given_name='Selyse' AND display_surname='Florent'",
    (TREE_ID,),
)
row = cur.fetchone()
pid, old_url = str(row[0]), row[1]

if old_url:
    try:
        s3.delete_object(Bucket="ourfamroots-media", Key=old_url)
    except Exception:
        pass

new_key = f"tenants/{TENANT_ID}/trees/{TREE_ID}/persons/{pid}/photo/{uuid.uuid4()}.jpg"
s3.put_object(Bucket="ourfamroots-media", Key=new_key, Body=img, ContentType="image/jpeg")
cur.execute("UPDATE persons SET photo_url=%s WHERE id=%s AND tree_id=%s", (new_key, pid, TREE_ID))
conn.commit()
cur.close()
conn.close()
print("Selyse updated!", file=sys.stderr)
