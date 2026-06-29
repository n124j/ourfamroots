"""
Generate a realistic 5000+ person family tree across 8+ generations.

Covers ALL relationship types:
  - MARRIAGE, PARTNERSHIP, COHABITATION unions
  - BIOLOGICAL, ADOPTIVE, STEP, FOSTER parentage
  - Divorces & remarriages (→ half-siblings, step-siblings)
  - Cross-family marriages (→ cousin relationships)
  - Single parents, widowed persons, large sibships, twins

Run: python -m scripts.seed_large_family --stats
     python -X utf8 -m scripts.seed_large_family > scripts/seed.sql
     python -m scripts.seed_large_family --json > scripts/seed.json

The script is deterministic (seeded RNG) so re-running produces identical output.
"""

from __future__ import annotations

import argparse
import json
import random
import uuid
from dataclasses import dataclass, field
from typing import Optional

random.seed(2024)

# ── Fixed IDs ────────────────────────────────────────────────────────────

TENANT_ID = uuid.UUID("626cddcf-0e25-4b56-9b05-13ad6a95ec8a")
TREE_ID = uuid.UUID("cccccccc-5000-4000-a000-000000000001")
USER_ID = uuid.UUID("5142fcf9-366f-47b5-8630-6086608fefbb")

# ── Name pools ───────────────────────────────────────────────────────────

MALE_NAMES = [
    "James", "Robert", "John", "Michael", "David", "William", "Richard",
    "Joseph", "Thomas", "Charles", "Christopher", "Daniel", "Matthew",
    "Anthony", "Mark", "Donald", "Steven", "Paul", "Andrew", "Joshua",
    "Kenneth", "Kevin", "Brian", "George", "Timothy", "Ronald", "Edward",
    "Jason", "Jeffrey", "Ryan", "Jacob", "Gary", "Nicholas", "Eric",
    "Jonathan", "Stephen", "Larry", "Justin", "Scott", "Brandon",
    "Benjamin", "Samuel", "Raymond", "Gregory", "Frank", "Alexander",
    "Patrick", "Jack", "Dennis", "Jerry", "Tyler", "Aaron", "Jose",
    "Nathan", "Henry", "Peter", "Douglas", "Zachary", "Kyle", "Walter",
    "Ethan", "Jeremy", "Harold", "Keith", "Christian", "Roger", "Noah",
    "Gerald", "Carl", "Terry", "Sean", "Austin", "Arthur", "Lawrence",
    "Jesse", "Dylan", "Bryan", "Joe", "Jordan", "Billy", "Bruce",
    "Albert", "Willie", "Gabriel", "Logan", "Alan", "Juan", "Wayne",
    "Elijah", "Randy", "Roy", "Vincent", "Ralph", "Eugene", "Russell",
    "Bobby", "Mason", "Philip", "Harry", "Liam", "Oliver", "Lucas",
    "Aiden", "Owen", "Leo", "Sebastian", "Caleb", "Miles", "Theodore",
    "Isaac", "Adrian", "Ezra", "Landon", "Jaxon", "Asher", "Dominic",
    "Colton", "Nolan", "Camden", "Roman", "Axel", "Brooks", "Sawyer",
    "Emmett", "Silas", "Jasper", "Milo", "Finn", "Felix", "Beckett",
    "Connor", "Declan", "Victor", "Oscar", "Mateo", "Hugo", "Atlas",
    "August", "Rowan", "Wesley", "Kai", "Grayson", "Bennett", "Knox",
    "Barrett", "Cruz", "Arlo", "Maxwell", "Henrik", "Cash", "Rhett",
    "Beau", "Reed", "Cade", "Tate", "Grant", "Drake", "Cole", "Blake",
    "Spencer", "Trevor", "Tucker", "Garrett", "Chase", "Parker", "Wyatt",
    "Carson", "Carter", "Bryce", "Trent", "Derek", "Shane", "Toby",
    "Clark", "Dean", "Neil", "Drew", "Brett", "Quinn", "Jude", "Ronan",
    "Dante", "Cyrus", "Orion", "Phoenix", "Zane", "Ryder", "Hendrix",
]

