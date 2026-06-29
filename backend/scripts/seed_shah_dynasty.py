"""
Seed the Shah Dynasty of Nepal — Prithvi Narayan Shah to current descendants.
13 generations spanning 1723-2025.

Sources: public genealogical records, Wikipedia, Nepali royal history.
Photos: randomuser.me placeholders (replaced by real ones in a second pass if available).
"""
from __future__ import annotations

import io
import random
import sys
import uuid
from dataclasses import dataclass, field
from typing import Optional

import boto3
import requests
from botocore.config import Config as BotoCfg
from PIL import Image

random.seed(1769)

TENANT_ID = "626cddcf-0e25-4b56-9b05-13ad6a95ec8a"
TREE_ID = "11111111-7769-4000-a000-000000000001"
TREE_NAME = "Shah Dynasty of Nepal"
USER_ID = "5142fcf9-366f-47b5-8630-6086608fefbb"

DB_URL = "postgresql://postgres:postgres@localhost:7000/ourfamroots"
S3_ENDPOINT = "http://localhost:7002"
S3_BUCKET = "ourfamroots-media"
S3_KEY = "minioadmin"
S3_SECRET = "minioadmin"

KTM = "Kathmandu"
GRK = "Gorkha"
NPL = "Nepal"


@dataclass
class Person:
    id: str
    given_name: str
    surname: str
    sex: str
    birth_year: int
    death_year: Optional[int] = None
    is_living: bool = True
    born_city: Optional[str] = None
    born_country: str = NPL
    died_city: Optional[str] = None
    died_country: Optional[str] = None
    notes: Optional[str] = None
    generation: int = 1
    photo_s3_key: Optional[str] = None
    gallery_keys: list[tuple[str, str, str]] = field(default_factory=list)


@dataclass
class FG:
    id: str
    union_type: str
    parent_ids: list[str] = field(default_factory=list)
    children: list[tuple[str, str]] = field(default_factory=list)
    is_divorced: bool = False
    union_year: Optional[int] = None
    union_end_year: Optional[int] = None


def uid(): return str(uuid.uuid4())
persons: dict[str, Person] = {}
fgs: list[FG] = []

def P(**kw) -> Person:
    kw.setdefault("id", uid())
    p = Person(**kw)
    persons[p.id] = p
    return p

def marry(a, b, **kw) -> FG:
    kw.setdefault("id", uid())
    kw.setdefault("union_type", "MARRIAGE")
    f = FG(parent_ids=[a, b], **kw)
    fgs.append(f)
    return f

def ch(fg, cid, pt="BIOLOGICAL"):
    fg.children.append((cid, pt))

# ═══════════════════════════════════════════════════════════════════════
# GENERATION 1 — Ancestors of Prithvi Narayan Shah
# ═══════════════════════════════════════════════════════════════════════

nara_bhupal = P(given_name="Nara Bhupal", surname="Shah", sex="MALE",
    birth_year=1694, death_year=1743, is_living=False,
    born_city=GRK, notes="King of Gorkha. Father of Prithvi Narayan Shah.", generation=1)

kaushalyavati = P(given_name="Kaushalyavati", surname="Devi", sex="FEMALE",
    birth_year=1700, death_year=1760, is_living=False,
    born_city=GRK, generation=1)

fg_nara = marry(nara_bhupal.id, kaushalyavati.id, union_year=1718)

# ═══════════════════════════════════════════════════════════════════════
# GENERATION 2 — Prithvi Narayan Shah (The Great Unifier)
# ═══════════════════════════════════════════════════════════════════════

prithvi = P(given_name="Prithvi Narayan", surname="Shah", sex="MALE",
    birth_year=1723, death_year=1775, is_living=False,
    born_city=GRK, died_city="Nuwakot",
    notes="Founder of modern Nepal. Unified the kingdoms in 1768.", generation=2)
ch(fg_nara, prithvi.id)

narendra_laxmi = P(given_name="Narendra Rajya Lakshmi", surname="Devi", sex="FEMALE",
    birth_year=1730, death_year=1785, is_living=False,
    born_city="Makwanpur",
    notes="Queen consort. Regent after Prithvi Narayan's death.", generation=2)

