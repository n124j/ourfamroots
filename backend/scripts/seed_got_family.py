"""
Game of Thrones family tree — all major houses & relationships.

Houses: Targaryen, Stark, Lannister, Baratheon, Tully, Tyrell,
        Martell, Greyjoy, Bolton, Arryn, Frey.

Photos are placeholders from randomuser.me & picsum.photos
(actual GoT images are HBO-copyrighted).

Run:  python -m scripts.seed_got_family
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

random.seed(777)

TENANT_ID = "626cddcf-0e25-4b56-9b05-13ad6a95ec8a"
TREE_ID = "ffffffff-0007-4000-a000-000000000001"
TREE_NAME = "Game of Thrones"
USER_ID = "5142fcf9-366f-47b5-8630-6086608fefbb"

DB_URL = "postgresql://postgres:postgres@localhost:7000/ourfamroots"
S3_ENDPOINT = "http://localhost:7002"
S3_BUCKET = "ourfamroots-media"
S3_KEY = "minioadmin"
S3_SECRET = "minioadmin"


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
    born_country: Optional[str] = None
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


def single_parent(pid) -> FG:
    f = FG(id=uid(), union_type="UNKNOWN", parent_ids=[pid])
    fgs.append(f)
    return f


def ch(fg, cid, pt="BIOLOGICAL"):
    fg.children.append((cid, pt))


# ── Helpers ──────────────────────────────────────────────────────────

N = "The North"
CL = "The Crownlands"
WL = "The Westerlands"
SL = "The Stormlands"
RL = "The Riverlands"
R = "The Reach"
D = "Dorne"
II = "The Iron Islands"
ES = "Essos"

# Years are AC (After Aegon's Conquest). Main events: 298-305 AC.

# ═════════════════════════════════════════════════════════════════════
# HOUSE TULLY — ancestors
# ═════════════════════════════════════════════════════════════════════

hoster = P(given_name="Hoster", surname="Tully", sex="MALE",
    birth_year=237, death_year=299, is_living=False,
    born_city="Riverrun", born_country=RL,
    notes="Lord Paramount of the Riverlands.", generation=1)

minisa = P(given_name="Minisa", surname="Whent", sex="FEMALE",
    birth_year=240, death_year=275, is_living=False,
    born_city="Harrenhal", born_country=RL, generation=1)

fg_hoster = marry(hoster.id, minisa.id, union_year=260)

brynden = P(given_name="Brynden", surname="Tully", sex="MALE",
    birth_year=235, death_year=300, is_living=False,
    born_city="Riverrun", born_country=RL,
    notes="The Blackfish. Hoster's brother. Never married.", generation=1)

catelyn = P(given_name="Catelyn", surname="Tully", sex="FEMALE",
    birth_year=264, death_year=299, is_living=False,
    born_city="Riverrun", born_country=RL,
    died_city="The Twins", died_country=RL,
    notes="Killed at the Red Wedding.", generation=2)
ch(fg_hoster, catelyn.id)

lysa = P(given_name="Lysa", surname="Tully", sex="FEMALE",
    birth_year=266, death_year=300, is_living=False,
    born_city="Riverrun", born_country=RL,
    died_city="The Eyrie", died_country="The Vale",
    notes="Pushed through the Moon Door by Littlefinger.", generation=2)
ch(fg_hoster, lysa.id)

edmure = P(given_name="Edmure", surname="Tully", sex="MALE",
    birth_year=274, is_living=True,
    born_city="Riverrun", born_country=RL,
    notes="Lord of Riverrun after the wars.", generation=2)
ch(fg_hoster, edmure.id)

# ═════════════════════════════════════════════════════════════════════
# HOUSE TARGARYEN
# ═════════════════════════════════════════════════════════════════════

aerys = P(given_name="Aerys II", surname="Targaryen", sex="MALE",
    birth_year=244, death_year=283, is_living=False,
    born_city="King's Landing", born_country=CL,
    died_city="King's Landing", died_country=CL,
    notes="The Mad King. Killed by Jaime Lannister.", generation=1)

rhaella = P(given_name="Rhaella", surname="Targaryen", sex="FEMALE",
    birth_year=246, death_year=284, is_living=False,
    born_city="King's Landing", born_country=CL,
    died_city="Dragonstone", died_country=CL,
    notes="Died giving birth to Daenerys.", generation=1)

fg_aerys = marry(aerys.id, rhaella.id, union_year=262)

rhaegar = P(given_name="Rhaegar", surname="Targaryen", sex="MALE",
    birth_year=259, death_year=283, is_living=False,
    born_city="King's Landing", born_country=CL,
    died_city="The Trident", died_country=RL,
    notes="Crown Prince. Killed by Robert Baratheon.", generation=2)
ch(fg_aerys, rhaegar.id)

viserys = P(given_name="Viserys", surname="Targaryen", sex="MALE",
    birth_year=276, death_year=298, is_living=False,
    born_city="King's Landing", born_country=CL,
    died_city="Vaes Dothrak", died_country=ES,
    notes="Crowned with molten gold by Khal Drogo.", generation=2)
ch(fg_aerys, viserys.id)

daenerys = P(given_name="Daenerys", surname="Targaryen", sex="FEMALE",
    birth_year=284, death_year=305, is_living=False,
    born_city="Dragonstone", born_country=CL,
    died_city="King's Landing", died_country=CL,
    notes="Mother of Dragons. Breaker of Chains.", generation=2)
ch(fg_aerys, daenerys.id)

# ═════════════════════════════════════════════════════════════════════
# HOUSE STARK
# ═════════════════════════════════════════════════════════════════════

rickard = P(given_name="Rickard", surname="Stark", sex="MALE",
    birth_year=230, death_year=282, is_living=False,
    born_city="Winterfell", born_country=N,
    died_city="King's Landing", died_country=CL,
    notes="Burned alive by the Mad King.", generation=1)

lyarra = P(given_name="Lyarra", surname="Stark", sex="FEMALE",
    birth_year=234, death_year=267, is_living=False,
    born_city="Winterfell", born_country=N, generation=1)

fg_rickard = marry(rickard.id, lyarra.id, union_year=258)

brandon_s = P(given_name="Brandon", surname="Stark", sex="MALE",
    birth_year=262, death_year=282, is_living=False,
    born_city="Winterfell", born_country=N,
    died_city="King's Landing", died_country=CL,
    notes="Strangled by the Mad King. Was betrothed to Catelyn.", generation=2)
ch(fg_rickard, brandon_s.id)

ned = P(given_name="Eddard", surname="Stark", sex="MALE",
    birth_year=263, death_year=298, is_living=False,
    born_city="Winterfell", born_country=N,
    died_city="King's Landing", died_country=CL,
    notes="Ned. Warden of the North. Hand of the King. Beheaded.", generation=2)
ch(fg_rickard, ned.id)

lyanna = P(given_name="Lyanna", surname="Stark", sex="FEMALE",
    birth_year=266, death_year=283, is_living=False,
    born_city="Winterfell", born_country=N,
    died_city="Tower of Joy", died_country=D,
    notes="Died after giving birth to Jon Snow.", generation=2)
ch(fg_rickard, lyanna.id)

benjen = P(given_name="Benjen", surname="Stark", sex="MALE",
    birth_year=267, death_year=304, is_living=False,
    born_city="Winterfell", born_country=N,
    notes="First Ranger of the Night's Watch.", generation=2)
ch(fg_rickard, benjen.id)

# Ned + Catelyn
fg_ned = marry(ned.id, catelyn.id, union_year=283)

robb = P(given_name="Robb", surname="Stark", sex="MALE",
    birth_year=283, death_year=299, is_living=False,
    born_city="Riverrun", born_country=RL,
    died_city="The Twins", died_country=RL,
    notes="The King in the North. Killed at the Red Wedding.", generation=3)
ch(fg_ned, robb.id)

sansa = P(given_name="Sansa", surname="Stark", sex="FEMALE",
    birth_year=286, is_living=True,
    born_city="Winterfell", born_country=N,
    notes="Queen in the North.", generation=3)
ch(fg_ned, sansa.id)

arya = P(given_name="Arya", surname="Stark", sex="FEMALE",
    birth_year=289, is_living=True,
    born_city="Winterfell", born_country=N,
    notes="Faceless assassin. Sailed west of Westeros.", generation=3)
ch(fg_ned, arya.id)

bran = P(given_name="Bran", surname="Stark", sex="MALE",
    birth_year=290, is_living=True,
    born_city="Winterfell", born_country=N,
    notes="The Three-Eyed Raven. King of the Six Kingdoms.", generation=3)
ch(fg_ned, bran.id)

rickon = P(given_name="Rickon", surname="Stark", sex="MALE",
    birth_year=295, death_year=303, is_living=False,
    born_city="Winterfell", born_country=N,
    died_city="Winterfell", died_country=N,
    notes="Killed by Ramsay Bolton before the Battle of the Bastards.", generation=3)
ch(fg_ned, rickon.id)

# Rhaegar + Elia Martell (first marriage)
elia = P(given_name="Elia", surname="Martell", sex="FEMALE",
    birth_year=257, death_year=283, is_living=False,
    born_city="Sunspear", born_country=D,
    died_city="King's Landing", died_country=CL,
    notes="Murdered during the Sack of King's Landing.", generation=2)

fg_rhaegar_elia = marry(rhaegar.id, elia.id, union_year=280)

rhaenys = P(given_name="Rhaenys", surname="Targaryen", sex="FEMALE",
    birth_year=280, death_year=283, is_living=False,
    born_city="King's Landing", born_country=CL,
    notes="Killed as an infant during the Sack.", generation=3)
ch(fg_rhaegar_elia, rhaenys.id)

aegon_baby = P(given_name="Aegon", surname="Targaryen", sex="MALE",
    birth_year=282, death_year=283, is_living=False,
    born_city="King's Landing", born_country=CL,
    notes="Killed as an infant during the Sack.", generation=3)
ch(fg_rhaegar_elia, aegon_baby.id)

# Rhaegar + Lyanna (secret marriage → Jon Snow)
fg_rhaegar_lyanna = marry(rhaegar.id, lyanna.id, union_year=282)

jon_snow = P(given_name="Jon Snow", surname="Targaryen", sex="MALE",
    birth_year=283, is_living=True,
    born_city="Tower of Joy", born_country=D,
    notes="Aegon Targaryen. Raised as Ned's bastard. King in the North.", generation=3)
ch(fg_rhaegar_lyanna, jon_snow.id)

# Daenerys + Khal Drogo
drogo = P(given_name="Khal Drogo", surname="", sex="MALE",
    birth_year=267, death_year=298, is_living=False,
    born_city="Vaes Dothrak", born_country=ES,
    died_city="Lhazareen", died_country=ES,
    notes="Khal of the Great Grass Sea.", generation=2)

fg_dany_drogo = marry(daenerys.id, drogo.id, union_year=298)

# ═════════════════════════════════════════════════════════════════════
# HOUSE LANNISTER
# ═════════════════════════════════════════════════════════════════════

tywin = P(given_name="Tywin", surname="Lannister", sex="MALE",
    birth_year=242, death_year=300, is_living=False,
    born_city="Casterly Rock", born_country=WL,
    died_city="King's Landing", died_country=CL,
    notes="Warden of the West. Hand of the King. Killed by Tyrion.", generation=1)

joanna = P(given_name="Joanna", surname="Lannister", sex="FEMALE",
    birth_year=245, death_year=273, is_living=False,
    born_city="Casterly Rock", born_country=WL,
    died_city="Casterly Rock", died_country=WL,
    notes="Died giving birth to Tyrion.", generation=1)

fg_tywin = marry(tywin.id, joanna.id, union_year=263)

cersei = P(given_name="Cersei", surname="Lannister", sex="FEMALE",
    birth_year=266, death_year=305, is_living=False,
    born_city="Casterly Rock", born_country=WL,
    died_city="King's Landing", died_country=CL,
    notes="Queen of the Seven Kingdoms. Crushed in the Red Keep collapse.", generation=2)
ch(fg_tywin, cersei.id)

jaime = P(given_name="Jaime", surname="Lannister", sex="MALE",
    birth_year=266, death_year=305, is_living=False,
    born_city="Casterly Rock", born_country=WL,
    died_city="King's Landing", died_country=CL,
    notes="The Kingslayer. Twin of Cersei. Died with her.", generation=2)
ch(fg_tywin, jaime.id)

tyrion = P(given_name="Tyrion", surname="Lannister", sex="MALE",
    birth_year=274, is_living=True,
    born_city="Casterly Rock", born_country=WL,
    notes="The Imp. Hand of the King to Bran the Broken.", generation=2)
ch(fg_tywin, tyrion.id)

# ═════════════════════════════════════════════════════════════════════
# HOUSE BARATHEON
# ═════════════════════════════════════════════════════════════════════

steffon = P(given_name="Steffon", surname="Baratheon", sex="MALE",
    birth_year=238, death_year=278, is_living=False,
    born_city="Storm's End", born_country=SL,
    notes="Lord of Storm's End. Died at sea.", generation=1)

cassana = P(given_name="Cassana", surname="Estermont", sex="FEMALE",
    birth_year=240, death_year=278, is_living=False,
    born_city="Greenstone", born_country=SL,
    notes="Died at sea with Steffon.", generation=1)

fg_steffon = marry(steffon.id, cassana.id, union_year=259)

robert_b = P(given_name="Robert", surname="Baratheon", sex="MALE",
    birth_year=262, death_year=298, is_living=False,
    born_city="Storm's End", born_country=SL,
    died_city="King's Landing", died_country=CL,
    notes="King of the Seven Kingdoms. Killed by a boar.", generation=2)
ch(fg_steffon, robert_b.id)

stannis = P(given_name="Stannis", surname="Baratheon", sex="MALE",
    birth_year=264, death_year=302, is_living=False,
    born_city="Storm's End", born_country=SL,
    died_city="Winterfell", died_country=N,
    notes="Self-proclaimed King. Executed by Brienne.", generation=2)
ch(fg_steffon, stannis.id)

renly = P(given_name="Renly", surname="Baratheon", sex="MALE",
    birth_year=277, death_year=299, is_living=False,
    born_city="Storm's End", born_country=SL,
    notes="Self-proclaimed King. Killed by Melisandre's shadow.", generation=2)
ch(fg_steffon, renly.id)

# Robert + Cersei (official marriage → children officially Baratheon)
fg_robert_cersei = marry(robert_b.id, cersei.id, union_year=284)

joffrey = P(given_name="Joffrey", surname="Baratheon", sex="MALE",
    birth_year=286, death_year=300, is_living=False,
    born_city="King's Landing", born_country=CL,
    notes="King. Poisoned at the Purple Wedding. Biological son of Jaime.", generation=3)
ch(fg_robert_cersei, joffrey.id)

myrcella = P(given_name="Myrcella", surname="Baratheon", sex="FEMALE",
    birth_year=290, death_year=302, is_living=False,
    born_city="King's Landing", born_country=CL,
    notes="Princess. Poisoned by Ellaria Sand.", generation=3)
ch(fg_robert_cersei, myrcella.id)

tommen = P(given_name="Tommen", surname="Baratheon", sex="MALE",
    birth_year=291, death_year=304, is_living=False,
    born_city="King's Landing", born_country=CL,
    notes="King. Suicide after the destruction of the Sept of Baelor.", generation=3)
ch(fg_robert_cersei, tommen.id)

# Robert's bastard
fg_robert_bastard = single_parent(robert_b.id)

gendry = P(given_name="Gendry", surname="Baratheon", sex="MALE",
    birth_year=284, is_living=True,
    born_city="King's Landing", born_country=CL,
    notes="Robert's bastard son. Legitimized. Lord of Storm's End.", generation=3)
ch(fg_robert_bastard, gendry.id)

# Stannis + Selyse
selyse = P(given_name="Selyse", surname="Florent", sex="FEMALE",
    birth_year=270, death_year=302, is_living=False,
    born_city="Brightwater Keep", born_country=R,
    notes="Follower of the Lord of Light. Hanged herself.", generation=2)

fg_stannis = marry(stannis.id, selyse.id, union_year=290)

shireen = P(given_name="Shireen", surname="Baratheon", sex="FEMALE",
    birth_year=299, death_year=302, is_living=False,
    born_city="Dragonstone", born_country=CL,
    notes="Burned at the stake by Melisandre.", generation=3)
ch(fg_stannis, shireen.id)

# ═════════════════════════════════════════════════════════════════════
# HOUSE TYRELL
# ═════════════════════════════════════════════════════════════════════

olenna = P(given_name="Olenna", surname="Tyrell", sex="FEMALE",
    birth_year=228, death_year=304, is_living=False,
    born_city="The Arbor", born_country=R,
    died_city="Highgarden", died_country=R,
    notes="The Queen of Thorns. Poisoned by Jaime.", generation=1)

luthor = P(given_name="Luthor", surname="Tyrell", sex="MALE",
    birth_year=225, death_year=280, is_living=False,
    born_city="Highgarden", born_country=R,
    notes="Lord of Highgarden. Fell off his horse.", generation=1)

fg_tyrell = marry(luthor.id, olenna.id, union_year=248)

mace = P(given_name="Mace", surname="Tyrell", sex="MALE",
    birth_year=256, death_year=304, is_living=False,
    born_city="Highgarden", born_country=R,
    died_city="King's Landing", died_country=CL,
    notes="Lord of Highgarden. Killed in the Sept of Baelor.", generation=2)
ch(fg_tyrell, mace.id)

alerie = P(given_name="Alerie", surname="Hightower", sex="FEMALE",
    birth_year=260, is_living=True,
    born_city="Oldtown", born_country=R, generation=2)

fg_mace = marry(mace.id, alerie.id, union_year=278)

margaery = P(given_name="Margaery", surname="Tyrell", sex="FEMALE",
    birth_year=283, death_year=304, is_living=False,
    born_city="Highgarden", born_country=R,
    died_city="King's Landing", died_country=CL,
    notes="Queen. Three husbands. Killed in the Sept of Baelor.", generation=3)
ch(fg_mace, margaery.id)

loras = P(given_name="Loras", surname="Tyrell", sex="MALE",
    birth_year=282, death_year=304, is_living=False,
    born_city="Highgarden", born_country=R,
    died_city="King's Landing", died_country=CL,
    notes="The Knight of Flowers. Killed in the Sept.", generation=3)
ch(fg_mace, loras.id)

# ═════════════════════════════════════════════════════════════════════
# HOUSE MARTELL
# ═════════════════════════════════════════════════════════════════════

doran = P(given_name="Doran", surname="Martell", sex="MALE",
    birth_year=248, death_year=302, is_living=False,
    born_city="Sunspear", born_country=D,
    notes="Prince of Dorne. Killed by Ellaria Sand.", generation=1)

oberyn = P(given_name="Oberyn", surname="Martell", sex="MALE",
    birth_year=258, death_year=300, is_living=False,
    born_city="Sunspear", born_country=D,
    died_city="King's Landing", died_country=CL,
    notes="The Red Viper. Skull crushed by the Mountain.", generation=1)

# Doran's son
fg_doran_single = single_parent(doran.id)

trystane = P(given_name="Trystane", surname="Martell", sex="MALE",
    birth_year=286, death_year=302, is_living=False,
    born_city="Sunspear", born_country=D,
    notes="Killed by the Sand Snakes.", generation=2)
ch(fg_doran_single, trystane.id)

# Oberyn + Ellaria
ellaria = P(given_name="Ellaria", surname="Sand", sex="FEMALE",
    birth_year=270, is_living=True,
    born_city="Sunspear", born_country=D,
    notes="Oberyn's paramour. Imprisoned by Cersei.", generation=1)

fg_oberyn = marry(oberyn.id, ellaria.id, union_type="PARTNERSHIP", union_year=278)

obara = P(given_name="Obara", surname="Sand", sex="FEMALE",
    birth_year=276, death_year=304, is_living=False,
    born_city="Sunspear", born_country=D,
    notes="Sand Snake. Killed by Euron Greyjoy.", generation=2)
ch(fg_oberyn, obara.id)

nymeria_s = P(given_name="Nymeria", surname="Sand", sex="FEMALE",
    birth_year=280, death_year=304, is_living=False,
    born_city="Sunspear", born_country=D,
    notes="Sand Snake. Killed by Euron Greyjoy.", generation=2)
ch(fg_oberyn, nymeria_s.id)

tyene = P(given_name="Tyene", surname="Sand", sex="FEMALE",
    birth_year=282, death_year=304, is_living=False,
    born_city="Sunspear", born_country=D,
    notes="Sand Snake. Poisoned by Cersei.", generation=2)
ch(fg_oberyn, tyene.id)

# ═════════════════════════════════════════════════════════════════════
# HOUSE GREYJOY
# ═════════════════════════════════════════════════════════════════════

quellon = P(given_name="Quellon", surname="Greyjoy", sex="MALE",
    birth_year=225, death_year=280, is_living=False,
    born_city="Pyke", born_country=II,
    notes="Lord of the Iron Islands.", generation=1)

quellon_wife = P(given_name="Lady", surname="Greyjoy", sex="FEMALE",
    birth_year=228, death_year=285, is_living=False,
    born_city="Pyke", born_country=II, generation=1)

fg_quellon = marry(quellon.id, quellon_wife.id, union_year=250)

balon = P(given_name="Balon", surname="Greyjoy", sex="MALE",
    birth_year=254, death_year=300, is_living=False,
    born_city="Pyke", born_country=II,
    notes="Lord of the Iron Islands. Pushed off a bridge by Euron.", generation=2)
ch(fg_quellon, balon.id)

euron = P(given_name="Euron", surname="Greyjoy", sex="MALE",
    birth_year=258, death_year=305, is_living=False,
    born_city="Pyke", born_country=II,
    died_city="King's Landing", died_country=CL,
    notes="Crow's Eye. Killed by Jaime Lannister.", generation=2)
ch(fg_quellon, euron.id)

alannys = P(given_name="Alannys", surname="Harlaw", sex="FEMALE",
    birth_year=258, is_living=True,
    born_city="Ten Towers", born_country=II, generation=2)

fg_balon = marry(balon.id, alannys.id, union_year=275)

yara = P(given_name="Yara", surname="Greyjoy", sex="FEMALE",
    birth_year=276, is_living=True,
    born_city="Pyke", born_country=II,
    notes="Queen of the Iron Islands.", generation=3)
ch(fg_balon, yara.id)

theon = P(given_name="Theon", surname="Greyjoy", sex="MALE",
    birth_year=279, death_year=305, is_living=False,
    born_city="Pyke", born_country=II,
    died_city="Winterfell", died_country=N,
    notes="Ward of Ned Stark. Died defending Bran from the Night King.", generation=3)
ch(fg_balon, theon.id)

# ═════════════════════════════════════════════════════════════════════
# HOUSE ARRYN
# ═════════════════════════════════════════════════════════════════════

jon_arryn = P(given_name="Jon", surname="Arryn", sex="MALE",
    birth_year=220, death_year=298, is_living=False,
    born_city="The Eyrie", born_country="The Vale",
    died_city="King's Landing", died_country=CL,
    notes="Hand of the King. Poisoned by Lysa at Littlefinger's behest.", generation=1)

fg_jon_lysa = marry(jon_arryn.id, lysa.id, union_year=282)

robin = P(given_name="Robin", surname="Arryn", sex="MALE",
    birth_year=292, is_living=True,
    born_city="The Eyrie", born_country="The Vale",
    notes="Lord of the Eyrie.", generation=3)
ch(fg_jon_lysa, robin.id)

# ═════════════════════════════════════════════════════════════════════
# HOUSE BOLTON
# ═════════════════════════════════════════════════════════════════════

roose = P(given_name="Roose", surname="Bolton", sex="MALE",
    birth_year=260, death_year=303, is_living=False,
    born_city="Dreadfort", born_country=N,
    notes="Lord of the Dreadfort. Stabbed by Ramsay.", generation=2)

fg_roose_single = single_parent(roose.id)

ramsay = P(given_name="Ramsay", surname="Bolton", sex="MALE",
    birth_year=282, death_year=303, is_living=False,
    born_city="Dreadfort", born_country=N,
    died_city="Winterfell", died_country=N,
    notes="The Bastard of Bolton. Fed to his own hounds.", generation=3)
ch(fg_roose_single, ramsay.id)

# ═════════════════════════════════════════════════════════════════════
# HOUSE FREY
# ═════════════════════════════════════════════════════════════════════

walder = P(given_name="Walder", surname="Frey", sex="MALE",
    birth_year=210, death_year=303, is_living=False,
    born_city="The Twins", born_country=RL,
    notes="The Late Lord Frey. Throat slit by Arya Stark.", generation=1)

fg_walder_single = single_parent(walder.id)

roslin = P(given_name="Roslin", surname="Frey", sex="FEMALE",
    birth_year=280, is_living=True,
    born_city="The Twins", born_country=RL, generation=2)
ch(fg_walder_single, roslin.id)

# Edmure + Roslin
fg_edmure = marry(edmure.id, roslin.id, union_year=299)

# ═════════════════════════════════════════════════════════════════════
# CROSS-HOUSE MARRIAGES (no children)
# ═════════════════════════════════════════════════════════════════════

# Robb + Talisa
talisa = P(given_name="Talisa", surname="Maegyr", sex="FEMALE",
    birth_year=281, death_year=299, is_living=False,
    born_city="Volantis", born_country=ES,
    died_city="The Twins", died_country=RL,
    notes="Healer from Volantis. Killed at the Red Wedding.", generation=3)

fg_robb = marry(robb.id, talisa.id, union_year=299)

# Renly + Margaery (brief)
fg_renly_marg = marry(renly.id, margaery.id, union_year=299)

# Joffrey + Margaery (brief — Purple Wedding)
fg_joff_marg = marry(joffrey.id, margaery.id, union_year=300)

# Tommen + Margaery
fg_tom_marg = marry(tommen.id, margaery.id, union_year=303)

# Sansa + Tyrion (forced)
fg_sansa_tyrion = marry(sansa.id, tyrion.id, union_year=300,
                         is_divorced=True, union_end_year=302)

# Sansa + Ramsay (forced)
fg_sansa_ramsay = marry(ramsay.id, sansa.id, union_year=302,
                         is_divorced=True, union_end_year=303)

# Myrcella betrothed to Trystane (PARTNERSHIP)
fg_myrcella_trystane = marry(trystane.id, myrcella.id, union_type="PARTNERSHIP", union_year=301)


# ═════════════════════════════════════════════════════════════════════
# PHOTO UPLOAD + DB INSERT  (same pattern as other seed scripts)
# ═════════════════════════════════════════════════════════════════════

CAPTIONS = [
    ["At the castle", "Council meeting", "Feast day"],
    ["Training yard", "Great hall", "The gardens"],
    ["Royal court", "Tourney day", "Weirwood grove"],
    ["Throne room", "War council", "Victory feast"],
    ["Harbor departure", "Market square", "Night's watch"],
    ["Dragon pit", "Sept of Baelor", "Kingsroad ride"],
    ["Jousting match", "At the Wall", "Coronation day"],
]


def download(url, timeout=15):
    try:
        r = requests.get(url, timeout=timeout, allow_redirects=True)
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
             "The great houses of Westeros — Targaryen, Stark, Lannister, Baratheon, Tyrell, Martell, Greyjoy, Tully, Arryn, Bolton, and Frey."))

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
    print(f"GoT Family Tree: {len(persons)} persons, {len(fgs)} family groups", file=sys.stderr)
    gc = {}
    for p in persons.values():
        gc[p.generation] = gc.get(p.generation, 0) + 1
    for g in sorted(gc):
        print(f"  Gen {g}: {gc[g]}", file=sys.stderr)

    houses: dict[str, int] = {}
    for p in persons.values():
        h = p.surname or "Unknown"
        houses[h] = houses.get(h, 0) + 1
    print("Houses:", file=sys.stderr)
    for h, c in sorted(houses.items(), key=lambda x: -x[1]):
        print(f"  {h}: {c}", file=sys.stderr)

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
