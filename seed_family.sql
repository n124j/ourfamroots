-- Seed: Smith family tree (4 generations, 12 persons) for test1@test.com
-- Run with: docker compose exec db psql -U postgres ourfamroots -f /seed_family.sql

DO $$
DECLARE
    v_user_id   UUID;
    v_tenant_id UUID;
    v_tree_id   UUID := gen_random_uuid();

    -- Gen 1 – great-grandparents
    v_james     UUID := gen_random_uuid();
    v_mary      UUID := gen_random_uuid();

    -- Gen 2 – grandparents
    v_robert    UUID := gen_random_uuid();
    v_patricia  UUID := gen_random_uuid();

    -- Gen 3 – parents + aunt/uncle
    v_david     UUID := gen_random_uuid();
    v_jennifer  UUID := gen_random_uuid();
    v_susan     UUID := gen_random_uuid();
    v_charles   UUID := gen_random_uuid();

    -- Gen 4 – children + cousin
    v_michael   UUID := gen_random_uuid();
    v_emily     UUID := gen_random_uuid();
    v_thomas    UUID := gen_random_uuid();
    v_olivia    UUID := gen_random_uuid();  -- Susan & Charles's daughter

    -- Family group IDs
    v_fg1 UUID := gen_random_uuid();   -- James + Mary
    v_fg2 UUID := gen_random_uuid();   -- Robert + Patricia
    v_fg3 UUID := gen_random_uuid();   -- David + Jennifer
    v_fg4 UUID := gen_random_uuid();   -- Susan + Charles