indra_kumari = P(given_name="Indra Kumari", surname="Devi", sex="FEMALE",
    birth_year=1735, death_year=1795, is_living=False,
    born_city=GRK, generation=2)

fg_prithvi1 = marry(prithvi.id, narendra_laxmi.id, union_year=1740)
fg_prithvi2 = marry(prithvi.id, indra_kumari.id, union_year=1748)

# ═══════════════════════════════════════════════════════════════════════
# GENERATION 3 — Sons of Prithvi Narayan
# ═══════════════════════════════════════════════════════════════════════

pratap = P(given_name="Pratap Singh", surname="Shah", sex="MALE",
    birth_year=1751, death_year=1777, is_living=False,
    born_city=GRK, died_city=KTM,
    notes="Second King of unified Nepal. Died at 26.", generation=3)
ch(fg_prithvi1, pratap.id)

bahadur = P(given_name="Bahadur", surname="Shah", sex="MALE",
    birth_year=1757, death_year=1797, is_living=False,
    born_city=GRK, died_city=KTM,
    notes="Regent of Nepal. Expanded the kingdom.", generation=3)
ch(fg_prithvi1, bahadur.id)

rajendra_laxmi_wife = P(given_name="Rajendra Rajya Lakshmi", surname="Devi", sex="FEMALE",
    birth_year=1754, death_year=1785, is_living=False,
    born_city=KTM,
    notes="Regent after Pratap Singh's death.", generation=3)

fg_pratap = marry(pratap.id, rajendra_laxmi_wife.id, union_year=1773)

# ═══════════════════════════════════════════════════════════════════════
# GENERATION 4 — Rana Bahadur Shah
# ═══════════════════════════════════════════════════════════════════════

rana_bahadur = P(given_name="Rana Bahadur", surname="Shah", sex="MALE",
    birth_year=1775, death_year=1806, is_living=False,
    born_city=KTM, died_city=KTM,
    notes="Third King. Abdicated, then assassinated.", generation=4)
ch(fg_pratap, rana_bahadur.id)

kantavati = P(given_name="Kantavati", surname="Devi", sex="FEMALE",
    birth_year=1780, death_year=1805, is_living=False,
    born_city=KTM, generation=4)

fg_rana = marry(rana_bahadur.id, kantavati.id, union_year=1794)

# ═══════════════════════════════════════════════════════════════════════
# GENERATION 5 — Girvan Yuddha
# ═══════════════════════════════════════════════════════════════════════

girvan = P(given_name="Girvan Yuddha Bikram", surname="Shah", sex="MALE",
    birth_year=1797, death_year=1816, is_living=False,
    born_city=KTM, died_city=KTM,
    notes="Became king at age 2. Died at 19.", generation=5)
ch(fg_rana, girvan.id)

gorakshya = P(given_name="Gorakshya Rajya Lakshmi", surname="Devi", sex="FEMALE",
    birth_year=1800, death_year=1835, is_living=False,
    born_city=KTM, generation=5)

fg_girvan = marry(girvan.id, gorakshya.id, union_year=1812)

# ═══════════════════════════════════════════════════════════════════════
# GENERATION 6 — Rajendra Bikram Shah
# ═══════════════════════════════════════════════════════════════════════

rajendra = P(given_name="Rajendra Bikram", surname="Shah", sex="MALE",
    birth_year=1813, death_year=1881, is_living=False,
    born_city=KTM, died_city="Varanasi", died_country="India",
    notes="Deposed by Jung Bahadur Rana. Exiled to India.", generation=6)
ch(fg_girvan, rajendra.id)

samrajya = P(given_name="Samrajya Lakshmi", surname="Devi", sex="FEMALE",
    birth_year=1815, death_year=1850, is_living=False,
    born_city=KTM, generation=6)

fg_rajendra = marry(rajendra.id, samrajya.id, union_year=1828)

