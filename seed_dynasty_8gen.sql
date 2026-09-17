-- ============================================================
--  Seed: The Mitchell Dynasty — 8-generation ancestry fan chart
-- ============================================================
--  255 persons using Ahnentafel numbering (person i's parents
--  are persons 2i and 2i+1, family-group fg[i] records that pair).
--
--  Generation timeline:
--    Gen 1  William James Mitchell  b.1990  (focus / root)
--    Gen 2  Parents                 b.~1962
--    Gen 3  Grandparents            b.~1932
--    Gen 4  Great-grandparents      b.~1902
--    Gen 5  2× great-grandparents   b.~1873  (Victorian)
--    Gen 6  3× great-grandparents   b.~1843  (Early Victorian)
--    Gen 7  4× great-grandparents   b.~1813  (Regency)
--    Gen 8  5× great-grandparents   b.~1783  (Georgian / Colonial)
--
--  Run:
--    docker compose exec db psql -U postgres ourfamroots \
--      -f /seed_dynasty_8gen.sql
-- ============================================================

DO $$
DECLARE
    v_user_id   UUID;
    v_tenant_id UUID;
    v_tree_id   UUID := gen_random_uuid();

    -- Ahnentafel person UUIDs  p[1]..p[255]
    p           UUID[];
    -- Family-group UUIDs       fg[1]..fg[127]
    -- fg[i] = the couple whose child is person i
    fg          UUID[];

    i           INTEGER;
    v_pos       INTEGER;     -- 0-based position within generation
    v_sex       TEXT;
    v_given     TEXT;
    v_surname   TEXT;
    v_offset    INTEGER;     -- name-bank offset per generation (avoids repeats)

    -- ── Victorian / Georgian name banks (32 entries each) ─────────
    m_names   TEXT[] := ARRAY[
        'William','George','Thomas','Henry','Robert','Charles',
        'Edward','John','Arthur','Frederick','Albert','Walter',
        'Alfred','Harold','Samuel','Benjamin','Isaac','Edmund',
        'Reginald','Herbert','Percy','Leonard','Francis','Josiah',
        'Nathaniel','Amos','Elias','Silas','Cornelius','Archibald',
        'Ambrose','Barnabas'
    ];
    f_names   TEXT[] := ARRAY[
        'Mary','Elizabeth','Margaret','Anne','Sarah','Jane',
        'Frances','Eleanor','Agnes','Alice','Dorothy','Edith',
        'Florence','Grace','Hannah','Harriet','Lydia','Martha',
        'Ruth','Susanna','Abigail','Beatrice','Catherine','Clara',
        'Constance','Deborah','Esther','Hester','Prudence',
        'Patience','Temperance','Charity'
    ];
    -- 32 paternal-line surnames
    m_snames  TEXT[] := ARRAY[
        'Mitchell','Bradford','Lawson','Thornton',
        'Ward','Ashworth','Foster','Whitmore',
        'Collins','Sutherland','Beaumont','Cromwell',
        'Hartley','Pemberton','Fairfax','Wentworth',
        'Cavendish','Grenville','Montague','Hathaway',
        'Alderton','Worthington','Davenport','Kingsley',
        'Weatherby','Cholmondeley','Blackwood','Pearson',
        'Ashford','Whitfield','Pendleton','Kensington'
    ];
    -- 32 maternal-birth surnames
    f_snames  TEXT[] := ARRAY[
        'Harrison','Thompson','Clarke','Carter',
        'Hughes','Bennett','Morgan','Stone',
        'Holmes','Barker','Knight','Spencer',
        'Marsh','Webb','Douglas','Dixon',
        'Ford','Griffin','Fletcher','Shaw',
        'Booth','Jennings','Hayward','Clifton',
        'Selby','Leighton','Harrington','Dalton',
        'Seymour','Talbot','Carlisle','Brampton'
    ];