BEGIN
    -- 0. Verify email so the user can log in
    UPDATE users SET email_verified = true, email_verified_at = NOW()
    WHERE email = 'test1@test.com';

    -- 1. Look up user
    SELECT id, tenant_id INTO v_user_id, v_tenant_id
    FROM users WHERE email = 'test1@test.com';

    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'User test1@test.com not found';
    END IF;

    -- 2. Create tree
    INSERT INTO family_trees (id, tenant_id, name, description)
    VALUES (
        v_tree_id, v_tenant_id,
        'The Smith Family',
        'Four generations of the Smith family, starting with James & Mary Smith.'
    );

    -- 3. Add test1@test.com as OWNER
    INSERT INTO tree_members (id, tree_id, user_id, tenant_id, role, joined_at)
    VALUES (gen_random_uuid(), v_tree_id, v_user_id, v_tenant_id, 'OWNER', NOW());

    -- 4. Persons – Generation 1 (great-grandparents, deceased)
    INSERT INTO persons (id, tenant_id, tree_id, sex, display_given_name, display_surname, is_living, is_deceased)
    VALUES
        (v_james,    v_tenant_id, v_tree_id, 'MALE',   'James',    'Smith',   false, true),
        (v_mary,     v_tenant_id, v_tree_id, 'FEMALE', 'Mary',     'Smith',   false, true);

    -- 4. Persons – Generation 2 (grandparents)
    INSERT INTO persons (id, tenant_id, tree_id, sex, display_given_name, display_surname, is_living, is_deceased)
    VALUES
        (v_robert,   v_tenant_id, v_tree_id, 'MALE',   'Robert',   'Smith',   false, true),
        (v_patricia, v_tenant_id, v_tree_id, 'FEMALE', 'Patricia', 'Smith',   true,  false);

    -- 4. Persons – Generation 3
    INSERT INTO persons (id, tenant_id, tree_id, sex, display_given_name, display_surname, is_living, is_deceased)
    VALUES
        (v_david,    v_tenant_id, v_tree_id, 'MALE',   'David',    'Smith',   true,  false),
        (v_jennifer, v_tenant_id, v_tree_id, 'FEMALE', 'Jennifer', 'Smith',   true,  false),
        (v_susan,    v_tenant_id, v_tree_id, 'FEMALE', 'Susan',    'Wilson',  true,  false),
        (v_charles,  v_tenant_id, v_tree_id, 'MALE',   'Charles',  'Wilson',  true,  false);

    -- 4. Persons – Generation 4
    INSERT INTO persons (id, tenant_id, tree_id, sex, display_given_name, display_surname, is_living, is_deceased)
    VALUES
        (v_michael,  v_tenant_id, v_tree_id, 'MALE',   'Michael',  'Smith',   true,  false),
        (v_emily,    v_tenant_id, v_tree_id, 'FEMALE', 'Emily',    'Smith',   true,  false),
        (v_thomas,   v_tenant_id, v_tree_id, 'MALE',   'Thomas',   'Smith',   true,  false),
        (v_olivia,   v_tenant_id, v_tree_id, 'FEMALE', 'Olivia',   'Wilson',  true,  false);

    -- 5. Family group 1: James + Mary → Robert
    INSERT INTO family_groups (id, tenant_id, tree_id, union_type, parent1_id, parent2_id)
    VALUES (v_fg1, v_tenant_id, v_tree_id, 'MARRIAGE', v_james, v_mary);

    INSERT INTO family_group_members (id, tenant_id, tree_id, family_group_id, person_id, role)
    VALUES
        (gen_random_uuid(), v_tenant_id, v_tree_id, v_fg1, v_james,   'PARENT'),
        (gen_random_uuid(), v_tenant_id, v_tree_id, v_fg1, v_mary,    'PARENT'),
        (gen_random_uuid(), v_tenant_id, v_tree_id, v_fg1, v_robert,  'CHILD');

    -- 5. Family group 2: Robert + Patricia → David, Susan
    INSERT INTO family_groups (id, tenant_id, tree_id, union_type, parent1_id, parent2_id)
    VALUES (v_fg2, v_tenant_id, v_tree_id, 'MARRIAGE', v_robert, v_patricia);

    INSERT INTO family_group_members (id, tenant_id, tree_id, family_group_id, person_id, role)
    VALUES
        (gen_random_uuid(), v_tenant_id, v_tree_id, v_fg2, v_robert,   'PARENT'),
        (gen_random_uuid(), v_tenant_id, v_tree_id, v_fg2, v_patricia, 'PARENT'),
        (gen_random_uuid(), v_tenant_id, v_tree_id, v_fg2, v_david,    'CHILD'),
        (gen_random_uuid(), v_tenant_id, v_tree_id, v_fg2, v_susan,    'CHILD');

    -- 5. Family group 3: David + Jennifer → Michael, Emily, Thomas
    INSERT INTO family_groups (id, tenant_id, tree_id, union_type, parent1_id, parent2_id)
    VALUES (v_fg3, v_tenant_id, v_tree_id, 'MARRIAGE', v_david, v_jennifer);

    INSERT INTO family_group_members (id, tenant_id, tree_id, family_group_id, person_id, role)
    VALUES
        (gen_random_uuid(), v_tenant_id, v_tree_id, v_fg3, v_david,    'PARENT'),
        (gen_random_uuid(), v_tenant_id, v_tree_id, v_fg3, v_jennifer, 'PARENT'),
        (gen_random_uuid(), v_tenant_id, v_tree_id, v_fg3, v_michael,  'CHILD'),
        (gen_random_uuid(), v_tenant_id, v_tree_id, v_fg3, v_emily,    'CHILD'),
        (gen_random_uuid(), v_tenant_id, v_tree_id, v_fg3, v_thomas,   'CHILD');

    -- 5. Family group 4: Susan + Charles → Olivia
    INSERT INTO family_groups (id, tenant_id, tree_id, union_type, parent1_id, parent2_id)
    VALUES (v_fg4, v_tenant_id, v_tree_id, 'MARRIAGE', v_susan, v_charles);

    INSERT INTO family_group_members (id, tenant_id, tree_id, family_group_id, person_id, role)
    VALUES
        (gen_random_uuid(), v_tenant_id, v_tree_id, v_fg4, v_susan,   'PARENT'),
        (gen_random_uuid(), v_tenant_id, v_tree_id, v_fg4, v_charles, 'PARENT'),
        (gen_random_uuid(), v_tenant_id, v_tree_id, v_fg4, v_olivia,  'CHILD');

    RAISE NOTICE 'Done. Tree ID: %', v_tree_id;
    RAISE NOTICE '12 persons across 4 generations seeded for test1@test.com';
END $$;
