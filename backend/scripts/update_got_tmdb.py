"""
Update remaining GoT placeholder photos using TMDB actor headshots.
Downloads w300 images from media.themoviedb.org.
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
TMDB_BASE = "https://media.themoviedb.org/t/p/w300/"

# TMDB image ID → (display_given_name, display_surname) in our DB
TMDB_MAP = {
    # Characters that still have placeholder photos
    "ykGFuhZ5rJ2ngdjJzPQ50ll3CFz.jpg":  ("Rhaegar", "Targaryen"),
    "g6qewxM4EEg02HUTLUw9KGkLdNj.jpg":  ("Lyanna", "Stark"),
    "nTeh6QYj4pQc4Jo0HHpDMpHpjJI.jpg":  ("Selyse", "Florent"),
    "eC37Kmdo5YKNG2MyirCG4tWDxCS.jpg":   ("Brynden", "Tully"),
    "r82iduLbDcvN4VvwfWtkFn6Libn.jpg":   ("Roslin", "Frey"),
    "9lBukGiFVV0pKNwndaNhRQVnNmt.jpg":   ("Obara", "Sand"),
    "rfUrgDyHWHlrfvdxiVg8Vooudnd.jpg":   ("Nymeria", "Sand"),
    "54jpEVJpRi74YR019n3XytOF4lb.jpg":   ("Tyene", "Sand"),
    # Also upgrade these with higher quality TMDB actor headshots
    "hQpTeZDljWR2F9n1PcL7sXilwCE.jpg":   ("Jon", "Arryn"),
    "bILA1vPtP0fWWV9BmYVbkRhNaWB.jpg":   ("Shireen", "Baratheon"),
    "97wwITEknXx7MbQda71NegQvJtz.jpg":   ("Myrcella", "Baratheon"),
    "hGhAw2obMEOu1K0ed9b3jds9thf.jpg":   ("Edmure", "Tully"),
    "mlFYUmZycpRa7TGgDTfP0xanE1Q.jpg":   ("Lysa", "Tully"),
    "w8vKYmEiOua5stHlFrbbdBUd6fC.jpg":   ("Robin", "Arryn"),
    "1Ocb9v3h54beGVoJMm4w50UQhLf.jpg":   ("Benjen", "Stark"),
}


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

    for img_id, (given_name, surname) in TMDB_MAP.items():
        key = (given_name, surname)
        if key not in person_lookup:
            print(f"  [SKIP] Not in tree: {given_name} {surname}", file=sys.stderr)
            continue

        person_id, old_url = person_lookup[key]
        url = TMDB_BASE + img_id

        try:
            resp = requests.get(url, timeout=15, headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://www.themoviedb.org/",
            })
            resp.raise_for_status()
            img_data = resp.content
            if len(img_data) < 500:
                raise ValueError(f"Image too small ({len(img_data)} bytes)")
        except Exception as e:
            print(f"  [FAIL] {given_name} {surname}: {e}", file=sys.stderr)
            failed += 1
            continue

        if old_url and not old_url.startswith("preset:"):
            try:
                s3.delete_object(Bucket=S3_BUCKET, Key=old_url)
            except Exception:
                pass

        ext = img_id.rsplit(".", 1)[-1]
        new_key = f"tenants/{TENANT_ID}/trees/{TREE_ID}/persons/{person_id}/photo/{uuid.uuid4()}.{ext}"
        ct = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
        s3.put_object(Bucket=S3_BUCKET, Key=new_key, Body=img_data, ContentType=ct)

        cur.execute("UPDATE persons SET photo_url = %s WHERE id = %s AND tree_id = %s",
                    (new_key, person_id, TREE_ID))
        print(f"  [OK] {given_name} {surname} ({len(img_data)//1024}KB)", file=sys.stderr)
        updated += 1

    conn.commit()
    cur.close()
    conn.close()

    total_persons = len(person_lookup)
    cur2 = psycopg2.connect(DB_URL).cursor()
    cur2.execute("""
        SELECT COUNT(*) FROM persons
        WHERE tree_id = %s AND photo_url NOT LIKE '%%randomuser%%'
        AND photo_url IS NOT NULL AND is_deleted = false
    """, (TREE_ID,))
    cur2.close()

    print(f"\nDone: {updated} photos from TMDB, {failed} failed.", file=sys.stderr)


if __name__ == "__main__":
    main()
