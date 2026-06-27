"""
Generate CSV of all relationships from Niraj Byanjankar to every other person
in The Byanjankar Family tree.
"""
import asyncio
import csv
import sys

from collections import defaultdict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.infrastructure.search.repository import (
    _infer_specific_label,
    _compute_edge_labels,
)

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@db:5432/ourfamroots"
TREE_ID = "212f254e-9eb1-4ada-82ef-cb062f03fc83"
FOCUS_ID = "fe8ba904-0882-4f4a-af66-8d20e89ee347"  # Samita Byanjankar

# Nepali translations keyed by the English label the backend produces.
# Compound labels like "Father / Son" are handled by splitting on " / " and " ↔ ".
NE = {
    "Same person": "एउटै व्यक्ति",
    "Spouses / Partners": "श्रीमान/श्रीमती",
    "Husband/Wife": "श्रीमान/श्रीमती",
    "Brother/Sister": "दाजुभाइ/दिदीबहिनी",
    "Brothers": "दाजुभाइहरू",
    "Sisters": "दिदीबहिनीहरू",
    "Brother & Sister": "दाजुभाइ र दिदीबहिनी",
    "Siblings": "दाजुभाइ/दिदीबहिनी",
    "Father": "बुबा",
    "Mother": "आमा",
    "Parent": "अभिभावक",
    "Son": "छोरा",
    "Daughter": "छोरी",
    "Child": "सन्तान",
    "Grandfather": "हजुरबुबा",
    "Grandmother": "हजुरआमा",
    "Grandparent": "हजुरबुबा/हजुरआमा",
    "Grandson": "नाति",
    "Granddaughter": "नातिनी",
    "Grandchild": "नाति/नातिनी",
    "Great-grandfather": "परबाजे",
    "Great-grandmother": "पर बज्यै",
    "Great-grandparent": "परबाजे/पर बज्यै",
    "Great-grandson": "प्रनाति",
    "Great-granddaughter": "प्रनातिनी",
    "Great-grandchild": "प्रनाति/प्रनातिनी",
    "Uncle": "काका/मामा",
    "Aunt": "फुपू/मौसी",
    "Uncle/Aunt": "काका/फुपू/मामा/मौसी",
    "Nephew": "भतिज/भाञ्जा",
    "Niece": "भतिजी/भाञ्जी",
    "Nephew/Niece": "भतिज/भाञ्जा/भतिजी/भाञ्जी",
    "Great-uncle": "ठूलोबुबा/ठूलोमामा",
    "Great-aunt": "ठूलीफुपू/ठूलीमौसी",
    "Great-uncle/aunt": "ठूलोबुबा/ठूलीफुपू",
    "Great-nephew": "प्रभतिज/प्रभाञ्जा",
    "Great-niece": "प्रभतिजी/प्रभाञ्जी",
    "Great-nephew/niece": "प्रभतिज/प्रभतिजी",
    # In-law
    "Brother-in-law": "साला",
    "Sister-in-law": "सालि",
    "Brother-in-law/Sister-in-law": "साला/सालि",
    "Father-in-law": "ससुरा",
    "Mother-in-law": "सासू",
    "Parent-in-law": "ससुरा/सासू",
    "Son-in-law": "ज्वाइँ",
    "Daughter-in-law": "बुहारी",
    "Child-in-law": "ज्वाइँ/बुहारी",
    "Brother-in-laws": "साला/ज्वाइँ",
    "Sister-in-laws": "ज्वाइँ/सालि",
    "Son-in-law/Father-in-law": "ज्वाइँ/ससुरा",
    "Son-in-law/Mother-in-law": "ज्वाइँ/सासू",
    "Daughter-in-law/Father-in-law": "बुहारी/ससुरा",
    "Daughter-in-law/Mother-in-law": "बुहारी/सासू",
    "Co-brother-in-law": "सधैँभाइ",
    "Co-sister-in-law": "जेठानी/भाउजू",
    "Co-in-law": "सधैँभाइ/जेठानी",
    "Brother-in-law (wife's brother)": "ज्वाइँ/साला",
    "Sister-in-law (wife's sister)": "ज्वाइँ/सालि",
    "Brother-in-law (husband's brother)": "भाउजू/देवर",
    "Sister-in-law (husband's sister)": "भाउजू/नन्द",
    "Sister-in-law (brother's wife)": "दाई/भाईबुहारी",
    "Brother-in-law (brother's husband)": "दाई/भाईबुहारी",
    "Brother-in-law (sister's husband)": "साला/ज्वाइँ",
    "Sister-in-law (sister's wife)": "सालि/ज्वाइँ",
    "Sister-in-law (elder brother's wife)": "भाउजू",
    "Sister-in-law (younger brother's wife)": "बुहारी",
    "Brother-in-law (elder brother's husband)": "भाउजू",
    "Brother-in-law (younger brother's husband)": "बुहारी",
    "Brother-in-law (elder sister's husband)": "सालो/भिनाजु",
    "Brother-in-law (younger sister's husband)": "साला/ज्वाइँ",
    "Sister-in-law (elder sister's wife)": "सालो/भिनाजु",
    "Sister-in-law (younger sister's wife)": "साला/ज्वाइँ",
    "Elder brother-in-law": "ज्वाइँ/जेठान",
    "Younger brother-in-law": "ज्वाइँ/साला (सानो)",
    "Brother-in-law (husband's younger brother)": "भाउजू/देवर",
    "Brother-in-law (husband's elder brother)": "जेठाज्यू/देउरानी",
    "Sister-in-law (husband's elder brother's wife)": "जेठानी/भाउजू",
    # Fallback labels
    "Direct family member": "प्रत्यक्ष परिवारको सदस्य",
    "Half-siblings / Step-siblings": "सौतेनी दाजुभाइ/दिदीबहिनी",
    "Co-parents": "सह-अभिभावक",
    "1st Cousins": "पहिलो चचेरा/ममेरा भाइबहिनी",
    "Parent, child, sibling, or spouse": "अभिभावक, सन्तान, दाजुभाइ/दिदीबहिनी, वा जीवनसाथी",
    "Grandparent/grandchild or uncle/aunt/nephew/niece": "हजुरबुबा-आमा/नाति वा काका/फुपू/मामा/मौसी",
    "Great-grandparent/grandchild or 1st cousin": "परबाजे/प्रनाति वा पहिलो चचेरा भाइबहिनी",
    "1st cousin once removed or 2×great-grandparent/grandchild": "पहिलो चचेरा भाइ एक पुस्ता टाढा वा दोस्रो परबाजे",
    "2nd cousin or 2×great-grandparent once removed": "दोस्रो चचेरा भाइबहिनी वा दोस्रो परबाजे एक पुस्ता टाढा",
    "2nd cousin once removed": "दोस्रो चचेरा भाइ एक पुस्ता टाढा",
    "Not connected": "जोडिएको छैन",
}


