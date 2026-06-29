"""
Update GoT profile photos using thronesapi.com character images.
Downloads from the API, uploads to MinIO, updates the DB.
"""
import sys
import uuid

import boto3
import requests
from botocore.config import Config as BotoCfg

TENANT_ID = "626cddcf-0e25-4b56-9b05-13ad6a95ec8a"
TREE_ID = "ffffffff-0007-4000-a000-000000000001"
DB_URL = "postgresql://postgres:postgres@localhost:7000/ourfamroots"
S3_ENDPOINT = "http://localhost:7002"
S3_BUCKET = "ourfamroots-media"

# API imageUrl → (display_given_name, display_surname) in our DB
# Handles spelling differences between API and our tree
API_TO_DB = {
    "daenerys.jpg":           ("Daenerys", "Targaryen"),
    "jon-snow.jpg":           ("Jon Snow", "Targaryen"),
    "arya-stark.jpg":         ("Arya", "Stark"),
    "sansa-stark.jpeg":       ("Sansa", "Stark"),
    "bran-stark.jpg":         ("Bran", "Stark"),
    "ned-stark.jpg":          ("Eddard", "Stark"),
    "robert-baratheon.jpeg":  ("Robert", "Baratheon"),
    "king-robert.jpg":        ("Robert", "Baratheon"),  # duplicate, same person
    "jaime-lannister.jpg":    ("Jaime", "Lannister"),
    "cersei.jpg":             ("Cersei", "Lannister"),
    "catelyn-stark.jpg":      ("Catelyn", "Tully"),
    "robb-stark.jpg":         ("Robb", "Stark"),
    "theon.jpg":              ("Theon", "Greyjoy"),
    "joffrey.jpg":            ("Joffrey", "Baratheon"),
    "tyrion-lannister.jpg":   ("Tyrion", "Lannister"),
    "stannis.jpg":            ("Stannis", "Baratheon"),
    "khal-drogo.jpg":         ("Khal Drogo", ""),
    "margaery-tyrell.jpg":    ("Margaery", "Tyrell"),
    "viserys-targaryan.jpg":  ("Viserys", "Targaryen"),
    "rickon.jpg":             ("Rickon", "Stark"),
    "roose-bolton.jpg":       ("Roose", "Bolton"),
    "tommen.jpg":             ("Tommen", "Baratheon"),
    "gendry.jpg":             ("Gendry", "Baratheon"),
    "ramsey-bolton.jpg":      ("Ramsay", "Bolton"),
    "talisa-stark.jpg":       ("Talisa", "Maegyr"),
    "red-viper.jpg":          ("Oberyn", "Martell"),
    "tywin-lannister.jpg":    ("Tywin", "Lannister"),
    "ellaria-sand.jpg":       ("Ellaria", "Sand"),
    "yara-greyjoy.jpg":       ("Yara", "Greyjoy"),
    "euron-greyjoy.jpg":      ("Euron", "Greyjoy"),
    "olenna-tyrell.jpg":      ("Olenna", "Tyrell"),
}

BASE_URL = "https://thronesapi.com/assets/images/"


def main():
    import psycopg2

    s3 = boto3.client("s3", endpoint_url=S3_ENDPOINT,
        aws_access_key_id="minioadmin", aws_secret_access_key="minioadmin",
        region_name="us-east-1", config=BotoCfg(signature_version="s3v4"))

    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False
    cur = conn.cursor()

    cur.execute("""
        SELECT id, display_given_name, display_surname, photo_url
        FROM persons WHERE tree_id = %s AND is_deleted = false
    """, (TREE_ID,))

    person_lookup = {}
    for pid, gn, sn, url in cur.fetchall():
        person_lookup[(gn, sn)] = (str(pid), url)

    updated = 0
    failed = 0

    for img_file, (given_name, surname) in API_TO_DB.items():
        key = (given_name, surname)
        if key not in person_lookup:
            print(f"  [SKIP] Not in tree: {given_name} {surname}", file=sys.stderr)
            continue

        person_id, old_url = person_lookup[key]
        url = BASE_URL + img_file

        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            img_data = resp.content
        except Exception as e:
            print(f"  [FAIL] {given_name} {surname}: {e}", file=sys.stderr)
            failed += 1
            continue

        # Delete old S3 object
        if old_url and not old_url.startswith("preset:"):
            try:
                s3.delete_object(Bucket=S3_BUCKET, Key=old_url)
            except Exception:
                pass

        ext = img_file.rsplit(".", 1)[-1]
        new_key = f"tenants/{TENANT_ID}/trees/{TREE_ID}/persons/{person_id}/photo/{uuid.uuid4()}.{ext}"
        content_type = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
        s3.put_object(Bucket=S3_BUCKET, Key=new_key, Body=img_data, ContentType=content_type)

        cur.execute("UPDATE persons SET photo_url = %s WHERE id = %s AND tree_id = %s",
                    (new_key, person_id, TREE_ID))

        print(f"  [OK] {given_name} {surname} ← {img_file}", file=sys.stderr)
        updated += 1

    conn.commit()
    cur.close()
    conn.close()

    print(f"\nDone: {updated} photos updated from thronesapi.com, {failed} failed.", file=sys.stderr)


if __name__ == "__main__":
    main()