# ═══════════════════════════════════════════════════════════════════════
# GENERATION 7 — Surendra Bikram Shah
# ═══════════════════════════════════════════════════════════════════════

surendra = P(given_name="Surendra Bikram", surname="Shah", sex="MALE",
    birth_year=1829, death_year=1881, is_living=False,
    born_city=KTM, died_city=KTM,
    notes="Figurehead king during Rana rule.", generation=7)
ch(fg_rajendra, surendra.id)

trailokya_queen = P(given_name="Trailokya Rajya Lakshmi", surname="Devi", sex="FEMALE",
    birth_year=1832, death_year=1882, is_living=False,
    born_city=KTM, generation=7)

fg_surendra = marry(surendra.id, trailokya_queen.id, union_year=1845)

# ═══════════════════════════════════════════════════════════════════════
# GENERATION 8 — Trailokya Bikram Shah
# ═══════════════════════════════════════════════════════════════════════

trailokya = P(given_name="Trailokya Bir Bikram", surname="Shah", sex="MALE",
    birth_year=1847, death_year=1878, is_living=False,
    born_city=KTM, died_city=KTM,
    notes="Crown Prince. Died before his father.", generation=8)
ch(fg_surendra, trailokya.id)

laxmi_devi = P(given_name="Laxmi", surname="Devi", sex="FEMALE",
    birth_year=1850, death_year=1900, is_living=False,
    born_city=KTM, generation=8)

fg_trailokya = marry(trailokya.id, laxmi_devi.id, union_year=1870)

# ═══════════════════════════════════════════════════════════════════════
# GENERATION 9 — Prithvi Bir Bikram Shah
# ═══════════════════════════════════════════════════════════════════════

prithvi_bir = P(given_name="Prithvi Bir Bikram", surname="Shah", sex="MALE",
    birth_year=1875, death_year=1911, is_living=False,
    born_city=KTM, died_city=KTM,
    notes="King during the Rana oligarchy. Figurehead ruler.", generation=9)
ch(fg_trailokya, prithvi_bir.id)

divyeshwari = P(given_name="Divyeshwari Rajya Lakshmi", surname="Devi", sex="FEMALE",
    birth_year=1878, death_year=1930, is_living=False,
    born_city=KTM, generation=9)

fg_prithvi_bir = marry(prithvi_bir.id, divyeshwari.id, union_year=1893)

# ═══════════════════════════════════════════════════════════════════════
# GENERATION 10 — Tribhuvan
# ═══════════════════════════════════════════════════════════════════════

tribhuvan = P(given_name="Tribhuvan Bir Bikram", surname="Shah", sex="MALE",
    birth_year=1906, death_year=1955, is_living=False,
    born_city=KTM, died_city="Zurich", died_country="Switzerland",
    notes="Overthrew the Rana regime in 1951. Father of democracy.", generation=10)
ch(fg_prithvi_bir, tribhuvan.id)

kanti = P(given_name="Kanti Rajya Lakshmi", surname="Devi", sex="FEMALE",
    birth_year=1906, death_year=1947, is_living=False,
    born_city=KTM,
    notes="First queen of Tribhuvan.", generation=10)

ishwari = P(given_name="Ishwari Rajya Lakshmi", surname="Devi", sex="FEMALE",
    birth_year=1912, death_year=1952, is_living=False,
    born_city=KTM,
    notes="Second queen of Tribhuvan.", generation=10)

fg_tribhuvan1 = marry(tribhuvan.id, kanti.id, union_year=1919)
fg_tribhuvan2 = marry(tribhuvan.id, ishwari.id, union_year=1925)

# ═══════════════════════════════════════════════════════════════════════
# GENERATION 11 — Mahendra & brothers
# ═══════════════════════════════════════════════════════════════════════

mahendra = P(given_name="Mahendra Bir Bikram", surname="Shah", sex="MALE",
    birth_year=1920, death_year=1972, is_living=False,
    born_city=KTM, died_city=KTM,
    notes="Introduced the Panchayat system. Modernized Nepal.", generation=11)
ch(fg_tribhuvan1, mahendra.id)

