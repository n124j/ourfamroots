"""
Seed a handcrafted 50+ person family tree across 8 generations with photos.

Downloads face portraits from randomuser.me, scenic photos from picsum.photos,
uploads them all to MinIO, and inserts persons/relationships/gallery into Postgres.

Run from project root:
    python -m scripts.seed_family_with_photos

Requires: boto3, requests, Pillow, psycopg2 (all in the backend venv)
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

random.seed(999)

# ── Config ───────────────────────────────────────────────────────────────

TENANT_ID = "626cddcf-0e25-4b56-9b05-13ad6a95ec8a"
TREE_ID = "dddddddd-0050-4000-a000-000000000001"
TREE_NAME = "The Williams Heritage"
USER_ID = "5142fcf9-366f-47b5-8630-6086608fefbb"

DB_URL = "postgresql://postgres:postgres@localhost:7000/ourfamroots"
S3_ENDPOINT = "http://localhost:7002"
S3_BUCKET = "ourfamroots-media"
S3_ACCESS_KEY = "minioadmin"
S3_SECRET_KEY = "minioadmin"

# randomuser.me portrait indices (0-99 available)
_male_portrait_idx = 0
_female_portrait_idx = 0


# ── Data structures ──────────────────────────────────────────────────────

@dataclass
class Person:
    id: str
    given_name: str
    surname: str
    sex: str  # MALE / FEMALE
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
    gallery_keys: list[tuple[str, str, str]] = field(default_factory=list)  # (photo_id, s3_key, caption)


@dataclass
class FamilyGroup:
    id: str
    union_type: str
    parent_ids: list[str] = field(default_factory=list)
    children: list[tuple[str, str]] = field(default_factory=list)  # (person_id, parentage_type)
    is_divorced: bool = False
    union_year: Optional[int] = None
    union_end_year: Optional[int] = None


def uid() -> str:
    return str(uuid.uuid4())


# ── Build the family tree ────────────────────────────────────────────────

persons: dict[str, Person] = {}
family_groups: list[FamilyGroup] = []


def add_person(**kwargs) -> Person:
    p = Person(**kwargs)
    persons[p.id] = p
    return p


def add_couple(p1_id: str, p2_id: str, union_type="MARRIAGE",
               union_year=None, is_divorced=False, union_end_year=None) -> FamilyGroup:
    fg = FamilyGroup(id=uid(), union_type=union_type,
                     parent_ids=[p1_id, p2_id],
                     is_divorced=is_divorced,
                     union_year=union_year, union_end_year=union_end_year)
    family_groups.append(fg)
    return fg


def add_child(fg: FamilyGroup, child_id: str, parentage="BIOLOGICAL"):
    fg.children.append((child_id, parentage))


# ═══════════════════════════════════════════════════════════════════════
# GENERATION 1 — The Founders (born ~1840s)
# ═══════════════════════════════════════════════════════════════════════

edward = add_person(id=uid(), given_name="Edward", surname="Williams",
    sex="MALE", birth_year=1842, death_year=1918, is_living=False,
    born_city="Boston", born_country="United States",
    died_city="Boston", died_country="United States",
    notes="Patriarch of the Williams family. Civil War veteran.", generation=1)

margaret = add_person(id=uid(), given_name="Margaret", surname="O'Brien",
    sex="FEMALE", birth_year=1845, death_year=1922, is_living=False,
    born_city="Dublin", born_country="Ireland",
    died_city="Boston", died_country="United States",
    notes="Immigrated from Ireland in 1862.", generation=1)

fg_gen1 = add_couple(edward.id, margaret.id, union_year=1865)

# ═══════════════════════════════════════════════════════════════════════
# GENERATION 2 — Children of Edward & Margaret (born ~1866-1878)
# ═══════════════════════════════════════════════════════════════════════

henry = add_person(id=uid(), given_name="Henry", surname="Williams",
    sex="MALE", birth_year=1866, death_year=1941, is_living=False,
    born_city="Boston", notes="Eldest son. Worked the shipyards.", generation=2)
add_child(fg_gen1, henry.id)

catherine = add_person(id=uid(), given_name="Catherine", surname="Williams",
    sex="FEMALE", birth_year=1869, death_year=1945, is_living=False,
    born_city="Boston", notes="School teacher for 30 years.", generation=2)
add_child(fg_gen1, catherine.id)

arthur = add_person(id=uid(), given_name="Arthur", surname="Williams",
    sex="MALE", birth_year=1872, death_year=1950, is_living=False,
    born_city="Boston", notes="Moved the family west to Chicago.", generation=2)
add_child(fg_gen1, arthur.id)

florence = add_person(id=uid(), given_name="Florence", surname="Williams",
    sex="FEMALE", birth_year=1876, death_year=1960, is_living=False,
    born_city="Boston", notes="The baby of the family. Amateur painter.", generation=2)
add_child(fg_gen1, florence.id)

# Gen 2 spouses
eleanor_sp = add_person(id=uid(), given_name="Eleanor", surname="Thompson",
    sex="FEMALE", birth_year=1870, death_year=1938, is_living=False,
    born_city="New York", generation=2)

thomas_sp = add_person(id=uid(), given_name="Thomas", surname="Baker",
    sex="MALE", birth_year=1867, death_year=1940, is_living=False,
    born_city="Philadelphia", generation=2)

ruth_sp = add_person(id=uid(), given_name="Ruth", surname="Anderson",
    sex="FEMALE", birth_year=1875, death_year=1955, is_living=False,
    born_city="Chicago", generation=2)

george_sp = add_person(id=uid(), given_name="George", surname="Mitchell",
    sex="MALE", birth_year=1873, death_year=1948, is_living=False,
    born_city="Baltimore", generation=2)

# Gen 2 marriages
fg_henry = add_couple(henry.id, eleanor_sp.id, union_year=1890)
fg_catherine = add_couple(thomas_sp.id, catherine.id, union_year=1892)
fg_arthur = add_couple(arthur.id, ruth_sp.id, union_year=1896)
fg_florence = add_couple(george_sp.id, florence.id, union_year=1898)

# ═══════════════════════════════════════════════════════════════════════
# GENERATION 3 — Grandchildren (born ~1891-1910)
# ═══════════════════════════════════════════════════════════════════════

# Henry & Eleanor's children
william = add_person(id=uid(), given_name="William", surname="Williams",
    sex="MALE", birth_year=1891, death_year=1968, is_living=False,
    born_city="Boston", notes="Fought in WWI. Received Purple Heart.", generation=3)
add_child(fg_henry, william.id)

dorothy = add_person(id=uid(), given_name="Dorothy", surname="Williams",
    sex="FEMALE", birth_year=1894, death_year=1975, is_living=False,
    born_city="Boston", generation=3)
add_child(fg_henry, dorothy.id)

# Thomas & Catherine's children
james_b = add_person(id=uid(), given_name="James", surname="Baker",
    sex="MALE", birth_year=1893, death_year=1970, is_living=False,
    born_city="Philadelphia", generation=3)
add_child(fg_catherine, james_b.id)

helen_b = add_person(id=uid(), given_name="Helen", surname="Baker",
    sex="FEMALE", birth_year=1896, death_year=1980, is_living=False,
    born_city="Philadelphia", generation=3)
add_child(fg_catherine, helen_b.id)

# Arthur & Ruth's children
robert = add_person(id=uid(), given_name="Robert", surname="Williams",
    sex="MALE", birth_year=1897, death_year=1972, is_living=False,
    born_city="Chicago", notes="Mayor of his hometown for 2 terms.", generation=3)
add_child(fg_arthur, robert.id)

virginia = add_person(id=uid(), given_name="Virginia", surname="Williams",
    sex="FEMALE", birth_year=1900, death_year=1985, is_living=False,
    born_city="Chicago", generation=3)
add_child(fg_arthur, virginia.id)

charles = add_person(id=uid(), given_name="Charles", surname="Williams",
    sex="MALE", birth_year=1903, death_year=1990, is_living=False,
    born_city="Chicago", notes="Adopted at age 3.", generation=3)
add_child(fg_arthur, charles.id, "ADOPTIVE")

# George & Florence's children
alice_m = add_person(id=uid(), given_name="Alice", surname="Mitchell",
    sex="FEMALE", birth_year=1899, death_year=1978, is_living=False,
    born_city="Baltimore", generation=3)
add_child(fg_florence, alice_m.id)

frank_m = add_person(id=uid(), given_name="Frank", surname="Mitchell",
    sex="MALE", birth_year=1902, death_year=1982, is_living=False,
    born_city="Baltimore", generation=3)
add_child(fg_florence, frank_m.id)

# Gen 3 spouses
mary_sp = add_person(id=uid(), given_name="Mary", surname="Sullivan",
    sex="FEMALE", birth_year=1895, death_year=1970, is_living=False,
    born_city="New York", generation=3)

harold_sp = add_person(id=uid(), given_name="Harold", surname="Davis",
    sex="MALE", birth_year=1892, death_year=1965, is_living=False,
    born_city="Cleveland", generation=3)

edith_sp = add_person(id=uid(), given_name="Edith", surname="Moore",
    sex="FEMALE", birth_year=1900, death_year=1988, is_living=False,
    born_city="Detroit", generation=3)

clara_sp = add_person(id=uid(), given_name="Clara", surname="Johnson",
    sex="FEMALE", birth_year=1905, death_year=1992, is_living=False,
    born_city="Milwaukee", generation=3)

fred_sp = add_person(id=uid(), given_name="Frederick", surname="Clark",
    sex="MALE", birth_year=1898, death_year=1975, is_living=False,
    born_city="St. Louis", generation=3)

josephine_sp = add_person(id=uid(), given_name="Josephine", surname="Reyes",
    sex="FEMALE", birth_year=1904, death_year=1985, is_living=False,
    born_city="San Antonio", generation=3)

# Gen 3 marriages — includes a DIVORCE + REMARRIAGE
fg_william = add_couple(william.id, mary_sp.id, union_year=1916)
fg_dorothy = add_couple(harold_sp.id, dorothy.id, union_year=1918)
fg_robert = add_couple(robert.id, edith_sp.id, union_year=1924,
                        is_divorced=True, union_end_year=1935)  # DIVORCE
fg_robert2 = add_couple(robert.id, clara_sp.id, union_year=1937)  # REMARRIAGE
fg_virginia = add_couple(fred_sp.id, virginia.id, union_year=1922)
fg_frank = add_couple(frank_m.id, josephine_sp.id, union_year=1926)

# ═══════════════════════════════════════════════════════════════════════
# GENERATION 4 — Great-grandchildren (born ~1917-1940)
# ═══════════════════════════════════════════════════════════════════════

# William & Mary's children
richard = add_person(id=uid(), given_name="Richard", surname="Williams",
    sex="MALE", birth_year=1917, death_year=1995, is_living=False,
    born_city="Boston", notes="WWII Navy veteran.", generation=4)
add_child(fg_william, richard.id)

elizabeth = add_person(id=uid(), given_name="Elizabeth", surname="Williams",
    sex="FEMALE", birth_year=1920, death_year=2005, is_living=False,
    born_city="Boston", generation=4)
add_child(fg_william, elizabeth.id)

# Harold & Dorothy's children
paul_d = add_person(id=uid(), given_name="Paul", surname="Davis",
    sex="MALE", birth_year=1919, death_year=2000, is_living=False,
    born_city="Cleveland", generation=4)
add_child(fg_dorothy, paul_d.id)

# Robert & Edith's child (before divorce — biological)
joseph_w = add_person(id=uid(), given_name="Joseph", surname="Williams",
    sex="MALE", birth_year=1926, death_year=2010, is_living=False,
    born_city="Chicago", notes="Child of Robert's first marriage.", generation=4)
add_child(fg_robert, joseph_w.id)
# Joseph is also a STEP child in Robert's second marriage
add_child(fg_robert2, joseph_w.id, "STEP")

# Robert & Clara's children (second marriage — half-siblings to Joseph)
nancy = add_person(id=uid(), given_name="Nancy", surname="Williams",
    sex="FEMALE", birth_year=1938, death_year=2020, is_living=False,
    born_city="Chicago", notes="Half-sister of Joseph.", generation=4)
add_child(fg_robert2, nancy.id)

# Frederick & Virginia's children
donald = add_person(id=uid(), given_name="Donald", surname="Clark",
    sex="MALE", birth_year=1923, death_year=2008, is_living=False,
    born_city="St. Louis", generation=4)
add_child(fg_virginia, donald.id)

jean = add_person(id=uid(), given_name="Jean", surname="Clark",
    sex="FEMALE", birth_year=1926, death_year=2015, is_living=False,
    born_city="St. Louis", generation=4)
add_child(fg_virginia, jean.id)

# Frank & Josephine's children
raymond = add_person(id=uid(), given_name="Raymond", surname="Mitchell",
    sex="MALE", birth_year=1928, death_year=2012, is_living=False,
    born_city="Baltimore", notes="Foster child, raised as their own.", generation=4)
add_child(fg_frank, raymond.id, "FOSTER")

gloria = add_person(id=uid(), given_name="Gloria", surname="Mitchell",
    sex="FEMALE", birth_year=1930, is_living=True,
    born_city="Baltimore", notes="Oldest living family member at 96.", generation=4)
add_child(fg_frank, gloria.id)

# Gen 4 spouses
barbara_sp = add_person(id=uid(), given_name="Barbara", surname="Wilson",
    sex="FEMALE", birth_year=1920, death_year=1998, is_living=False,
    born_city="Denver", generation=4)

kenneth_sp = add_person(id=uid(), given_name="Kenneth", surname="Harris",
    sex="MALE", birth_year=1918, death_year=1990, is_living=False,
    born_city="Atlanta", generation=4)

sandra_sp = add_person(id=uid(), given_name="Sandra", surname="Lewis",
    sex="FEMALE", birth_year=1928, death_year=2015, is_living=False,
    born_city="Nashville", generation=4)

shirley_sp = add_person(id=uid(), given_name="Shirley", surname="Martin",
    sex="FEMALE", birth_year=1940, is_living=True,
    born_city="Miami", generation=4)

patrick_sp = add_person(id=uid(), given_name="Patrick", surname="O'Neill",
    sex="MALE", birth_year=1922, death_year=2005, is_living=False,
    born_city="Boston", born_country="United States", generation=4)

evelyn_sp = add_person(id=uid(), given_name="Evelyn", surname="Torres",
    sex="FEMALE", birth_year=1930, death_year=2018, is_living=False,
    born_city="San Francisco", generation=4)

# Gen 4 marriages
fg_richard = add_couple(richard.id, barbara_sp.id, union_year=1942)
fg_elizabeth = add_couple(kenneth_sp.id, elizabeth.id, union_year=1944)
fg_joseph = add_couple(joseph_w.id, sandra_sp.id, union_year=1950)
fg_nancy = add_couple(patrick_sp.id, nancy.id, union_year=1958)
fg_donald = add_couple(donald.id, shirley_sp.id, union_year=1948)
fg_raymond = add_couple(raymond.id, evelyn_sp.id, union_year=1952, union_type="PARTNERSHIP")

# ═══════════════════════════════════════════════════════════════════════
# GENERATION 5 — (born ~1943-1965)
# ═══════════════════════════════════════════════════════════════════════

# Richard & Barbara's children
michael = add_person(id=uid(), given_name="Michael", surname="Williams",
    sex="MALE", birth_year=1943, is_living=True,
    born_city="Denver", notes="Retired professor of history.", generation=5)
add_child(fg_richard, michael.id)

susan = add_person(id=uid(), given_name="Susan", surname="Williams",
    sex="FEMALE", birth_year=1946, is_living=True,
    born_city="Denver", generation=5)
add_child(fg_richard, susan.id)

# Kenneth & Elizabeth's children
steven = add_person(id=uid(), given_name="Steven", surname="Harris",
    sex="MALE", birth_year=1945, is_living=True,
    born_city="Atlanta", generation=5)
add_child(fg_elizabeth, steven.id)

# Joseph & Sandra's children
david = add_person(id=uid(), given_name="David", surname="Williams",
    sex="MALE", birth_year=1952, is_living=True,
    born_city="Chicago", generation=5)
add_child(fg_joseph, david.id)

karen = add_person(id=uid(), given_name="Karen", surname="Williams",
    sex="FEMALE", birth_year=1955, is_living=True,
    born_city="Chicago", generation=5)
add_child(fg_joseph, karen.id)

# Patrick & Nancy's children
brian = add_person(id=uid(), given_name="Brian", surname="O'Neill",
    sex="MALE", birth_year=1960, is_living=True,
    born_city="Boston", generation=5)
add_child(fg_nancy, brian.id)

# Donald & Shirley's children
timothy = add_person(id=uid(), given_name="Timothy", surname="Clark",
    sex="MALE", birth_year=1950, is_living=True,
    born_city="St. Louis", generation=5)
add_child(fg_donald, timothy.id)

# Raymond & Evelyn's child
diane = add_person(id=uid(), given_name="Diane", surname="Mitchell",
    sex="FEMALE", birth_year=1954, is_living=True,
    born_city="San Francisco", generation=5)
add_child(fg_raymond, diane.id)

# Gen 5 spouses
janet_sp = add_person(id=uid(), given_name="Janet", surname="Peterson",
    sex="FEMALE", birth_year=1945, is_living=True,
    born_city="Seattle", generation=5)

roger_sp = add_person(id=uid(), given_name="Roger", surname="Campbell",
    sex="MALE", birth_year=1944, is_living=True,
    born_city="Portland", generation=5)

carol_sp = add_person(id=uid(), given_name="Carol", surname="Reed",
    sex="FEMALE", birth_year=1948, is_living=True,
    born_city="Minneapolis", generation=5)

mark_sp = add_person(id=uid(), given_name="Mark", surname="Foster",
    sex="MALE", birth_year=1953, is_living=True,
    born_city="Dallas", generation=5)

laura_sp = add_person(id=uid(), given_name="Laura", surname="Evans",
    sex="FEMALE", birth_year=1960, is_living=True,
    born_city="Phoenix", generation=5)

pamela_sp = add_person(id=uid(), given_name="Pamela", surname="Cooper",
    sex="FEMALE", birth_year=1952, is_living=True,
    born_city="Tampa", generation=5)

# Gen 5 marriages — one COHABITATION
fg_michael = add_couple(michael.id, janet_sp.id, union_year=1968)
fg_susan = add_couple(roger_sp.id, susan.id, union_year=1970)
fg_david = add_couple(david.id, carol_sp.id, union_year=1978)
fg_karen = add_couple(mark_sp.id, karen.id, union_year=1980)
fg_brian = add_couple(brian.id, laura_sp.id, union_year=1985)
fg_timothy = add_couple(timothy.id, pamela_sp.id, union_year=1976, union_type="COHABITATION")

# Single parent family (Gen 5 → Gen 6)
fg_diane_single = FamilyGroup(id=uid(), union_type="UNKNOWN", parent_ids=[diane.id])
family_groups.append(fg_diane_single)

# ═══════════════════════════════════════════════════════════════════════
# GENERATION 6 — (born ~1970-1995)
# ═══════════════════════════════════════════════════════════════════════

# Michael & Janet's children
christopher = add_person(id=uid(), given_name="Christopher", surname="Williams",
    sex="MALE", birth_year=1970, is_living=True,
    born_city="Seattle", generation=6)
add_child(fg_michael, christopher.id)

jennifer = add_person(id=uid(), given_name="Jennifer", surname="Williams",
    sex="FEMALE", birth_year=1973, is_living=True,
    born_city="Seattle", generation=6)
add_child(fg_michael, jennifer.id)

# Roger & Susan's children
matthew = add_person(id=uid(), given_name="Matthew", surname="Campbell",
    sex="MALE", birth_year=1972, is_living=True,
    born_city="Portland", generation=6)
add_child(fg_susan, matthew.id)

# David & Carol's children
jessica = add_person(id=uid(), given_name="Jessica", surname="Williams",
    sex="FEMALE", birth_year=1980, is_living=True,
    born_city="Chicago", generation=6)
add_child(fg_david, jessica.id)

andrew = add_person(id=uid(), given_name="Andrew", surname="Williams",
    sex="MALE", birth_year=1983, is_living=True,
    born_city="Chicago", generation=6)
add_child(fg_david, andrew.id)

# Mark & Karen's child
stephanie = add_person(id=uid(), given_name="Stephanie", surname="Foster",
    sex="FEMALE", birth_year=1982, is_living=True,
    born_city="Dallas", generation=6)
add_child(fg_karen, stephanie.id)

# Brian & Laura's children
ryan = add_person(id=uid(), given_name="Ryan", surname="O'Neill",
    sex="MALE", birth_year=1987, is_living=True,
    born_city="Phoenix", generation=6)
add_child(fg_brian, ryan.id)

megan = add_person(id=uid(), given_name="Megan", surname="O'Neill",
    sex="FEMALE", birth_year=1990, is_living=True,
    born_city="Phoenix", generation=6)
add_child(fg_brian, megan.id)

# Timothy & Pamela's child
kyle = add_person(id=uid(), given_name="Kyle", surname="Clark",
    sex="MALE", birth_year=1978, is_living=True,
    born_city="St. Louis", generation=6)
add_child(fg_timothy, kyle.id)

# Diane's child (single parent)
amber = add_person(id=uid(), given_name="Amber", surname="Mitchell",
    sex="FEMALE", birth_year=1980, is_living=True,
    born_city="San Francisco", generation=6)
add_child(fg_diane_single, amber.id)

# Gen 6 spouses
amanda_sp = add_person(id=uid(), given_name="Amanda", surname="Garcia",
    sex="FEMALE", birth_year=1972, is_living=True,
    born_city="Los Angeles", generation=6)

derek_sp = add_person(id=uid(), given_name="Derek", surname="Nguyen",
    sex="MALE", birth_year=1971, is_living=True,
    born_city="San Diego", generation=6)

rachel_sp = add_person(id=uid(), given_name="Rachel", surname="Patel",
    sex="FEMALE", birth_year=1982, is_living=True,
    born_city="Houston", generation=6)

nicole_sp = add_person(id=uid(), given_name="Nicole", surname="Kim",
    sex="FEMALE", birth_year=1985, is_living=True,
    born_city="San Francisco", generation=6)

tyler_sp = add_person(id=uid(), given_name="Tyler", surname="Brooks",
    sex="MALE", birth_year=1988, is_living=True,
    born_city="Austin", generation=6)

marcus_sp = add_person(id=uid(), given_name="Marcus", surname="Rivera",
    sex="MALE", birth_year=1978, is_living=True,
    born_city="Miami", generation=6)

# Gen 6 marriages — includes a DIVORCE + REMARRIAGE
fg_chris = add_couple(christopher.id, amanda_sp.id, union_year=1996)
fg_jennifer = add_couple(derek_sp.id, jennifer.id, union_year=1998,
                          is_divorced=True, union_end_year=2008)  # DIVORCED

# Jennifer remarries
jason_sp2 = add_person(id=uid(), given_name="Jason", surname="Wright",
    sex="MALE", birth_year=1975, is_living=True,
    born_city="Denver", generation=6)
fg_jennifer2 = add_couple(jason_sp2.id, jennifer.id, union_year=2010)  # REMARRIAGE

fg_andrew = add_couple(andrew.id, rachel_sp.id, union_year=2008)
fg_ryan = add_couple(ryan.id, nicole_sp.id, union_year=2014)
fg_megan = add_couple(tyler_sp.id, megan.id, union_year=2016)
fg_amber = add_couple(marcus_sp.id, amber.id, union_year=2005, union_type="PARTNERSHIP")

# ═══════════════════════════════════════════════════════════════════════
# GENERATION 7 — (born ~1997-2012)
# ═══════════════════════════════════════════════════════════════════════

# Christopher & Amanda's children
ethan = add_person(id=uid(), given_name="Ethan", surname="Williams",
    sex="MALE", birth_year=1998, is_living=True,
    born_city="Los Angeles", generation=7)
add_child(fg_chris, ethan.id)

olivia = add_person(id=uid(), given_name="Olivia", surname="Williams",
    sex="FEMALE", birth_year=2001, is_living=True,
    born_city="Los Angeles", generation=7)
add_child(fg_chris, olivia.id)

# Derek & Jennifer's child (before divorce)
noah = add_person(id=uid(), given_name="Noah", surname="Nguyen",
    sex="MALE", birth_year=2000, is_living=True,
    born_city="San Diego", generation=7)
add_child(fg_jennifer, noah.id)
add_child(fg_jennifer2, noah.id, "STEP")  # Step-child in Jennifer's 2nd marriage

# Jason & Jennifer's child (after remarriage)
lily = add_person(id=uid(), given_name="Lily", surname="Wright",
    sex="FEMALE", birth_year=2012, is_living=True,
    born_city="Denver", notes="Half-sister of Noah.", generation=7)
add_child(fg_jennifer2, lily.id)

# Andrew & Rachel's children
sophia = add_person(id=uid(), given_name="Sophia", surname="Williams",
    sex="FEMALE", birth_year=2010, is_living=True,
    born_city="Houston", generation=7)
add_child(fg_andrew, sophia.id)

liam = add_person(id=uid(), given_name="Liam", surname="Williams",
    sex="MALE", birth_year=2012, is_living=True,
    born_city="Houston", generation=7)
add_child(fg_andrew, liam.id)

# Ryan & Nicole's child
emma = add_person(id=uid(), given_name="Emma", surname="O'Neill",
    sex="FEMALE", birth_year=2016, is_living=True,
    born_city="San Francisco", generation=7)
add_child(fg_ryan, emma.id)

# Tyler & Megan's child
lucas = add_person(id=uid(), given_name="Lucas", surname="Brooks",
    sex="MALE", birth_year=2018, is_living=True,
    born_city="Austin", generation=7)
add_child(fg_megan, lucas.id)

# Marcus & Amber's children (adoptive)
maya = add_person(id=uid(), given_name="Maya", surname="Rivera",
    sex="FEMALE", birth_year=2008, is_living=True,
    born_city="Miami", notes="Adopted from Guatemala in 2010.", generation=7)
add_child(fg_amber, maya.id, "ADOPTIVE")

# Gen 7 spouse — Ethan marries young
hannah_sp = add_person(id=uid(), given_name="Hannah", surname="Park",
    sex="FEMALE", birth_year=1999, is_living=True,
    born_city="Seattle", generation=7)
fg_ethan = add_couple(ethan.id, hannah_sp.id, union_year=2022)

# ═══════════════════════════════════════════════════════════════════════
# GENERATION 8 — Babies & toddlers (born ~2023-2025)
# ═══════════════════════════════════════════════════════════════════════

ava = add_person(id=uid(), given_name="Ava", surname="Williams",
    sex="FEMALE", birth_year=2023, is_living=True,
    born_city="Seattle", notes="The newest Williams!", generation=8)
add_child(fg_ethan, ava.id)

james_newest = add_person(id=uid(), given_name="James", surname="Williams",
    sex="MALE", birth_year=2025, is_living=True,
    born_city="Seattle", notes="Born June 2025.", generation=8)
add_child(fg_ethan, james_newest.id)


# ═══════════════════════════════════════════════════════════════════════
# PHOTO DOWNLOAD & UPLOAD
# ═══════════════════════════════════════════════════════════════════════

GALLERY_CAPTIONS = [
    ["Family portrait", "At the park", "Holiday gathering"],
    ["Wedding day", "Sunday brunch", "Garden party"],
    ["Summer vacation", "Birthday celebration", "Reunion photo"],
    ["Graduation day", "Thanksgiving dinner", "Beach trip"],
    ["Christmas morning", "Anniversary dinner", "Picnic afternoon"],
    ["Baby shower", "Camping trip", "School play"],
    ["Road trip stop", "Backyard BBQ", "Museum visit"],
    ["First day of school", "Snow day", "Farmers market"],
]


def download_image(url: str, timeout: int = 15) -> bytes | None:
    try:
        resp = requests.get(url, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
        return resp.content
    except Exception as e:
        print(f"  [WARN] Failed to download {url}: {e}", file=sys.stderr)
        return None


def make_placeholder_jpeg(width: int, height: int, color: tuple, label: str = "") -> bytes:
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=80)
    return buf.getvalue()


def upload_photos(s3_client):
    global _male_portrait_idx, _female_portrait_idx

    total = len(persons)
    print(f"\nUploading photos for {total} persons...", file=sys.stderr)

    male_idx = 0
    female_idx = 0

    for i, p in enumerate(persons.values()):
        pct = (i + 1) / total * 100
        print(f"  [{i+1}/{total}] ({pct:.0f}%) {p.given_name} {p.surname}...", file=sys.stderr)

        # ── Profile photo ────────────────────────────────────────
        if p.sex == "MALE":
            portrait_url = f"https://randomuser.me/api/portraits/men/{male_idx % 100}.jpg"
            male_idx += 1
        else:
            portrait_url = f"https://randomuser.me/api/portraits/women/{female_idx % 100}.jpg"
            female_idx += 1

        img_data = download_image(portrait_url)
        if img_data is None:
            colors = {"MALE": (70, 130, 180), "FEMALE": (219, 112, 147)}
            img_data = make_placeholder_jpeg(300, 300, colors.get(p.sex, (128, 128, 128)))

        photo_uuid = uid()
        photo_key = f"tenants/{TENANT_ID}/trees/{TREE_ID}/persons/{p.id}/photo/{photo_uuid}.jpg"
        s3_client.put_object(
            Bucket=S3_BUCKET, Key=photo_key,
            Body=img_data, ContentType="image/jpeg",
        )
        p.photo_s3_key = photo_key

        # ── Gallery photos (3 per person) ────────────────────────
        captions = random.choice(GALLERY_CAPTIONS)
        for pos in range(3):
            seed_val = f"{p.id}-{pos}"
            gallery_url = f"https://picsum.photos/seed/{seed_val}/400/300"
            gal_data = download_image(gallery_url)
            if gal_data is None:
                colors = [(180, 200, 150), (150, 180, 200), (200, 170, 150)]
                gal_data = make_placeholder_jpeg(400, 300, colors[pos])

            gal_photo_id = uid()
            gal_key = f"tenants/{TENANT_ID}/trees/{TREE_ID}/persons/{p.id}/gallery/{gal_photo_id}.jpg"
            s3_client.put_object(
                Bucket=S3_BUCKET, Key=gal_key,
                Body=gal_data, ContentType="image/jpeg",
            )
            p.gallery_keys.append((gal_photo_id, gal_key, captions[pos]))

    print(f"  Done — uploaded {total} profiles + {total * 3} gallery photos.", file=sys.stderr)


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
        # Tree
        cur.execute("""
            INSERT INTO family_trees (id, tenant_id, name, description, created_at, updated_at)
            VALUES (%s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (id) DO NOTHING
        """, (TREE_ID, TENANT_ID, TREE_NAME,
              "A handcrafted 8-generation family with photos, divorces, adoptions, and all relationship types."))

        # Tree membership
        cur.execute("""
            INSERT INTO tree_members (id, tree_id, user_id, tenant_id, role, joined_at, created_at, updated_at)
            VALUES (gen_random_uuid(), %s, %s, %s, 'ADMIN', NOW(), NOW(), NOW())
            ON CONFLICT ON CONSTRAINT uq_tree_member DO NOTHING
        """, (TREE_ID, USER_ID, TENANT_ID))

        # Persons
        for p in persons.values():
            cur.execute("""
                INSERT INTO persons (
                    id, tree_id, tenant_id, display_given_name, display_surname,
                    sex, birth_year, death_year, is_living, is_deceased, is_deleted,
                    born_city, born_country, died_city, died_country,
                    notes, photo_url, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, false,
                    %s, %s, %s, %s,
                    %s, %s, NOW(), NOW()
                )
            """, (
                p.id, TREE_ID, TENANT_ID, p.given_name, p.surname,
                p.sex, p.birth_year, p.death_year, p.is_living, not p.is_living,
                p.born_city, p.born_country, p.died_city, p.died_country,
                p.notes, p.photo_s3_key,
            ))

        # Family groups
        for fg in family_groups:
            p1 = fg.parent_ids[0] if len(fg.parent_ids) > 0 else None
            p2 = fg.parent_ids[1] if len(fg.parent_ids) > 1 else None
            cur.execute("""
                INSERT INTO family_groups (
                    id, tree_id, tenant_id, union_type,
                    parent1_id, parent2_id, is_divorced,
                    union_date_year, union_end_date_year,
                    created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            """, (
                fg.id, TREE_ID, TENANT_ID, fg.union_type,
                p1, p2, fg.is_divorced,
                fg.union_year, fg.union_end_year,
            ))

        # Family group members
        for fg in family_groups:
            for pid in fg.parent_ids:
                cur.execute("""
                    INSERT INTO family_group_members (
                        id, family_group_id, person_id, role, parentage_type,
                        tree_id, tenant_id, created_at, updated_at
                    ) VALUES (gen_random_uuid(), %s, %s, 'PARENT', NULL, %s, %s, NOW(), NOW())
                """, (fg.id, pid, TREE_ID, TENANT_ID))

            for child_id, parentage_type in fg.children:
                cur.execute("""
                    INSERT INTO family_group_members (
                        id, family_group_id, person_id, role, parentage_type,
                        tree_id, tenant_id, created_at, updated_at
                    ) VALUES (gen_random_uuid(), %s, %s, 'CHILD', %s, %s, %s, NOW(), NOW())
                """, (fg.id, child_id, parentage_type, TREE_ID, TENANT_ID))

        # Gallery photos
        for p in persons.values():
            for gal_photo_id, gal_key, caption in p.gallery_keys:
                cur.execute("""
                    INSERT INTO person_gallery_photos (
                        id, person_id, tree_id, tenant_id,
                        photo_url, caption, position, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                """, (
                    gal_photo_id, p.id, TREE_ID, TENANT_ID,
                    gal_key, caption,
                    p.gallery_keys.index((gal_photo_id, gal_key, caption)),
                ))

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
    print(f"Family tree: {len(persons)} persons across 8 generations", file=sys.stderr)
    print(f"Family groups: {len(family_groups)}", file=sys.stderr)

    gen_counts = {}
    for p in persons.values():
        gen_counts[p.generation] = gen_counts.get(p.generation, 0) + 1
    for g in sorted(gen_counts):
        print(f"  Gen {g}: {gen_counts[g]} persons", file=sys.stderr)

    # Relationship type summary
    parentage_counts: dict[str, int] = {}
    union_counts: dict[str, int] = {}
    divorced = 0
    single_parent = 0
    for fg in family_groups:
        union_counts[fg.union_type] = union_counts.get(fg.union_type, 0) + 1
        if fg.is_divorced:
            divorced += 1
        if len(fg.parent_ids) == 1:
            single_parent += 1
        for _, pt in fg.children:
            parentage_counts[pt] = parentage_counts.get(pt, 0) + 1

    print(f"\nUnion types: {dict(sorted(union_counts.items()))}", file=sys.stderr)
    print(f"Parentage:   {dict(sorted(parentage_counts.items()))}", file=sys.stderr)
    print(f"Divorced:    {divorced}", file=sys.stderr)
    print(f"Single-parent: {single_parent}", file=sys.stderr)

    # S3 client
    print(f"\nConnecting to MinIO at {S3_ENDPOINT}...", file=sys.stderr)
    s3 = boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        region_name="us-east-1",
        config=BotoCfg(signature_version="s3v4"),
    )

    upload_photos(s3)
    insert_into_db()

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"Done! Tree '{TREE_NAME}' is ready.", file=sys.stderr)
    print(f"Log in as nirajbjk@gmail.com at http://localhost:7006", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)


if __name__ == "__main__":
    main()
