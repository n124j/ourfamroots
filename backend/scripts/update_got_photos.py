"""
Replace GoT placeholder profile photos with real character images.
Maps local image files to characters by (given_name, surname).
"""
import uuid
import sys

import boto3
from botocore.config import Config as BotoCfg

TENANT_ID = "626cddcf-0e25-4b56-9b05-13ad6a95ec8a"
TREE_ID = "ffffffff-0007-4000-a000-000000000001"
DB_URL = "postgresql://postgres:postgres@localhost:7000/ourfamroots"
S3_ENDPOINT = "http://localhost:7002"
S3_BUCKET = "ourfamroots-media"

PHOTO_DIR = r"C:\Users\newro\Downloads\Game of Thrones pictures"

# filename → (given_name, surname) in the database
PHOTO_MAP = {
    "Screenshot 2026-06-08 000014.jpg": ("Aerys II", "Targaryen"),
    "Screenshot 2026-06-08 000446.jpg": ("Jon", "Arryn"),
    "Screenshot 2026-06-08 000608.jpg": ("Viserys", "Targaryen"),
    "Screenshot 2026-06-08 000636.jpg": ("Robert", "Baratheon"),
    "Screenshot 2026-06-08 000657.jpg": ("Daenerys", "Targaryen"),
    "Screenshot 2026-06-08 000813.jpg": ("Edmure", "Tully"),
    "Screenshot 2026-06-08 000832.jpg": ("Lysa", "Tully"),
    "Screenshot 2026-06-08 000942.jpg": ("Robin", "Arryn"),
    "Screenshot 2026-06-08 001338.jpg": ("Sansa", "Stark"),
    "Screenshot 2026-06-08 001350.jpg": ("Talisa", "Maegyr"),
    "Screenshot 2026-06-08 001400.jpg": ("Robb", "Stark"),
    "Screenshot 2026-06-08 001412.jpg": ("Arya", "Stark"),
    "Screenshot 2026-06-08 001425.jpg": ("Bran", "Stark"),
    "Screenshot 2026-06-08 001440.jpg": ("Rickon", "Stark"),
    "Screenshot 2026-06-08 001500.jpg": ("Ramsay", "Bolton"),
    "Screenshot 2026-06-08 001512.jpg": ("Roose", "Bolton"),
    "Screenshot 2026-06-08 001654.jpg": ("Catelyn", "Tully"),
    "Screenshot 2026-06-08 001726.jpg": ("Eddard", "Stark"),
    "Screenshot 2026-06-08 002001.jpg": ("Walder", "Frey"),
    "Screenshot 2026-06-08 002044.jpg": ("Benjen", "Stark"),
    "Screenshot 2026-06-08 002104.jpg": ("Brandon", "Stark"),
    "Screenshot 2026-06-08 003145.jpg": ("Stannis", "Baratheon"),
    "Screenshot 2026-06-08 003158.jpg": ("Renly", "Baratheon"),
    "Screenshot 2026-06-08 003215.jpg": ("Shireen", "Baratheon"),
    "Screenshot 2026-06-08 003413.jpg": ("Joffrey", "Baratheon"),
    "Screenshot 2026-06-08 003425.jpg": ("Myrcella", "Baratheon"),
    "Screenshot 2026-06-08 003435.jpg": ("Tommen", "Baratheon"),
    "Screenshot 2026-06-08 003449.jpg": ("Jaime", "Lannister"),
    "Screenshot 2026-06-08 003500.jpg": ("Cersei", "Lannister"),
    "Screenshot 2026-06-08 003510.jpg": ("Tyrion", "Lannister"),
    "Screenshot 2026-06-08 003523.jpg": ("Tywin", "Lannister"),
    "Screenshot 2026-06-08 005344.jpg": ("Margaery", "Tyrell"),
    "Screenshot 2026-06-08 005401.jpg": ("Loras", "Tyrell"),
    "Screenshot 2026-06-08 005416.jpg": ("Trystane", "Martell"),
    "Screenshot 2026-06-08 005427.jpg": ("Mace", "Tyrell"),
    "Screenshot 2026-06-08 005440.jpg": ("Doran", "Martell"),
    "Screenshot 2026-06-08 005453.jpg": ("Oberyn", "Martell"),
    "Screenshot 2026-06-08 005505.jpg": ("Olenna", "Tyrell"),
    "Screenshot 2026-06-08 010452.jpg": ("Theon", "Greyjoy"),
    "Screenshot 2026-06-08 010505.jpg": ("Balon", "Greyjoy"),
    # Ned on Iron Throne — use as Ned's profile
    "61+5mMtkPbL._AC_SL1024_.jpg": ("Eddard", "Stark"),
}

# Prefer the better portrait for Ned (001726 is a close-up headshot)
# 61+5mMtkPbL is the poster — skip it, use 001726 instead
# Remove the poster duplicate for Ned
del PHOTO_MAP["61+5mMtkPbL._AC_SL1024_.jpg"]


def main():
    import os
    import psycopg2

    s3 = boto3.client("s3", endpoint_url=S3_ENDPOINT,
        aws_access_key_id="minioadmin", aws_secret_access_key="minioadmin",
        region_name="us-east-1", config=BotoCfg(signature_version="s3v4"))

    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False
    cur = conn.cursor()

    # Load all persons in this tree
    cur.execute("""
        SELECT id, display_given_name, display_surname, photo_url
        FROM persons WHERE tree_id = %s AND is_deleted = false
    """, (TREE_ID,))
    rows = cur.fetchall()

    person_lookup = {}
    for pid, gn, sn, existing_url in rows:
        person_lookup[(gn, sn)] = (str(pid), existing_url)

    updated = 0
    skipped = 0

    for filename, (given_name, surname) in PHOTO_MAP.items():
        filepath = os.path.join(PHOTO_DIR, filename)
        if not os.path.exists(filepath):
            print(f"  [SKIP] File not found: {filename}", file=sys.stderr)
            skipped += 1
            continue

        key = (given_name, surname)
        if key not in person_lookup:
            print(f"  [SKIP] Person not found: {given_name} {surname}", file=sys.stderr)
            skipped += 1
            continue

        person_id, old_url = person_lookup[key]

        # Delete old photo from S3 if it exists
        if old_url and not old_url.startswith("preset:"):
            try:
                s3.delete_object(Bucket=S3_BUCKET, Key=old_url)
            except Exception:
                pass

        # Upload new photo
        with open(filepath, "rb") as f:
            data = f.read()

        new_photo_id = str(uuid.uuid4())
        new_key = f"tenants/{TENANT_ID}/trees/{TREE_ID}/persons/{person_id}/photo/{new_photo_id}.jpg"
        s3.put_object(Bucket=S3_BUCKET, Key=new_key, Body=data, ContentType="image/jpeg")

        # Update DB
        cur.execute("""
            UPDATE persons SET photo_url = %s
            WHERE id = %s AND tree_id = %s
        """, (new_key, person_id, TREE_ID))

        print(f"  [OK] {given_name} {surname}", file=sys.stderr)
        updated += 1

    conn.commit()
    cur.close()
    conn.close()

    print(f"\nDone: {updated} photos replaced, {skipped} skipped.", file=sys.stderr)
    print(f"Remaining {len(rows) - updated} persons keep placeholder photos.", file=sys.stderr)


if __name__ == "__main__":
    main()