himalaya = P(given_name="Himalaya Bir Bikram", surname="Shah", sex="MALE",
    birth_year=1921, death_year=2019, is_living=False,
    born_city=KTM,
    notes="Prince. Mahendra's brother.", generation=11)
ch(fg_tribhuvan1, himalaya.id)

basundhara = P(given_name="Basundhara Bir Bikram", surname="Shah", sex="MALE",
    birth_year=1925, death_year=2015, is_living=False,
    born_city=KTM,
    notes="Prince. Mahendra's brother.", generation=11)
ch(fg_tribhuvan1, basundhara.id)

# Mahendra's wives
indra_queen = P(given_name="Indra Rajya Lakshmi", surname="Devi", sex="FEMALE",
    birth_year=1928, death_year=1950, is_living=False,
    born_city=KTM, died_city=KTM,
    notes="First queen. Died young at 22.", generation=11)

ratna = P(given_name="Ratna Rajya Lakshmi", surname="Devi", sex="FEMALE",
    birth_year=1928, death_year=2019, is_living=False,
    born_city=KTM, died_city=KTM,
    notes="Second queen. Known as Queen Mother Ratna.", generation=11)

fg_mahendra1 = marry(mahendra.id, indra_queen.id, union_year=1940)
fg_mahendra2 = marry(mahendra.id, ratna.id, union_year=1952)

# ═══════════════════════════════════════════════════════════════════════
# GENERATION 12 — Birendra, Gyanendra, siblings
# ═══════════════════════════════════════════════════════════════════════

shanti = P(given_name="Shanti Rajya Lakshmi", surname="Shah", sex="FEMALE",
    birth_year=1943, death_year=2001, is_living=False,
    born_city=KTM, died_city=KTM,
    notes="Princess. Killed in the 2001 Royal Massacre.", generation=12)
ch(fg_mahendra1, shanti.id)

birendra = P(given_name="Birendra Bir Bikram", surname="Shah Dev", sex="MALE",
    birth_year=1945, death_year=2001, is_living=False,
    born_city=KTM, died_city=KTM,
    notes="King of Nepal (1972-2001). Killed in the Royal Massacre.", generation=12)
ch(fg_mahendra1, birendra.id)

gyanendra = P(given_name="Gyanendra Bir Bikram", surname="Shah Dev", sex="MALE",
    birth_year=1947, is_living=True,
    born_city=KTM,
    notes="Last King of Nepal (2001-2008). Monarchy abolished.", generation=12)
ch(fg_mahendra1, gyanendra.id)

sharada = P(given_name="Sharada Rajya Lakshmi", surname="Shah", sex="FEMALE",
    birth_year=1948, death_year=2001, is_living=False,
    born_city=KTM, died_city=KTM,
    notes="Princess. Killed in the 2001 Royal Massacre.", generation=12)
ch(fg_mahendra1, sharada.id)

dhirendra = P(given_name="Dhirendra Bir Bikram", surname="Shah", sex="MALE",
    birth_year=1950, death_year=2001, is_living=False,
    born_city=KTM, died_city=KTM,
    notes="Prince. Killed in the 2001 Royal Massacre.", generation=12)
ch(fg_mahendra1, dhirendra.id)

shobha = P(given_name="Shobha Rajya Lakshmi", surname="Shahi", sex="FEMALE",
    birth_year=1952, is_living=True,
    born_city=KTM,
    notes="Princess. Daughter of Mahendra and Ratna.", generation=12)
ch(fg_mahendra2, shobha.id)

# Spouses
aishwarya = P(given_name="Aishwarya Rajya Lakshmi", surname="Devi Rana", sex="FEMALE",
    birth_year=1949, death_year=2001, is_living=False,
    born_city=KTM, died_city=KTM,
    notes="Queen consort. Killed in the 2001 Royal Massacre.", generation=12)

komal = P(given_name="Komal Rajya Lakshmi", surname="Devi Rana", sex="FEMALE",
    birth_year=1951, is_living=True,
    born_city=KTM,
    notes="Queen consort of Gyanendra. Survived the 2001 massacre.", generation=12)