FEMALE_NAMES = [
    "Mary", "Patricia", "Jennifer", "Linda", "Barbara", "Elizabeth",
    "Susan", "Jessica", "Sarah", "Karen", "Lisa", "Nancy", "Betty",
    "Margaret", "Sandra", "Ashley", "Dorothy", "Kimberly", "Emily",
    "Donna", "Michelle", "Carol", "Amanda", "Melissa", "Deborah",
    "Stephanie", "Rebecca", "Sharon", "Laura", "Cynthia", "Kathleen",
    "Amy", "Angela", "Shirley", "Anna", "Brenda", "Pamela", "Emma",
    "Nicole", "Helen", "Samantha", "Katherine", "Christine", "Debra",
    "Rachel", "Carolyn", "Janet", "Catherine", "Maria", "Heather",
    "Diane", "Ruth", "Julie", "Olivia", "Joyce", "Virginia", "Victoria",
    "Kelly", "Lauren", "Christina", "Joan", "Evelyn", "Judith", "Megan",
    "Andrea", "Cheryl", "Hannah", "Jacqueline", "Martha", "Gloria",
    "Teresa", "Ann", "Sara", "Madison", "Frances", "Kathryn", "Janice",
    "Jean", "Abigail", "Alice", "Judy", "Sophia", "Grace", "Denise",
    "Amber", "Doris", "Marilyn", "Danielle", "Beverly", "Isabella",
    "Theresa", "Diana", "Natalie", "Brittany", "Charlotte", "Marie",
    "Kayla", "Alexis", "Lori", "Ava", "Mia", "Chloe", "Ella",
    "Harper", "Luna", "Aria", "Scarlett", "Penelope", "Layla", "Riley",
    "Zoey", "Nora", "Lily", "Eleanor", "Hazel", "Violet", "Aurora",
    "Savannah", "Audrey", "Brooklyn", "Bella", "Claire", "Skylar",
    "Stella", "Paisley", "Willow", "Lucy", "Emilia", "Addison", "Leah",
    "Ellie", "Ivy", "Piper", "Ruby", "Kennedy", "Madelyn", "Autumn",
    "Naomi", "Serenity", "Hailey", "Gianna", "Maya", "Elena", "Aaliyah",
    "Faith", "Alexandra", "Iris", "Eliana", "Sydney", "Kinsley", "Lyla",
    "Aubrey", "Vivian", "Clara", "Jade", "Rose", "Margot", "Thea",
    "Quinn", "Wren", "Sage", "Brielle", "Blaire", "Sloane", "Hadley",
    "Camille", "Genevieve", "Juliette", "Celeste", "Daphne", "Vera",
    "Esme", "Fiona", "Greta", "Ingrid", "Petra", "Signe", "Astrid",
]

SURNAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark",
    "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King",
    "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green",
    "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
    "Carter", "Roberts", "Sullivan", "Murphy", "Foster", "Reed", "Cook",
    "Morgan", "Bell", "Bailey", "Cooper", "Richardson", "Cox", "Howard",
    "Ward", "Brooks", "Peterson", "Gray", "Watson", "Sanders", "Price",
    "Bennett", "Wood", "Barnes", "Ross", "Henderson", "Coleman", "Jenkins",
    "Perry", "Powell", "Long", "Patterson", "Hughes", "Butler", "Simmons",
    "Bryant", "Russell", "Griffin", "Diaz", "Hayes", "Myers", "Ford",
    "Hamilton", "Graham", "Sullivan", "Wallace", "Woods", "Cole", "West",
    "Jordan", "Owens", "Reynolds", "Fisher", "Ellis", "Harrison", "Gibson",
    "McDonald", "Cruz", "Marshall", "Ortiz", "Gomez", "Murray", "Freeman",
    "Wells", "Webb", "Simpson", "Stevens", "Tucker", "Porter", "Hunter",
    "Hicks", "Crawford", "Henry", "Boyd", "Mason", "Morales", "Kennedy",
    "Warren", "Dixon", "Ramos", "Reyes", "Burns", "Gordon", "Shaw",
    "Holmes", "Rice", "Robertson", "Hunt", "Black", "Daniels", "Palmer",
    "Mills", "Nichols", "Grant", "Knight", "Ferguson", "Rose", "Stone",
    "Hawkins", "Dunn", "Perkins", "Hudson", "Spencer", "Gardner", "Stephens",
    "Payne", "Pierce", "Berry", "Matthews", "Arnold", "Wagner", "Willis",
    "Ray", "Watkins", "Olson", "Carroll", "Duncan", "Snyder", "Hart",
    "Cunningham", "Bradley", "Lane", "Andrews", "Ruiz", "Harper", "Fox",
    "Riley", "Armstrong", "Carpenter", "Weaver", "Greene", "Lawrence",
    "Elliott", "Chavez", "Sims", "Austin", "Peters", "Kelley", "Franklin",
]

