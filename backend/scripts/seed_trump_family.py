"""
Seed the publicly documented Trump family tree — 6 generations.

Sources: public genealogical records, Wikipedia, news archives.
Photos are placeholder portraits from randomuser.me & picsum.photos.

Run:  python -m scripts.seed_trump_family
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

random.seed(45)

# ── Config ───────────────────────────────────────────────────────────────

TENANT_ID = "626cddcf-0e25-4b56-9b05-13ad6a95ec8a"
TREE_ID = "eeeeeeee-0045-4000-a000-000000000001"
TREE_NAME = "The Trump Family"
USER_ID = "5142fcf9-366f-47b5-8630-6086608fefbb"

DB_URL = "postgresql://postgres:postgres@localhost:7000/ourfamroots"
S3_ENDPOINT = "http://localhost:7002"
S3_BUCKET = "ourfamroots-media"
S3_ACCESS_KEY = "minioadmin"
S3_SECRET_KEY = "minioadmin"


# ── Data structures ──────────────────────────────────────────────────────

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
    born_country: str = "United States"
    died_city: Optional[str] = None
    died_country: Optional[str] = None
    notes: Optional[str] = None
    generation: int = 1
    photo_s3_key: Optional[str] = None
    gallery_keys: list[tuple[str, str, str]] = field(default_factory=list)


@dataclass
class FamilyGroup:
    id: str
    union_type: str
    parent_ids: list[str] = field(default_factory=list)
    children: list[tuple[str, str]] = field(default_factory=list)
    is_divorced: bool = False
    union_year: Optional[int] = None
    union_end_year: Optional[int] = None


def uid() -> str:
    return str(uuid.uuid4())


persons: dict[str, Person] = {}
family_groups: list[FamilyGroup] = []


def P(**kw) -> Person:
    kw.setdefault("id", uid())
    p = Person(**kw)
    persons[p.id] = p
    return p


def couple(p1: str, p2: str, **kw) -> FamilyGroup:
    kw.setdefault("id", uid())
    kw.setdefault("union_type", "MARRIAGE")
    fg = FamilyGroup(parent_ids=[p1, p2], **kw)
    family_groups.append(fg)
    return fg


def child(fg: FamilyGroup, cid: str, pt: str = "BIOLOGICAL"):
    fg.children.append((cid, pt))


# ═══════════════════════════════════════════════════════════════════════
# GENERATION 1 — Great-Grandparents (born 1829-1869)
# ═══════════════════════════════════════════════════════════════════════

# Paternal great-grandparents
johannes = P(given_name="Johannes", surname="Trump", sex="MALE",
    birth_year=1829, death_year=1877, is_living=False,
    born_city="Kallstadt", born_country="Germany",
    died_city="Kallstadt", died_country="Germany",
    notes="Viticulturist in Kallstadt, Bavaria.", generation=1)

katharina_k = P(given_name="Katharina", surname="Kober", sex="FEMALE",
    birth_year=1836, death_year=1922, is_living=False,
    born_city="Kallstadt", born_country="Germany",
    died_city="Kallstadt", died_country="Germany",
    generation=1)

fg_johannes = couple(johannes.id, katharina_k.id, union_year=1859)

# Maternal great-grandparents (mother's parents' parents - simplified)
# Mary Anne MacLeod's paternal grandparents from Isle of Lewis
alexander_macleod = P(given_name="Alexander", surname="MacLeod", sex="MALE",
    birth_year=1830, death_year=1900, is_living=False,
    born_city="Stornoway", born_country="United Kingdom",
    notes="Crofter on the Isle of Lewis, Scotland.", generation=1)

ann_macleod = P(given_name="Ann", surname="MacKenzie", sex="FEMALE",
    birth_year=1833, death_year=1905, is_living=False,
    born_city="Stornoway", born_country="United Kingdom",
    generation=1)

fg_alexander = couple(alexander_macleod.id, ann_macleod.id, union_year=1855)

# ═══════════════════════════════════════════════════════════════════════
# GENERATION 2 — Grandparents (born 1866-1880)
# ═══════════════════════════════════════════════════════════════════════

# Paternal grandparents
friedrich = P(given_name="Friedrich", surname="Trump", sex="MALE",
    birth_year=1869, death_year=1918, is_living=False,
    born_city="Kallstadt", born_country="Germany",
    died_city="Queens", died_country="United States",
    notes="Emigrated to the US in 1885. Died in the 1918 flu pandemic.", generation=2)
child(fg_johannes, friedrich.id)

elizabeth_c = P(given_name="Elizabeth", surname="Christ", sex="FEMALE",
    birth_year=1880, death_year=1966, is_living=False,
    born_city="Kallstadt", born_country="Germany",
    died_city="Queens", died_country="United States",
    notes="Co-founded Elizabeth Trump & Son real estate.", generation=2)

fg_friedrich = couple(friedrich.id, elizabeth_c.id, union_year=1902)

# Maternal grandparents
malcolm = P(given_name="Malcolm", surname="MacLeod", sex="MALE",
    birth_year=1866, death_year=1954, is_living=False,
    born_city="Stornoway", born_country="United Kingdom",
    died_city="Stornoway", died_country="United Kingdom",
    notes="Fisherman and crofter on Isle of Lewis.", generation=2)
child(fg_alexander, malcolm.id)

mary_smith = P(given_name="Mary", surname="Smith", sex="FEMALE",
    birth_year=1867, death_year=1963, is_living=False,
    born_city="Stornoway", born_country="United Kingdom",
    died_city="Stornoway", died_country="United Kingdom",
    generation=2)

fg_malcolm = couple(malcolm.id, mary_smith.id, union_year=1891)

# ═══════════════════════════════════════════════════════════════════════
# GENERATION 3 — Parents & their siblings (born 1904-1915)
# ═══════════════════════════════════════════════════════════════════════

# Fred Trump — Donald's father
fred = P(given_name="Fred", surname="Trump", sex="MALE",
    birth_year=1905, death_year=1999, is_living=False,
    born_city="Woodhaven", born_country="United States",
    died_city="New Hyde Park", died_country="United States",
    notes="Real estate developer in New York City.", generation=3)
child(fg_friedrich, fred.id)

# Fred's siblings
john_trump = P(given_name="John", surname="Trump", sex="MALE",
    birth_year=1907, death_year=1985, is_living=False,
    born_city="New York", born_country="United States",
    died_city="Boston", died_country="United States",
    notes="MIT professor of electrical engineering.", generation=3)
child(fg_friedrich, john_trump.id)

elizabeth_t = P(given_name="Elizabeth", surname="Trump", sex="FEMALE",
    birth_year=1904, death_year=1961, is_living=False,
    born_city="New York", born_country="United States",
    notes="Eldest child of Friedrich and Elizabeth.", generation=3)
child(fg_friedrich, elizabeth_t.id)

# Mary Anne MacLeod — Donald's mother
mary_anne = P(given_name="Mary Anne", surname="MacLeod", sex="FEMALE",
    birth_year=1912, death_year=2000, is_living=False,
    born_city="Tong", born_country="United Kingdom",
    died_city="New Hyde Park", died_country="United States",
    notes="Emigrated from Scotland to New York in 1930.", generation=3)
child(fg_malcolm, mary_anne.id)

fg_fred = couple(fred.id, mary_anne.id, union_year=1936)

# ═══════════════════════════════════════════════════════════════════════
# GENERATION 4 — Donald & siblings (born 1937-1948) + spouses
# ═══════════════════════════════════════════════════════════════════════

maryanne = P(given_name="Maryanne", surname="Trump", sex="FEMALE",
    birth_year=1937, death_year=2023, is_living=False,
    born_city="Jamaica", born_country="United States",
    died_city="New York", died_country="United States",
    notes="Senior US Circuit Judge.", generation=4)
child(fg_fred, maryanne.id)

fred_jr = P(given_name="Fred", surname="Trump Jr.", sex="MALE",
    birth_year=1938, death_year=1981, is_living=False,
    born_city="Jamaica", born_country="United States",
    died_city="Queens", died_country="United States",
    notes="TWA airline pilot. Died at age 42.", generation=4)
child(fg_fred, fred_jr.id)

elizabeth_g = P(given_name="Elizabeth", surname="Trump", sex="FEMALE",
    birth_year=1942, is_living=True,
    born_city="Jamaica", born_country="United States",
    notes="Administrative assistant at Chase Manhattan Bank.", generation=4)
child(fg_fred, elizabeth_g.id)

donald = P(given_name="Donald", surname="Trump", sex="MALE",
    birth_year=1946, is_living=True,
    born_city="Jamaica", born_country="United States",
    notes="45th and 47th President of the United States.", generation=4)
child(fg_fred, donald.id)

robert = P(given_name="Robert", surname="Trump", sex="MALE",
    birth_year=1948, death_year=2020, is_living=False,
    born_city="Jamaica", born_country="United States",
    died_city="New York", died_country="United States",
    notes="Business executive. Youngest of the five siblings.", generation=4)
child(fg_fred, robert.id)

# ── Gen 4 spouses ────────────────────────────────────────────────────

# Maryanne's husband
john_barry = P(given_name="John", surname="Barry", sex="MALE",
    birth_year=1927, death_year=2000, is_living=False,
    born_city="New Jersey", born_country="United States",
    notes="Attorney.", generation=4)
fg_maryanne = couple(john_barry.id, maryanne.id, union_year=1961)

# Fred Jr.'s wife
linda_clapp = P(given_name="Linda", surname="Clapp", sex="FEMALE",
    birth_year=1940, is_living=True,
    born_city="Florida", born_country="United States",
    generation=4)
fg_fred_jr = couple(fred_jr.id, linda_clapp.id, union_year=1962,
                     is_divorced=True, union_end_year=1971)

# Elizabeth's husband
james_grau = P(given_name="James", surname="Grau", sex="MALE",
    birth_year=1940, is_living=True,
    born_city="New York", born_country="United States",
    notes="Film producer.", generation=4)
fg_elizabeth_g = couple(james_grau.id, elizabeth_g.id, union_year=1989)

# Donald's three marriages
ivana = P(given_name="Ivana", surname="Trump", sex="FEMALE",
    birth_year=1949, death_year=2022, is_living=False,
    born_city="Zlín", born_country="Czechoslovakia",
    died_city="New York", died_country="United States",
    notes="Businesswoman and fashion designer. Born Ivana Zelníčková.", generation=4)
fg_donald1 = couple(donald.id, ivana.id, union_year=1977,
                     is_divorced=True, union_end_year=1992)

marla = P(given_name="Marla", surname="Maples", sex="FEMALE",
    birth_year=1963, is_living=True,
    born_city="Dalton", born_country="United States",
    notes="Actress and television personality.", generation=4)
fg_donald2 = couple(donald.id, marla.id, union_year=1993,
                     is_divorced=True, union_end_year=1999)

melania = P(given_name="Melania", surname="Trump", sex="FEMALE",
    birth_year=1970, is_living=True,
    born_city="Novo Mesto", born_country="Slovenia",
    notes="Former model. Former First Lady of the US.", generation=4)
fg_donald3 = couple(donald.id, melania.id, union_year=2005)

# Robert's wife
blaine = P(given_name="Blaine", surname="Trump", sex="FEMALE",
    birth_year=1957, is_living=True,
    born_city="New York", born_country="United States",
    notes="Socialite and fashion designer.", generation=4)
fg_robert = couple(robert.id, blaine.id, union_year=1989,
                    is_divorced=True, union_end_year=2007)

ann_marie = P(given_name="Ann Marie", surname="Pallan", sex="FEMALE",
    birth_year=1965, is_living=True,
    born_city="New York", born_country="United States",
    generation=4)
fg_robert2 = couple(robert.id, ann_marie.id, union_year=2020)

# ═══════════════════════════════════════════════════════════════════════
# GENERATION 5 — Children (born 1960-2006)
# ═══════════════════════════════════════════════════════════════════════

# Maryanne & John Barry's son
david_desmond = P(given_name="David", surname="Desmond", sex="MALE",
    birth_year=1962, is_living=True,
    born_city="New York", born_country="United States",
    generation=5)
child(fg_maryanne, david_desmond.id)

# Fred Jr. & Linda's children
fred_iii = P(given_name="Fred", surname="Trump III", sex="MALE",
    birth_year=1963, is_living=True,
    born_city="New York", born_country="United States",
    notes="Real estate developer.", generation=5)
child(fg_fred_jr, fred_iii.id)

mary_t = P(given_name="Mary", surname="Trump", sex="FEMALE",
    birth_year=1965, is_living=True,
    born_city="New York", born_country="United States",
    notes="Author and clinical psychologist.", generation=5)
child(fg_fred_jr, mary_t.id)

# Donald & Ivana's children
don_jr = P(given_name="Donald", surname="Trump Jr.", sex="MALE",
    birth_year=1977, is_living=True,
    born_city="New York", born_country="United States",
    notes="Businessman and political activist.", generation=5)
child(fg_donald1, don_jr.id)

ivanka = P(given_name="Ivanka", surname="Trump", sex="FEMALE",
    birth_year=1981, is_living=True,
    born_city="New York", born_country="United States",
    notes="Businesswoman. Senior Advisor to the President.", generation=5)
child(fg_donald1, ivanka.id)

eric = P(given_name="Eric", surname="Trump", sex="MALE",
    birth_year=1984, is_living=True,
    born_city="New York", born_country="United States",
    notes="Executive VP of the Trump Organization.", generation=5)
child(fg_donald1, eric.id)

# Donald & Marla's daughter
tiffany = P(given_name="Tiffany", surname="Trump", sex="FEMALE",
    birth_year=1993, is_living=True,
    born_city="West Palm Beach", born_country="United States",
    notes="Attorney. Georgetown Law graduate.", generation=5)
child(fg_donald2, tiffany.id)

# Donald & Melania's son
barron = P(given_name="Barron", surname="Trump", sex="MALE",
    birth_year=2006, is_living=True,
    born_city="New York", born_country="United States",
    notes="Youngest child of Donald Trump.", generation=5)
child(fg_donald3, barron.id)

# ── Gen 5 spouses ────────────────────────────────────────────────────

vanessa = P(given_name="Vanessa", surname="Haydon", sex="FEMALE",
    birth_year=1977, is_living=True,
    born_city="New York", born_country="United States",
    notes="Former model and actress.", generation=5)
fg_don_jr = couple(don_jr.id, vanessa.id, union_year=2005,
                    is_divorced=True, union_end_year=2018)

kimberly = P(given_name="Kimberly", surname="Guilfoyle", sex="FEMALE",
    birth_year=1969, is_living=True,
    born_city="San Francisco", born_country="United States",
    notes="Attorney and television personality.", generation=5)
fg_don_jr2 = couple(don_jr.id, kimberly.id, union_year=2024)

jared = P(given_name="Jared", surname="Kushner", sex="MALE",
    birth_year=1981, is_living=True,
    born_city="Livingston", born_country="United States",
    notes="Businessman. Senior Advisor to the President.", generation=5)
fg_ivanka = couple(jared.id, ivanka.id, union_year=2009)

lara = P(given_name="Lara", surname="Trump", sex="FEMALE",
    birth_year=1982, is_living=True,
    born_city="Wilmington", born_country="United States",
    notes="Television producer. Co-chair of the RNC.", generation=5)
fg_eric = couple(eric.id, lara.id, union_year=2014)

michael_b = P(given_name="Michael", surname="Boulos", sex="MALE",
    birth_year=1997, is_living=True,
    born_city="Lagos", born_country="Nigeria",
    notes="Businessman. Lebanese-Nigerian descent.", generation=5)
fg_tiffany = couple(michael_b.id, tiffany.id, union_year=2022)

# ═══════════════════════════════════════════════════════════════════════
# GENERATION 6 — Grandchildren (born 2007-2024)
# ═══════════════════════════════════════════════════════════════════════

# Don Jr. & Vanessa's children
kai = P(given_name="Kai", surname="Trump", sex="FEMALE",
    birth_year=2007, is_living=True,
    born_city="New York", born_country="United States",
    notes="Eldest grandchild of Donald Trump.", generation=6)
child(fg_don_jr, kai.id)

donald_iii = P(given_name="Donald", surname="Trump III", sex="MALE",
    birth_year=2009, is_living=True,
    born_city="New York", born_country="United States",
    generation=6)
child(fg_don_jr, donald_iii.id)

tristan = P(given_name="Tristan", surname="Trump", sex="MALE",
    birth_year=2011, is_living=True,
    born_city="New York", born_country="United States",
    generation=6)
child(fg_don_jr, tristan.id)

spencer = P(given_name="Spencer", surname="Trump", sex="MALE",
    birth_year=2012, is_living=True,
    born_city="New York", born_country="United States",
    generation=6)
child(fg_don_jr, spencer.id)

chloe = P(given_name="Chloe", surname="Trump", sex="FEMALE",
    birth_year=2014, is_living=True,
    born_city="New York", born_country="United States",
    generation=6)
child(fg_don_jr, chloe.id)

# Ivanka & Jared's children
arabella = P(given_name="Arabella", surname="Kushner", sex="FEMALE",
    birth_year=2011, is_living=True,
    born_city="New York", born_country="United States",
    generation=6)
child(fg_ivanka, arabella.id)

joseph_k = P(given_name="Joseph", surname="Kushner", sex="MALE",
    birth_year=2013, is_living=True,
    born_city="New York", born_country="United States",
    generation=6)
child(fg_ivanka, joseph_k.id)

theodore_k = P(given_name="Theodore", surname="Kushner", sex="MALE",
    birth_year=2016, is_living=True,
    born_city="New York", born_country="United States",
    generation=6)
child(fg_ivanka, theodore_k.id)

# Eric & Lara's children
luke = P(given_name="Eric", surname="Trump", sex="MALE",
    birth_year=2017, is_living=True,
    born_city="New York", born_country="United States",
    notes="Known as Luke.", generation=6)
child(fg_eric, luke.id)

carolina = P(given_name="Carolina", surname="Trump", sex="FEMALE",
    birth_year=2019, is_living=True,
    born_city="New York", born_country="United States",
    generation=6)
child(fg_eric, carolina.id)


# ═══════════════════════════════════════════════════════════════════════
# PHOTO DOWNLOAD & UPLOAD
# ═══════════════════════════════════════════════════════════════════════

GALLERY_CAPTIONS = [
    ["Family portrait", "At a gala", "Holiday gathering"],
    ["Official photo", "Sunday brunch", "Garden party"],
    ["Summer vacation", "Birthday celebration", "Reunion photo"],
    ["Formal event", "Thanksgiving dinner", "At the estate"],
    ["Christmas portrait", "Anniversary dinner", "Charity event"],
    ["Graduation day", "Campaign trail", "At the office"],
    ["Press event", "Family dinner", "At the club"],
    ["Award ceremony", "Weekend retreat", "Community event"],
]


def download_image(url: str, timeout: int = 15) -> bytes | None:
    try:
        r = requests.get(url, timeout=timeout, allow_redirects=True)
        r.raise_for_status()
        return r.content
    except Exception as e:
        print(f"  [WARN] Failed: {url}: {e}", file=sys.stderr)
        return None


def make_placeholder(w: int, h: int, color: tuple) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "JPEG", quality=80)
    return buf.getvalue()


def upload_photos(s3):
    total = len(persons)
    print(f"\nUploading photos for {total} persons...", file=sys.stderr)

    male_idx, female_idx = 0, 0

    for i, p in enumerate(persons.values()):
        pct = (i + 1) / total * 100
        print(f"  [{i+1}/{total}] ({pct:.0f}%) {p.given_name} {p.surname}...", file=sys.stderr)

        # Profile photo
        if p.sex == "MALE":
            url = f"https://randomuser.me/api/portraits/men/{male_idx % 100}.jpg"
            male_idx += 1
        else:
            url = f"https://randomuser.me/api/portraits/women/{female_idx % 100}.jpg"
            female_idx += 1

        img = download_image(url)
        if img is None:
            c = (70, 130, 180) if p.sex == "MALE" else (219, 112, 147)
            img = make_placeholder(300, 300, c)

        photo_id = uid()
        key = f"tenants/{TENANT_ID}/trees/{TREE_ID}/persons/{p.id}/photo/{photo_id}.jpg"
        s3.put_object(Bucket=S3_BUCKET, Key=key, Body=img, ContentType="image/jpeg")
        p.photo_s3_key = key

        # 3 gallery photos
        captions = random.choice(GALLERY_CAPTIONS)
        for pos in range(3):
            gal_url = f"https://picsum.photos/seed/{p.id}-{pos}/400/300"
            gal_img = download_image(gal_url)
            if gal_img is None:
                colors = [(180, 200, 150), (150, 180, 200), (200, 170, 150)]
                gal_img = make_placeholder(400, 300, colors[pos])

            gal_id = uid()
            gal_key = f"tenants/{TENANT_ID}/trees/{TREE_ID}/persons/{p.id}/gallery/{gal_id}.jpg"
            s3.put_object(Bucket=S3_BUCKET, Key=gal_key, Body=gal_img, ContentType="image/jpeg")
            p.gallery_keys.append((gal_id, gal_key, captions[pos]))

    print(f"  Done — {total} profiles + {total * 3} gallery photos.", file=sys.stderr)


# ═══════════════════════════════════════════════════════════════════════
# DATABASE INSERT
# ═══════════════════════════════════════════════════════════════════════

def insert_into_db():
    import psycopg2
    print("\nInserting into database...", file=sys.stderr)
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO family_trees (id, tenant_id, name, description, created_at, updated_at)
            VALUES (%s, %s, %s, %s, NOW(), NOW()) ON CONFLICT (id) DO NOTHING
        """, (TREE_ID, TENANT_ID, TREE_NAME,
              "The Trump family tree spanning 6 generations — from 1820s Bavaria to present day."))

        cur.execute("""
            INSERT INTO tree_members (id, tree_id, user_id, tenant_id, role, joined_at, created_at, updated_at)
            VALUES (gen_random_uuid(), %s, %s, %s, 'ADMIN', NOW(), NOW(), NOW())
            ON CONFLICT ON CONSTRAINT uq_tree_member DO NOTHING
        """, (TREE_ID, USER_ID, TENANT_ID))

        for p in persons.values():
            cur.execute("""
                INSERT INTO persons (
                    id, tree_id, tenant_id, display_given_name, display_surname,
                    sex, birth_year, death_year, is_living, is_deceased, is_deleted,
                    born_city, born_country, died_city, died_country,
                    notes, photo_url, created_at, updated_at
                ) VALUES (%s,%s,%s,%s,%s, %s,%s,%s,%s,%s,false, %s,%s,%s,%s, %s,%s,NOW(),NOW())
            """, (
                p.id, TREE_ID, TENANT_ID, p.given_name, p.surname,
                p.sex, p.birth_year, p.death_year, p.is_living, not p.is_living,
                p.born_city, p.born_country, p.died_city, p.died_country,
                p.notes, p.photo_s3_key,
            ))

        for fg in family_groups:
            p1 = fg.parent_ids[0] if len(fg.parent_ids) > 0 else None
            p2 = fg.parent_ids[1] if len(fg.parent_ids) > 1 else None
            cur.execute("""
                INSERT INTO family_groups (
                    id, tree_id, tenant_id, union_type,
                    parent1_id, parent2_id, is_divorced,
                    union_date_year, union_end_date_year, created_at, updated_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())
            """, (fg.id, TREE_ID, TENANT_ID, fg.union_type,
                  p1, p2, fg.is_divorced, fg.union_year, fg.union_end_year))

        for fg in family_groups:
            for pid in fg.parent_ids:
                cur.execute("""
                    INSERT INTO family_group_members (
                        id, family_group_id, person_id, role, parentage_type,
                        tree_id, tenant_id, created_at, updated_at
                    ) VALUES (gen_random_uuid(),%s,%s,'PARENT',NULL,%s,%s,NOW(),NOW())
                """, (fg.id, pid, TREE_ID, TENANT_ID))

            for cid, pt in fg.children:
                cur.execute("""
                    INSERT INTO family_group_members (
                        id, family_group_id, person_id, role, parentage_type,
                        tree_id, tenant_id, created_at, updated_at
                    ) VALUES (gen_random_uuid(),%s,%s,'CHILD',%s,%s,%s,NOW(),NOW())
                """, (fg.id, cid, pt, TREE_ID, TENANT_ID))

        for p in persons.values():
            for gal_id, gal_key, caption in p.gallery_keys:
                pos = [x[0] for x in p.gallery_keys].index(gal_id)
                cur.execute("""
                    INSERT INTO person_gallery_photos (
                        id, person_id, tree_id, tenant_id,
                        photo_url, caption, position, created_at, updated_at
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())
                """, (gal_id, p.id, TREE_ID, TENANT_ID, gal_key, caption, pos))

        conn.commit()
        print(f"  Inserted {len(persons)} persons, {len(family_groups)} family groups, "
              f"{sum(len(p.gallery_keys) for p in persons.values())} gallery photos.", file=sys.stderr)
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

def main():
    print(f"Trump Family Tree: {len(persons)} persons, {len(family_groups)} family groups", file=sys.stderr)
    gen_counts = {}
    for p in persons.values():
        gen_counts[p.generation] = gen_counts.get(p.generation, 0) + 1
    for g in sorted(gen_counts):
        print(f"  Gen {g}: {gen_counts[g]} persons", file=sys.stderr)

    union_counts: dict[str, int] = {}
    divorced = 0
    for fg in family_groups:
        union_counts[fg.union_type] = union_counts.get(fg.union_type, 0) + 1
        if fg.is_divorced:
            divorced += 1
    print(f"Unions: {dict(sorted(union_counts.items()))}", file=sys.stderr)
    print(f"Divorces: {divorced}", file=sys.stderr)

    s3 = boto3.client(
        "s3", endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY, aws_secret_access_key=S3_SECRET_KEY,
        region_name="us-east-1", config=BotoCfg(signature_version="s3v4"),
    )

    upload_photos(s3)
    insert_into_db()

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"Done! '{TREE_NAME}' is ready.", file=sys.stderr)
    print(f"Log in as nirajbjk@gmail.com at http://localhost:7006", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)


if __name__ == "__main__":
    main()