fg_birendra = marry(birendra.id, aishwarya.id, union_year=1970)
fg_gyanendra = marry(gyanendra.id, komal.id, union_year=1970)

kumar_khadga = P(given_name="Kumar Khadga Bikram", surname="Shah", sex="MALE",
    birth_year=1945, death_year=2001, is_living=False,
    born_city=KTM, died_city=KTM,
    notes="Husband of Princess Sharada. Killed in the massacre.", generation=12)

fg_sharada = marry(kumar_khadga.id, sharada.id, union_year=1968)

# ═══════════════════════════════════════════════════════════════════════
# GENERATION 13 — Dipendra, Shruti, Nirajan, Paras, Prerana
# ═══════════════════════════════════════════════════════════════════════

dipendra = P(given_name="Dipendra Bir Bikram", surname="Shah Dev", sex="MALE",
    birth_year=1971, death_year=2001, is_living=False,
    born_city=KTM, died_city=KTM,
    notes="Crown Prince. Perpetrated the 2001 Royal Massacre. King for 3 days while in coma.", generation=13)
ch(fg_birendra, dipendra.id)

shruti = P(given_name="Shruti Rajya Lakshmi", surname="Shah", sex="FEMALE",
    birth_year=1976, death_year=2001, is_living=False,
    born_city=KTM, died_city=KTM,
    notes="Princess. Killed in the 2001 Royal Massacre.", generation=13)
ch(fg_birendra, shruti.id)

nirajan = P(given_name="Nirajan Bir Bikram", surname="Shah", sex="MALE",
    birth_year=1978, death_year=2001, is_living=False,
    born_city=KTM, died_city=KTM,
    notes="Prince. Killed in the 2001 Royal Massacre.", generation=13)
ch(fg_birendra, nirajan.id)

# Shruti's husband
gorakh = P(given_name="Kumar Gorakh", surname="Shumsher Rana", sex="MALE",
    birth_year=1974, is_living=True,
    born_city=KTM,
    notes="Husband of Princess Shruti.", generation=13)

fg_shruti = marry(gorakh.id, shruti.id, union_year=1997)

# Shruti's children
girwani = P(given_name="Girwani Rajya Lakshmi", surname="Rana", sex="FEMALE",
    birth_year=1998, is_living=True,
    born_city=KTM,
    notes="Daughter of Princess Shruti.", generation=14)
ch(fg_shruti, girwani.id)

surangana = P(given_name="Surangana Rajya Lakshmi", surname="Rana", sex="FEMALE",
    birth_year=2000, is_living=True,
    born_city=KTM,
    notes="Daughter of Princess Shruti.", generation=14)
ch(fg_shruti, surangana.id)

# Gyanendra's children
paras = P(given_name="Paras Bir Bikram", surname="Shah Dev", sex="MALE",
    birth_year=1971, is_living=True,
    born_city=KTM,
    notes="Former Crown Prince of Nepal. Survived the 2001 massacre.", generation=13)
ch(fg_gyanendra, paras.id)

prerana = P(given_name="Prerana Rajya Lakshmi", surname="Shah Singh", sex="FEMALE",
    birth_year=1978, is_living=True,
    born_city=KTM,
    notes="Princess. Daughter of Gyanendra. Survived the 2001 massacre.", generation=13)
ch(fg_gyanendra, prerana.id)

# Paras's wife
himani = P(given_name="Himani Rajya Lakshmi", surname="Devi Shah", sex="FEMALE",
    birth_year=1976, is_living=True,
    born_city=KTM,
    notes="Wife of former Crown Prince Paras.", generation=13)

fg_paras = marry(paras.id, himani.id, union_year=2000)

# ═══════════════════════════════════════════════════════════════════════
# GENERATION 14 — Current youngest generation
# ═══════════════════════════════════════════════════════════════════════

purnika = P(given_name="Purnika Rajya Lakshmi", surname="Shah", sex="FEMALE",
    birth_year=2000, is_living=True,
    born_city=KTM,
    notes="Eldest child of Paras and Himani.", generation=14)