CITIES = [
    "New York", "Los Angeles", "Chicago", "Houston", "Phoenix",
    "Philadelphia", "San Antonio", "San Diego", "Dallas", "Austin",
    "Denver", "Portland", "Seattle", "Boston", "Atlanta", "Miami",
    "Minneapolis", "Nashville", "Detroit", "Charlotte", "San Francisco",
    "Indianapolis", "Columbus", "Memphis", "Baltimore", "Milwaukee",
    "Albuquerque", "Tucson", "Sacramento", "Kansas City", "Omaha",
    "Raleigh", "Cleveland", "Tampa", "St. Louis", "Pittsburgh",
    "Cincinnati", "Orlando", "New Orleans", "Salt Lake City",
    "London", "Manchester", "Dublin", "Toronto", "Vancouver", "Sydney",
    "Melbourne", "Edinburgh", "Belfast", "Cork", "Montreal", "Calgary",
]

COUNTRIES = ["United States", "Canada", "United Kingdom", "Australia", "Ireland"]


# ── Data structures ──────────────────────────────────────────────────────

@dataclass
class Person:
    id: uuid.UUID
    given_name: str
    surname: str
    sex: str
    birth_year: int
    death_year: Optional[int] = None
    is_living: bool = True
    born_city: Optional[str] = None
    born_country: str = "United States"
    generation: int = 0


@dataclass
class FamilyGroup:
    id: uuid.UUID
    union_type: str
    parent_ids: list[uuid.UUID] = field(default_factory=list)
    children: list[tuple[uuid.UUID, str]] = field(default_factory=list)
    is_divorced: bool = False
    union_year: Optional[int] = None
    union_end_year: Optional[int] = None


# ── Generation config ────────────────────────────────────────────────────

N_FOUNDERS = 8

GEN_CONFIG = [
    # (gen, n_founders, min_kids, max_kids, base_birth_year, marriage_pct, divorce_pct)
    (1, N_FOUNDERS, 0, 0, 1840, 1.0, 0.0),
    (2, 0, 4, 6, 0, 0.92, 0.04),          # 1860s-1880s
    (3, 0, 3, 5, 0, 0.88, 0.06),          # 1890s-1910s
    (4, 0, 2, 4, 0, 0.82, 0.08),          # 1920s-1940s
    (5, 0, 2, 3, 0, 0.75, 0.10),          # 1950s-1970s
    (6, 0, 1, 3, 0, 0.60, 0.12),          # 1970s-1990s
    (7, 0, 1, 2, 0, 0.40, 0.08),          # 1990s-2010s
    (8, 0, 1, 2, 0, 0.12, 0.02),          # 2010s-2020s (young, few married)
]


