"""
Update Shah Dynasty placeholder photos with real Wikipedia/Wikimedia portraits.
"""
import sys
import time
import uuid

import boto3
import requests
from botocore.config import Config as BotoCfg

TENANT_ID = "626cddcf-0e25-4b56-9b05-13ad6a95ec8a"
TREE_ID = "11111111-7769-4000-a000-000000000001"
DB_URL = "postgresql://postgres:postgres@localhost:7000/ourfamroots"
S3_ENDPOINT = "http://localhost:7002"
S3_BUCKET = "ourfamroots-media"

WK = "https://upload.wikimedia.org/wikipedia/commons"

# Full-resolution URLs (no thumbnail sizing)
PHOTO_MAP = {
    f"{WK}/2/2a/Amar_Chitrakar_-_Portrait_of_King_Prithvi_Narayan_Shah.jpg":
        ("Prithvi Narayan", "Shah"),

    f"{WK}/e/eb/Amar_Chitrakar_-_Portrait_of_King_Rana_Bahadur_Shah.jpg":
        ("Rana Bahadur", "Shah"),

    f"{WK}/f/ff/Prithvi_Bir_Bikram_Shah_standing_%28cropped%29.png":
        ("Prithvi Bir Bikram", "Shah"),

    f"{WK}/3/35/King_Tribhuvan_%28cropped%29.png":
        ("Tribhuvan Bir Bikram", "Shah"),

    f"{WK}/4/47/King_Mahendra_of_Nepal.jpg":
        ("Mahendra Bir Bikram", "Shah"),

    f"{WK}/b/b3/Birendra_Bir_Bikram_Shah_c._1967_%28restoration%29.jpg":
        ("Birendra Bir Bikram", "Shah Dev"),

    f"{WK}/0/08/Gyanendra_01.jpg":
        ("Gyanendra Bir Bikram", "Shah Dev"),

    f"{WK}/0/08/Dipendra_Bir_Bikram_Shah_Dev_in_grey_suit_and_Dhaka_topi.jpg":
        ("Dipendra Bir Bikram", "Shah Dev"),

    f"{WK}/0/0f/The_Crown_Prince_of_Nepal_Shri_Paras_Bir_Bikram_Shah_Dev_in_New_Delhi_on_January_19%2C_2004_%28cropped%29.jpg":
        ("Paras Bir Bikram", "Shah Dev"),

    f"{WK}/1/1a/Aishwarya_1972.jpg":
        ("Aishwarya Rajya Lakshmi", "Devi Rana"),
}


def main():
    import psycopg2

    s3 = boto3.client("s3", endpoint_url=S3_ENDPOINT,
        aws_access_key_id="minioadmin", aws_secret_access_key="minioadmin",
        region_name="us-east-1", config=BotoCfg(signature_version="s3v4"))

    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False
    cur = conn.cursor()

    cur.execute("""SELECT id, display_given_name, display_surname, photo_url
        FROM persons WHERE tree_id = %s AND is_deleted = false""", (TREE_ID,))

    lookup = {}
    for pid, gn, sn, url in cur.fetchall():
        lookup[(gn, sn)] = (str(pid), url)

    updated = 0
    for url, (gn, sn) in PHOTO_MAP.items():
        if (gn, sn) not in lookup:
            print(f"  [SKIP] Not found: {gn} {sn}", file=sys.stderr)
            continue

        person_id, old_url = lookup[(gn, sn)]
        time.sleep(3)
        try:
            resp = requests.get(url, timeout=20,
                headers={"User-Agent": "Mozilla/5.0 (compatible; FamilyTreeBot/1.0; mailto:nirajbjk@gmail.com)"})
            resp.raise_for_status()
            img = resp.content
            if len(img) < 500:
                raise ValueError(f"Too small: {len(img)} bytes")
        except Exception as e:
            print(f"  [FAIL] {gn} {sn}: {e}", file=sys.stderr)
            continue

        if old_url and not old_url.startswith("preset:"):
            try:
                s3.delete_object(Bucket=S3_BUCKET, Key=old_url)
            except Exception:
                pass

        ext = "jpg" if url.endswith(".jpg") else "png"
        new_key = f"tenants/{TENANT_ID}/trees/{TREE_ID}/persons/{person_id}/photo/{uuid.uuid4()}.{ext}"
        ct = "image/jpeg" if ext == "jpg" else "image/png"
        s3.put_object(Bucket=S3_BUCKET, Key=new_key, Body=img, ContentType=ct)
        cur.execute("UPDATE persons SET photo_url=%s WHERE id=%s AND tree_id=%s",
                    (new_key, person_id, TREE_ID))
        print(f"  [OK] {gn} {sn} ({len(img)//1024}KB)", file=sys.stderr)
        updated += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"\nDone: {updated} photos updated from Wikipedia.", file=sys.stderr)


if __name__ == "__main__":
    main()