ch(fg_paras, purnika.id)

hridayendra = P(given_name="Hridayendra Bir Bikram", surname="Shah Dev", sex="MALE",
    birth_year=2002, is_living=True,
    born_city=KTM,
    notes="Would-be heir to the throne. Son of Paras.", generation=14)
ch(fg_paras, hridayendra.id)

kritika = P(given_name="Kritika Rajya Lakshmi", surname="Shah", sex="FEMALE",
    birth_year=2004, is_living=True,
    born_city=KTM,
    notes="Youngest child of Paras and Himani.", generation=14)
ch(fg_paras, kritika.id)


# ═══════════════════════════════════════════════════════════════════════
# PHOTO + DB (same pattern as other scripts)
# ═══════════════════════════════════════════════════════════════════════

CAPTIONS = [
    ["Royal portrait", "At the palace", "Durbar ceremony"],
    ["Official portrait", "State visit", "Coronation day"],
    ["Royal audience", "Temple visit", "Basantapur Durbar"],
    ["Narayanhiti Palace", "Royal procession", "State function"],
    ["Diplomatic event", "Family portrait", "Nepal heritage"],
]


def download(url, timeout=15):
    try:
        r = requests.get(url, timeout=timeout, allow_redirects=True,
                         headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        return r.content
    except Exception as e:
        print(f"  [WARN] {e}", file=sys.stderr)
        return None


def placeholder(w, h, color):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "JPEG", quality=80)
    return buf.getvalue()


def upload_photos(s3):
    total = len(persons)
    print(f"\nUploading photos for {total} persons...", file=sys.stderr)
    mi, fi = 0, 0
    for i, p in enumerate(persons.values()):
        print(f"  [{i+1}/{total}] {p.given_name} {p.surname}", file=sys.stderr)

        if p.sex == "MALE":
            url = f"https://randomuser.me/api/portraits/men/{mi % 100}.jpg"
            mi += 1
        else:
            url = f"https://randomuser.me/api/portraits/women/{fi % 100}.jpg"
            fi += 1

        img = download(url) or placeholder(300, 300,
              (70, 130, 180) if p.sex == "MALE" else (219, 112, 147))

        pid = uid()
        key = f"tenants/{TENANT_ID}/trees/{TREE_ID}/persons/{p.id}/photo/{pid}.jpg"
        s3.put_object(Bucket=S3_BUCKET, Key=key, Body=img, ContentType="image/jpeg")
        p.photo_s3_key = key

        caps = random.choice(CAPTIONS)
        for pos in range(3):
            gurl = f"https://picsum.photos/seed/{p.id}-{pos}/400/300"
            gimg = download(gurl) or placeholder(400, 300,
                   [(180, 200, 150), (150, 180, 200), (200, 170, 150)][pos])
            gid = uid()
            gkey = f"tenants/{TENANT_ID}/trees/{TREE_ID}/persons/{p.id}/gallery/{gid}.jpg"
            s3.put_object(Bucket=S3_BUCKET, Key=gkey, Body=gimg, ContentType="image/jpeg")
            p.gallery_keys.append((gid, gkey, caps[pos]))

    print(f"  Done — {total} profiles + {total*3} gallery photos.", file=sys.stderr)