BEGIN
    -- ── 1. Locate any verified, active user ──────────────────────
    -- Picks whoever registered first — works with any account.
    SELECT id, tenant_id
    INTO   v_user_id, v_tenant_id
    FROM   users
    WHERE  is_active = true
    ORDER  BY created_at
    LIMIT  1;

    IF v_user_id IS NULL THEN
        RAISE EXCEPTION
            'No active user found. Register an account via the app first.';
    END IF;

    -- ── 2. Create the family tree ─────────────────────────────────
    INSERT INTO family_trees (id, tenant_id, name, description)
    VALUES (
        v_tree_id,
        v_tenant_id,
        'The Mitchell Dynasty',
        'Eight generations of the Mitchell family — from William James '
        'Mitchell (b.1990) through Victorian and Georgian ancestors born '
        'in the 1780s. Built to showcase the full 8-ring ancestry fan chart.'
    );

    INSERT INTO tree_members
        (id, tree_id, user_id, tenant_id, role, joined_at)
    VALUES
        (gen_random_uuid(), v_tree_id, v_user_id, v_tenant_id, 'OWNER', NOW());

    -- ── 3. Pre-allocate all UUIDs ─────────────────────────────────
    FOR i IN 1..255 LOOP p[i]  := gen_random_uuid(); END LOOP;
    FOR i IN 1..127 LOOP fg[i] := gen_random_uuid(); END LOOP;

    -- ══════════════════════════════════════════════════════════════
    --  PERSONS  (Generations 1–5 hand-crafted, 6–8 procedural)
    -- ══════════════════════════════════════════════════════════════

    -- ── Gen 1 — Focus person ─────────────────────────────────────
    INSERT INTO persons
        (id, tenant_id, tree_id, sex, display_given_name,
         display_surname, is_living, is_deceased)
    VALUES
        (p[1], v_tenant_id, v_tree_id,
         'MALE', 'William James', 'Mitchell', true, false);

    -- ── Gen 2 — Parents ──────────────────────────────────────────
    INSERT INTO persons
        (id, tenant_id, tree_id, sex, display_given_name,
         display_surname, is_living, is_deceased)
    VALUES
        (p[2], v_tenant_id, v_tree_id, 'MALE',   'Richard Edward',  'Mitchell', true, false),
        (p[3], v_tenant_id, v_tree_id, 'FEMALE', 'Catherine Anne',  'Ward',     true, false);

    -- ── Gen 3 — Grandparents ─────────────────────────────────────
    INSERT INTO persons
        (id, tenant_id, tree_id, sex, display_given_name,
         display_surname, is_living, is_deceased)
    VALUES
        (p[4], v_tenant_id, v_tree_id, 'MALE',   'George Thomas',   'Mitchell',  false, true),
        (p[5], v_tenant_id, v_tree_id, 'FEMALE', 'Margaret Rose',   'Lawson',    false, true),
        (p[6], v_tenant_id, v_tree_id, 'MALE',   'Henry James',     'Ward',      false, true),
        (p[7], v_tenant_id, v_tree_id, 'FEMALE', 'Elizabeth Anne',  'Foster',    false, true);

    -- ── Gen 4 — Great-grandparents ───────────────────────────────
    INSERT INTO persons
        (id, tenant_id, tree_id, sex, display_given_name,
         display_surname, is_living, is_deceased)
    VALUES
        (p[8],  v_tenant_id, v_tree_id, 'MALE',   'Edward Arthur',    'Mitchell',  false, true),
        (p[9],  v_tenant_id, v_tree_id, 'FEMALE', 'Alice Mary',       'Bradford',  false, true),
        (p[10], v_tenant_id, v_tree_id, 'MALE',   'Frederick William','Lawson',    false, true),
        (p[11], v_tenant_id, v_tree_id, 'FEMALE', 'Dorothy Rose',     'Thornton',  false, true),
        (p[12], v_tenant_id, v_tree_id, 'MALE',   'Herbert James',    'Ward',      false, true),
        (p[13], v_tenant_id, v_tree_id, 'FEMALE', 'Florence Grace',   'Ashworth',  false, true),
        (p[14], v_tenant_id, v_tree_id, 'MALE',   'Walter Thomas',    'Foster',    false, true),
        (p[15], v_tenant_id, v_tree_id, 'FEMALE', 'Edith Clara',      'Whitmore',  false, true);

    -- ── Gen 5 — 2× great-grandparents (Victorian, b.~1873) ───────
    INSERT INTO persons
        (id, tenant_id, tree_id, sex, display_given_name,
         display_surname, is_living, is_deceased)
    VALUES
        (p[16], v_tenant_id, v_tree_id, 'MALE',   'Thomas John',      'Mitchell',    false, true),
        (p[17], v_tenant_id, v_tree_id, 'FEMALE', 'Eleanor Frances',  'Collins',     false, true),
        (p[18], v_tenant_id, v_tree_id, 'MALE',   'Samuel Robert',    'Bradford',    false, true),
        (p[19], v_tenant_id, v_tree_id, 'FEMALE', 'Hannah Grace',     'Sutherland',  false, true),
        (p[20], v_tenant_id, v_tree_id, 'MALE',   'Charles Henry',    'Lawson',      false, true),
        (p[21], v_tenant_id, v_tree_id, 'FEMALE', 'Agnes Beatrice',   'Blackwood',   false, true),
        (p[22], v_tenant_id, v_tree_id, 'MALE',   'John William',     'Thornton',    false, true),
        (p[23], v_tenant_id, v_tree_id, 'FEMALE', 'Harriet Jane',     'Pearson',     false, true),
        (p[24], v_tenant_id, v_tree_id, 'MALE',   'Joseph Albert',    'Ward',        false, true),
        (p[25], v_tenant_id, v_tree_id, 'FEMALE', 'Martha Louise',    'Beaumont',    false, true),
        (p[26], v_tenant_id, v_tree_id, 'MALE',   'James Frederick',  'Ashworth',    false, true),
        (p[27], v_tenant_id, v_tree_id, 'FEMALE', 'Lydia Sarah',      'Whitfield',   false, true),
        (p[28], v_tenant_id, v_tree_id, 'MALE',   'Robert George',    'Foster',      false, true),
        (p[29], v_tenant_id, v_tree_id, 'FEMALE', 'Susanna Mary',     'Cromwell',    false, true),
        (p[30], v_tenant_id, v_tree_id, 'MALE',   'Alfred Edward',    'Whitmore',    false, true),
        (p[31], v_tenant_id, v_tree_id, 'FEMALE', 'Clara Victoria',   'Hartley',     false, true);

    -- ── Gens 6–8 — procedural (Early Victorian → Georgian) ───────
    --  Even index  → MALE   (father in their family)
    --  Odd  index  → FEMALE (mother in their family)
    --  v_pos  = 0-based position within generation
    --  v_offset offsets into name arrays so adjacent gens don't
    --  repeat the same first name in position 0.
    FOR i IN 32..255 LOOP

        v_pos := i - CASE
            WHEN i < 64  THEN 32    -- gen 6 starts at index 32
            WHEN i < 128 THEN 64    -- gen 7 starts at index 64
            ELSE              128   -- gen 8 starts at index 128
        END;

        v_offset := CASE
            WHEN i < 64  THEN 0
            WHEN i < 128 THEN 7
            ELSE              13
        END;

        IF i % 2 = 0 THEN
            v_sex     := 'MALE';
            v_given   := m_names[((i + v_offset) % 32) + 1];
            v_surname := m_snames[(v_pos          % 32) + 1];
        ELSE
            v_sex     := 'FEMALE';
            v_given   := f_names[((i / 2 + v_offset) % 32) + 1];
            v_surname := f_snames[(v_pos              % 32) + 1];
        END IF;

        INSERT INTO persons
            (id, tenant_id, tree_id, sex, display_given_name,
             display_surname, is_living, is_deceased)
        VALUES
            (p[i], v_tenant_id, v_tree_id,
             v_sex::person_sex, v_given, v_surname, false, true);

    END LOOP;

    -- ══════════════════════════════════════════════════════════════
    --  FAMILY GROUPS + MEMBERS
    --  fg[i]  →  father = p[2*i],  mother = p[2*i+1],  child = p[i]
    --  Only gens 1-7 need groups (gen-8 persons have no parents here).
    -- ══════════════════════════════════════════════════════════════
    FOR i IN 1..127 LOOP

        INSERT INTO family_groups
            (id, tenant_id, tree_id, union_type, parent1_id, parent2_id)
        VALUES
            (fg[i], v_tenant_id, v_tree_id,
             'MARRIAGE', p[2*i], p[2*i + 1]);

        INSERT INTO family_group_members
            (id, tenant_id, tree_id, family_group_id, person_id, role)
        VALUES
            (gen_random_uuid(), v_tenant_id, v_tree_id, fg[i], p[2*i],     'PARENT'),
            (gen_random_uuid(), v_tenant_id, v_tree_id, fg[i], p[2*i + 1], 'PARENT'),
            (gen_random_uuid(), v_tenant_id, v_tree_id, fg[i], p[i],       'CHILD');

    END LOOP;

    RAISE NOTICE '-----------------------------------------------';
    RAISE NOTICE 'Mitchell Dynasty seeded successfully.';
    RAISE NOTICE 'Tree ID   : %', v_tree_id;
    RAISE NOTICE 'User ID   : %', v_user_id;
    RAISE NOTICE 'Persons   : 255  (8 generations)';
    RAISE NOTICE 'Fam groups: 127';
    RAISE NOTICE '-----------------------------------------------';
    RAISE NOTICE 'Open the app, select this tree, click the fan';
    RAISE NOTICE 'chart icon, then set William James Mitchell as';
    RAISE NOTICE 'the focus to see all 8 rings.';

END $$;