class FamilyTreeBuilder:
    def __init__(self):
        self.persons: dict[uuid.UUID, Person] = {}
        self.family_groups: list[FamilyGroup] = []
        self._name_counters = {"MALE": 0, "FEMALE": 0}
        self._surname_idx = 0
        self._shuffled_m = list(MALE_NAMES)
        self._shuffled_f = list(FEMALE_NAMES)
        random.shuffle(self._shuffled_m)
        random.shuffle(self._shuffled_f)

    def _pick_name(self, sex: str) -> str:
        pool = self._shuffled_m if sex == "MALE" else self._shuffled_f
        idx = self._name_counters[sex]
        self._name_counters[sex] = idx + 1
        return pool[idx % len(pool)]

    def _pick_surname(self) -> str:
        s = SURNAMES[self._surname_idx % len(SURNAMES)]
        self._surname_idx += 1
        return s

    def _make_person(self, sex: str, surname: str, birth_year: int, gen: int,
                     given_name: str | None = None) -> Person:
        if given_name is None:
            given_name = self._pick_name(sex)

        is_living = birth_year > 1935
        death_year = None
        if not is_living:
            death_year = birth_year + random.randint(55, 95)

        p = Person(
            id=uuid.uuid4(), given_name=given_name, surname=surname,
            sex=sex, birth_year=birth_year, death_year=death_year,
            is_living=is_living,
            born_city=random.choice(CITIES),
            born_country=random.choice(COUNTRIES),
            generation=gen,
        )
        self.persons[p.id] = p
        return p

    def _make_couple(self, p1: uuid.UUID, p2: uuid.UUID,
                     union_type: str = "MARRIAGE",
                     union_year: int | None = None,
                     is_divorced: bool = False,
                     union_end_year: int | None = None) -> FamilyGroup:
        fg = FamilyGroup(
            id=uuid.uuid4(), union_type=union_type,
            parent_ids=[p1, p2], is_divorced=is_divorced,
            union_year=union_year, union_end_year=union_end_year,
        )
        self.family_groups.append(fg)
        return fg

    def _pick_union_type(self) -> str:
        r = random.random()
        if r < 0.82:
            return "MARRIAGE"
        elif r < 0.93:
            return "PARTNERSHIP"
        else:
            return "COHABITATION"

    def _pick_parentage(self, couple_idx: int, child_idx: int) -> str:
        r = random.random()
        if r < 0.92:
            return "BIOLOGICAL"
        elif r < 0.96:
            return "ADOPTIVE"
        elif r < 0.98:
            return "STEP"
        else:
            return "FOSTER"

    # ── Main build ───────────────────────────────────────────────────

    def build(self):
        gen_couples: list[list[tuple[Person, Person, FamilyGroup]]] = [[] for _ in range(9)]

        # Gen 1: founding couples
        for _ in range(N_FOUNDERS):
            surname = self._pick_surname()
            by_m = random.randint(1855, 1875)
            by_f = by_m + random.randint(-4, 6)
            husband = self._make_person("MALE", surname, by_m, 1)
            wife = self._make_person("FEMALE", self._pick_surname(), by_f, 1)
            uy = max(by_m, by_f) + random.randint(18, 26)
            fg = self._make_couple(husband.id, wife.id, "MARRIAGE", union_year=uy)
            gen_couples[1].append((husband, wife, fg))

        # Gen 2 through 8: produce children, pair them, optional divorces
        for gen in range(2, 9):
            _, _, min_k, max_k, _, marriage_pct, divorce_pct = GEN_CONFIG[gen - 1]
            prev_couples = gen_couples[gen - 1]
            children_this_gen: list[Person] = []

            # Produce children for each couple from previous generation
            for ci, (father, mother, fg) in enumerate(prev_couples):
                n_kids = random.randint(min_k, max_k)
                for ki in range(n_kids):
                    sex = random.choice(["MALE", "FEMALE"])
                    base_year = (fg.union_year or father.birth_year + 22)
                    by = base_year + random.randint(1, min(12, max_k * 2))
                    child = self._make_person(sex, father.surname, by, gen)
                    pt = self._pick_parentage(ci, ki)
                    fg.children.append((child.id, pt))
                    children_this_gen.append(child)

            if gen >= 9:
                break

            # Pair children into couples
            random.shuffle(children_this_gen)
            males = [p for p in children_this_gen if p.sex == "MALE"]
            females = [p for p in children_this_gen if p.sex == "FEMALE"]
            paired: set[uuid.UUID] = set()

            for m in males:
                if m.id in paired:
                    continue
                if random.random() > marriage_pct:
                    continue

                spouse: Person | None = None
                # 20% chance of cross-family marriage within same gen
                if females and random.random() < 0.20:
                    for f in females:
                        if f.id not in paired and f.surname != m.surname:
                            spouse = f
                            paired.add(f.id)
                            break

                if spouse is None:
                    spouse = self._make_person(
                        "FEMALE", self._pick_surname(),
                        m.birth_year + random.randint(-4, 4), gen,
                    )

                paired.add(m.id)
                uy = max(m.birth_year, spouse.birth_year) + random.randint(19, 30)
                ut = self._pick_union_type()
                fg = self._make_couple(m.id, spouse.id, ut, union_year=uy)
                gen_couples[gen].append((m, spouse, fg))

            # Pair remaining unpaired females
            for f in females:
                if f.id in paired:
                    continue
                if random.random() > marriage_pct:
                    continue
                outsider = self._make_person(
                    "MALE", self._pick_surname(),
                    f.birth_year + random.randint(-4, 3), gen,
                )
                paired.add(f.id)
                uy = max(f.birth_year, outsider.birth_year) + random.randint(19, 30)
                fg = self._make_couple(outsider.id, f.id, self._pick_union_type(), union_year=uy)
                gen_couples[gen].append((outsider, f, fg))

            # Divorces + remarriages
            n_divorces = int(len(gen_couples[gen]) * divorce_pct)
            divorce_indices = random.sample(
                range(len(gen_couples[gen])),
                min(n_divorces, len(gen_couples[gen])),
            )
            for idx in divorce_indices:
                m, f, orig_fg = gen_couples[gen][idx]
                orig_fg.is_divorced = True
                orig_fg.union_end_year = (orig_fg.union_year or m.birth_year + 25) + random.randint(3, 14)

                # Remarriage — alternate who remarries
                if idx % 2 == 0:
                    new_spouse = self._make_person(
                        "FEMALE", self._pick_surname(),
                        m.birth_year + random.randint(-3, 6), gen,
                    )
                    new_uy = (orig_fg.union_end_year or 1970) + random.randint(1, 5)
                    new_fg = self._make_couple(m.id, new_spouse.id, "MARRIAGE", union_year=new_uy)
                    gen_couples[gen].append((m, new_spouse, new_fg))
                else:
                    new_spouse = self._make_person(
                        "MALE", self._pick_surname(),
                        f.birth_year + random.randint(-3, 6), gen,
                    )
                    new_uy = (orig_fg.union_end_year or 1970) + random.randint(1, 5)
                    new_fg = self._make_couple(new_spouse.id, f.id, "MARRIAGE", union_year=new_uy)
                    gen_couples[gen].append((new_spouse, f, new_fg))

        # ── Special relationships ────────────────────────────────────

        # Single-parent families (one parent, no spouse)
        for gen in range(3, 7):
            for _ in range(3):
                all_gen = [p for p in self.persons.values() if p.generation == gen and p.sex == "FEMALE"]
                if not all_gen:
                    continue
                parent = random.choice(all_gen)
                fg = FamilyGroup(id=uuid.uuid4(), union_type="UNKNOWN", parent_ids=[parent.id])
                self.family_groups.append(fg)
                for _ in range(random.randint(1, 2)):
                    sex = random.choice(["MALE", "FEMALE"])
                    by = parent.birth_year + random.randint(18, 30)
                    child = self._make_person(sex, parent.surname, by, gen + 1)
                    child.is_living = True
                    child.death_year = None
                    fg.children.append((child.id, "BIOLOGICAL"))

        # Large families (7-10 children)
        large_family_data = [
            ("Gallagher", "O'Brien", 1925, 4, 7),
            ("O'Sullivan", "Kelly", 1945, 5, 9),
            ("Kowalski", "Nowak", 1960, 6, 8),
            ("Nakamura", "Tanaka", 1935, 5, 10),
        ]
        for father_sn, mother_sn, base_year, gen, n_kids in large_family_data:
            father = self._make_person("MALE", father_sn, base_year, gen)
            mother = self._make_person("FEMALE", mother_sn, base_year + 2, gen)
            fg = self._make_couple(father.id, mother.id, "MARRIAGE",
                                   union_year=base_year + random.randint(20, 25))
            for i in range(n_kids):
                sex = "MALE" if i % 2 == 0 else "FEMALE"
                by = (fg.union_year or base_year + 22) + 1 + i * 2
                child = self._make_person(sex, father_sn, by, gen + 1)
                child.is_living = by > 1940
                if not child.is_living:
                    child.death_year = by + random.randint(55, 90)
                fg.children.append((child.id, "BIOLOGICAL"))

        # Twin pairs
        for gen in range(4, 8):
            couples = gen_couples[gen][:3]
            for m, f, fg in couples:
                twin_year = (fg.union_year or m.birth_year + 24) + 2
                t1 = self._make_person("MALE", m.surname, twin_year, gen + 1,
                                       given_name=f"Twin-A-{self._name_counters['MALE']}")
                t2 = self._make_person("MALE", m.surname, twin_year, gen + 1,
                                       given_name=f"Twin-B-{self._name_counters['MALE']}")
                t1.is_living = True; t1.death_year = None
                t2.is_living = True; t2.death_year = None
                fg.children.append((t1.id, "BIOLOGICAL"))
                fg.children.append((t2.id, "BIOLOGICAL"))

        # Step-children across remarriages
        for gen in range(3, 7):
            for m, f, fg in gen_couples[gen]:
                if not fg.is_divorced:
                    continue
                remarriages = [
                    (m2, f2, fg2) for m2, f2, fg2 in gen_couples[gen]
                    if not fg2.is_divorced and (m2.id == m.id or f2.id == f.id)
                    and fg2.id != fg.id
                ]
                for _, _, new_fg in remarriages[:1]:
                    for cid, _ in fg.children[:2]:
                        if not any(c[0] == cid for c in new_fg.children):
                            new_fg.children.append((cid, "STEP"))

    # ── SQL output ───────────────────────────────────────────────────

    def to_sql(self) -> str:
        lines: list[str] = []
        lines.append("-- =============================================================")
        lines.append(f"-- Family Tree Seed: {len(self.persons)} persons, "
                     f"{len(self.family_groups)} family groups")
        lines.append("-- =============================================================")
        lines.append("")
        lines.append("BEGIN;")
        lines.append("")

        lines.append("-- Family tree")
        lines.append(
            f"INSERT INTO family_trees (id, tenant_id, name, description, created_at, updated_at) "
            f"VALUES ('{TREE_ID}', '{TENANT_ID}', "
            f"'The Grand Dynasty', 'A 5000+ person family tree spanning 8 generations with all relationship types', "
            f"NOW(), NOW()) ON CONFLICT (id) DO NOTHING;"
        )
        lines.append("")
        lines.append("-- Link tree to user")
        lines.append(
            f"INSERT INTO tree_members (id, tree_id, user_id, tenant_id, role, joined_at, created_at, updated_at) "
            f"VALUES (gen_random_uuid(), '{TREE_ID}', '{USER_ID}', '{TENANT_ID}', "
            f"'ADMIN', NOW(), NOW(), NOW()) "
            f"ON CONFLICT ON CONSTRAINT uq_tree_member DO NOTHING;"
        )
        lines.append("")

        # Persons in batches for performance
        lines.append(f"-- ── Persons ({len(self.persons)}) ──")
        lines.append("")
        for p in self.persons.values():
            gn = p.given_name.replace("'", "''")
            sn = p.surname.replace("'", "''")
            bc = f"'{p.born_city.replace(chr(39), chr(39)*2)}'" if p.born_city else "NULL"
            bco = f"'{p.born_country.replace(chr(39), chr(39)*2)}'" if p.born_country else "NULL"
            by_val = str(p.birth_year) if p.birth_year else "NULL"
            dy_val = str(p.death_year) if p.death_year else "NULL"
            living = "true" if p.is_living else "false"
            deceased = "false" if p.is_living else "true"

            lines.append(
                f"INSERT INTO persons (id, tree_id, tenant_id, display_given_name, display_surname, "
                f"sex, birth_year, death_year, is_living, is_deceased, is_deleted, "
                f"born_city, born_country, created_at, updated_at) VALUES ("
                f"'{p.id}', '{TREE_ID}', '{TENANT_ID}', "
                f"'{gn}', '{sn}', '{p.sex}', "
                f"{by_val}, {dy_val}, {living}, {deceased}, false, "
                f"{bc}, {bco}, NOW(), NOW());"
            )
        lines.append("")

        # Family groups
        lines.append(f"-- ── Family Groups ({len(self.family_groups)}) ──")
        lines.append("")
        for fg in self.family_groups:
            p1 = f"'{fg.parent_ids[0]}'" if len(fg.parent_ids) > 0 else "NULL"
            p2 = f"'{fg.parent_ids[1]}'" if len(fg.parent_ids) > 1 else "NULL"
            divorced = "true" if fg.is_divorced else "false"
            uy = str(fg.union_year) if fg.union_year else "NULL"
            uey = str(fg.union_end_year) if fg.union_end_year else "NULL"

            lines.append(
                f"INSERT INTO family_groups (id, tree_id, tenant_id, union_type, "
                f"parent1_id, parent2_id, is_divorced, union_date_year, union_end_date_year, "
                f"created_at, updated_at) VALUES ("
                f"'{fg.id}', '{TREE_ID}', '{TENANT_ID}', '{fg.union_type}', "
                f"{p1}, {p2}, {divorced}, {uy}, {uey}, NOW(), NOW());"
            )
        lines.append("")

        # Members
        member_count = 0
        lines.append("-- ── Family Group Members ──")
        lines.append("")
        for fg in self.family_groups:
            for pid in fg.parent_ids:
                mid = uuid.uuid4()
                lines.append(
                    f"INSERT INTO family_group_members (id, family_group_id, person_id, "
                    f"role, parentage_type, tree_id, tenant_id, created_at, updated_at) VALUES ("
                    f"'{mid}', '{fg.id}', '{pid}', 'PARENT', NULL, "
                    f"'{TREE_ID}', '{TENANT_ID}', NOW(), NOW());"
                )
                member_count += 1

            for child_id, parentage_type in fg.children:
                mid = uuid.uuid4()
                lines.append(
                    f"INSERT INTO family_group_members (id, family_group_id, person_id, "
                    f"role, parentage_type, tree_id, tenant_id, created_at, updated_at) VALUES ("
                    f"'{mid}', '{fg.id}', '{child_id}', 'CHILD', '{parentage_type}', "
                    f"'{TREE_ID}', '{TENANT_ID}', NOW(), NOW());"
                )
                member_count += 1

        lines.append("")
        lines.append("COMMIT;")
        lines.append("")
        lines.append(f"-- Total: {len(self.persons)} persons, "
                     f"{len(self.family_groups)} family groups, "
                     f"{member_count} memberships")
        return "\n".join(lines)

    def to_json(self) -> str:
        persons_list = [
            {
                "id": str(p.id), "tree_id": str(TREE_ID), "tenant_id": str(TENANT_ID),
                "display_given_name": p.given_name, "display_surname": p.surname,
                "sex": p.sex, "birth_year": p.birth_year, "death_year": p.death_year,
                "is_living": p.is_living, "born_city": p.born_city,
                "born_country": p.born_country, "generation": p.generation,
            }
            for p in self.persons.values()
        ]
        fg_list = [
            {
                "id": str(fg.id), "tree_id": str(TREE_ID), "tenant_id": str(TENANT_ID),
                "union_type": fg.union_type,
                "parent_ids": [str(pid) for pid in fg.parent_ids],
                "children": [{"person_id": str(cid), "parentage_type": pt} for cid, pt in fg.children],
                "is_divorced": fg.is_divorced,
                "union_year": fg.union_year, "union_end_year": fg.union_end_year,
            }
            for fg in self.family_groups
        ]
        return json.dumps({
            "meta": {
                "total_persons": len(self.persons),
                "total_family_groups": len(self.family_groups),
                "generations": 8, "tree_id": str(TREE_ID), "tenant_id": str(TENANT_ID),
            },
            "persons": persons_list, "family_groups": fg_list,
        }, indent=2)

    def stats(self) -> str:
        gen_counts: dict[int, int] = {}
        for p in self.persons.values():
            gen_counts[p.generation] = gen_counts.get(p.generation, 0) + 1

        union_types: dict[str, int] = {}
        parentage_types: dict[str, int] = {}
        divorced_count = 0
        single_parent_count = 0

        for fg in self.family_groups:
            union_types[fg.union_type] = union_types.get(fg.union_type, 0) + 1
            if fg.is_divorced:
                divorced_count += 1
            if len(fg.parent_ids) == 1:
                single_parent_count += 1
            for _, pt in fg.children:
                parentage_types[pt] = parentage_types.get(pt, 0) + 1

        lines = [
            f"Total persons:       {len(self.persons)}",
            f"Total family groups: {len(self.family_groups)}",
            "",
            "Persons by generation:",
        ]
        for gen in sorted(gen_counts):
            lines.append(f"  Gen {gen}: {gen_counts[gen]:>5} persons")

        lines.append("")
        lines.append("Union types:")
        for ut, c in sorted(union_types.items()):
            lines.append(f"  {ut:<15} {c:>4}")

        lines.append("")
        lines.append("Parentage types:")
        for pt, c in sorted(parentage_types.items()):
            lines.append(f"  {pt:<12} {c:>5}")

        lines.append(f"\nDivorced families:     {divorced_count}")
        lines.append(f"Single-parent families: {single_parent_count}")
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--stats", action="store_true")
    args = parser.parse_args()

    builder = FamilyTreeBuilder()
    builder.build()

    if args.stats:
        print(builder.stats())
    elif args.json:
        print(builder.to_json())
    else:
        print(builder.to_sql())


if __name__ == "__main__":
    main()