def translate(label: str) -> str:
    """Translate an English relationship label to Nepali."""
    if label in NE:
        return NE[label]
    # Compound labels: "Father / Son", "Uncle/Nephew"
    for sep in (" / ", " ↔ ", "/"):
        if sep in label:
            parts = label.split(sep)
            if all(NE.get(p.strip()) for p in parts):
                translated = [NE[p.strip()] for p in parts]
                return "/".join(translated)
            break
    # Distant relative fallback
    if label.startswith("Distant relative"):
        return label.replace("Distant relative", "टाढाको नातेदार")
    return label


async def main():
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # 1. Load all persons
        rows = (await session.execute(text("""
            SELECT id, display_given_name, display_surname, sex, birth_year
            FROM persons
            WHERE tree_id = :tree_id AND is_deleted = false
            ORDER BY display_surname, display_given_name
        """), {"tree_id": TREE_ID})).fetchall()

        person_map = {}
        sex_map = {}
        birth_year_map = {}
        for r in rows:
            pid = str(r.id)
            name = f"{r.display_given_name or ''} {r.display_surname or ''}".strip()
            person_map[pid] = name
            sex_map[pid] = r.sex
            birth_year_map[pid] = r.birth_year

        # 2. Load adjacency
        adj_rows = (await session.execute(text("""
            SELECT person_id, family_group_id, role
            FROM family_group_members
            WHERE tree_id = :tree_id
        """), {"tree_id": TREE_ID})).fetchall()

        person_to_fgs = defaultdict(list)
        fg_to_persons = defaultdict(list)
        for r in adj_rows:
            person_to_fgs[str(r.person_id)].append((str(r.family_group_id), r.role))
            fg_to_persons[str(r.family_group_id)].append(str(r.person_id))

        # 3. BFS from Niraj
        visited = {FOCUS_ID: None}
        queue = [FOCUS_ID]
        for _ in range(40):
            if not queue:
                break
            next_queue = []
            for pid in queue:
                for fg_id, _role in person_to_fgs.get(pid, []):
                    for neighbor in fg_to_persons.get(fg_id, []):
                        if neighbor not in visited:
                            visited[neighbor] = pid
                            next_queue.append(neighbor)
            queue = next_queue

        # 4. Compute labels
        results = []
        niraj_name = person_map.get(FOCUS_ID, "Niraj Byanjankar")

        for pid, name in sorted(person_map.items(), key=lambda x: x[1]):
            if pid == FOCUS_ID:
                continue

            if pid not in visited:
                results.append((niraj_name, name, "Not connected", translate("Not connected")))
                continue

            path_ids = []
            cur = pid
            while cur is not None:
                path_ids.append(cur)
                cur = visited.get(cur)
            path_ids.reverse()

            label = _infer_specific_label(path_ids, person_to_fgs, sex_map, birth_year_map)
            ne_label = translate(label)
            results.append((niraj_name, name, label, ne_label))

        # 5. Write CSV
        writer = csv.writer(sys.stdout)
        writer.writerow(["Person 1", "Person 2", "Relationship", "Nepali Relationship"])
        for r in results:
            writer.writerow(r)

    await engine.dispose()

asyncio.run(main())