def insert_db():
    import psycopg2
    print("\nInserting into database...", file=sys.stderr)
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False
    cur = conn.cursor()
    try:
        cur.execute("""INSERT INTO family_trees (id,tenant_id,name,description,created_at,updated_at)
            VALUES (%s,%s,%s,%s,NOW(),NOW()) ON CONFLICT (id) DO NOTHING""",
            (TREE_ID, TENANT_ID, TREE_NAME,
             "The Shah Dynasty of Nepal — from Prithvi Narayan Shah (1723) to current descendants. 14 generations including the 2001 Royal Massacre."))

        cur.execute("""INSERT INTO tree_members (id,tree_id,user_id,tenant_id,role,joined_at,created_at,updated_at)
            VALUES (gen_random_uuid(),%s,%s,%s,'ADMIN',NOW(),NOW(),NOW())
            ON CONFLICT ON CONSTRAINT uq_tree_member DO NOTHING""",
            (TREE_ID, USER_ID, TENANT_ID))

        for p in persons.values():
            cur.execute("""INSERT INTO persons (id,tree_id,tenant_id,display_given_name,display_surname,
                sex,birth_year,death_year,is_living,is_deceased,is_deleted,
                born_city,born_country,died_city,died_country,notes,photo_url,created_at,updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,false,%s,%s,%s,%s,%s,%s,NOW(),NOW())""",
                (p.id, TREE_ID, TENANT_ID, p.given_name, p.surname,
                 p.sex, p.birth_year, p.death_year, p.is_living, not p.is_living,
                 p.born_city, p.born_country, p.died_city, p.died_country,
                 p.notes, p.photo_s3_key))

        for fg in fgs:
            p1 = fg.parent_ids[0] if len(fg.parent_ids) > 0 else None
            p2 = fg.parent_ids[1] if len(fg.parent_ids) > 1 else None
            cur.execute("""INSERT INTO family_groups (id,tree_id,tenant_id,union_type,
                parent1_id,parent2_id,is_divorced,union_date_year,union_end_date_year,created_at,updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())""",
                (fg.id, TREE_ID, TENANT_ID, fg.union_type, p1, p2,
                 fg.is_divorced, fg.union_year, fg.union_end_year))

        for fg in fgs:
            for pid in fg.parent_ids:
                cur.execute("""INSERT INTO family_group_members (id,family_group_id,person_id,
                    role,parentage_type,tree_id,tenant_id,created_at,updated_at)
                    VALUES (gen_random_uuid(),%s,%s,'PARENT',NULL,%s,%s,NOW(),NOW())""",
                    (fg.id, pid, TREE_ID, TENANT_ID))
            for cid, pt in fg.children:
                cur.execute("""INSERT INTO family_group_members (id,family_group_id,person_id,
                    role,parentage_type,tree_id,tenant_id,created_at,updated_at)
                    VALUES (gen_random_uuid(),%s,%s,'CHILD',%s,%s,%s,NOW(),NOW())""",
                    (fg.id, cid, pt, TREE_ID, TENANT_ID))

        for p in persons.values():
            for gid, gkey, cap in p.gallery_keys:
                pos = [x[0] for x in p.gallery_keys].index(gid)
                cur.execute("""INSERT INTO person_gallery_photos (id,person_id,tree_id,tenant_id,
                    photo_url,caption,position,created_at,updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())""",
                    (gid, p.id, TREE_ID, TENANT_ID, gkey, cap, pos))

        conn.commit()
        n_gal = sum(len(p.gallery_keys) for p in persons.values())
        print(f"  Inserted {len(persons)} persons, {len(fgs)} family groups, {n_gal} gallery photos.", file=sys.stderr)
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def main():
    print(f"Shah Dynasty: {len(persons)} persons, {len(fgs)} family groups", file=sys.stderr)
    gc = {}
    for p in persons.values():
        gc[p.generation] = gc.get(p.generation, 0) + 1
    for g in sorted(gc):
        print(f"  Gen {g}: {gc[g]}", file=sys.stderr)

    massacre_victims = [p for p in persons.values() if p.death_year == 2001]
    print(f"\n2001 Royal Massacre victims: {len(massacre_victims)}", file=sys.stderr)
    for v in massacre_victims:
        print(f"  {v.given_name} {v.surname} ({v.birth_year}-{v.death_year})", file=sys.stderr)

    s3 = boto3.client("s3", endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_KEY, aws_secret_access_key=S3_SECRET,
        region_name="us-east-1", config=BotoCfg(signature_version="s3v4"))

    upload_photos(s3)
    insert_db()

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"Done! '{TREE_NAME}' is ready.", file=sys.stderr)
    print(f"Log in as nirajbjk@gmail.com at http://localhost:7006", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)


if __name__ == "__main__":
    main()
