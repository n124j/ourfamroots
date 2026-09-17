-- Seed: Smith Family – Generation 5 extension
-- Adds spouses + children for Michael, Emily, Thomas, and Olivia
-- Run with: docker compose exec db psql -U postgres ourfamroots -f /seed_smith_gen5.sql

DO $$
DECLARE
    v_tree_id   UUID := '26f9d85d-12d7-4eeb-8e24-5691f2c30e4d';
    v_tenant_id UUID := '6f4a16f3-935a-4331-9cb8-8c6b1c8a0f25';

    -- Gen 4 (existing) – looked up by ID
    v_michael UUID := '8bf5f859-35ad-4188-9db2-d704cd093563';
    v_emily   UUID := '5bfcb718-0175-4ed5-baa4-ac7d2850264e';
    v_thomas  UUID := '684cc147-9da6-4110-9cd4-63770fe7e34f';
    v_olivia  UUID := '0b25179f-a4e8-4ab3-8bdf-470d5ad09506';

    -- Gen 4 spouses (new)
    v_sarah   UUID := gen_random_uuid();   -- Michael's wife
    v_daniel  UUID := gen_random_uuid();   -- Emily's husband
    v_laura   UUID := gen_random_uuid();   -- Thomas's wife
    v_ryan    UUID := gen_random_uuid();   -- Olivia's husband

    -- Gen 5 – Michael & Sarah's children
    v_noah    UUID := gen_random_uuid();
    v_sophie  UUID := gen_random_uuid();
    v_jack    UUID := gen_random_uuid();

    -- Gen 5 – Emily & Daniel's children
    v_alice   UUID := gen_random_uuid();
    v_ben     UUID := gen_random_uuid();

    -- Gen 5 – Thomas & Laura's children
    v_grace   UUID := gen_random_uuid();

    -- Gen 5 – Olivia & Ryan's children
    v_ethan   UUID := gen_random_uuid();
    v_chloe   UUID := gen_random_uuid();

    -- Family group IDs
    v_fg5 UUID := gen_random_uuid();   -- Michael + Sarah
    v_fg6 UUID := gen_random_uuid();   -- Emily + Daniel
    v_fg7 UUID := gen_random_uuid();   -- Thomas + Laura
    v_fg8 UUID := gen_random_uuid();   -- Olivia + Ryan

BEGIN
    -- Gen 4 spouses
    INSERT INTO persons (id, tenant_id, tree_id, sex, display_given_name, display_surname, is_living, is_deceased)
    VALUES
        (v_sarah,  v_tenant_id, v_tree_id, 'FEMALE', 'Sarah',  'Smith',   true, false),
        (v_daniel, v_tenant_id, v_tree_id, 'MALE',   'Daniel', 'Smith',   true, false),
        (v_laura,  v_tenant_id, v_tree_id, 'FEMALE', 'Laura',  'Smith',   true, false),
        (v_ryan,   v_tenant_id, v_tree_id, 'MALE',   'Ryan',   'Davis',   true, false);

    -- Gen 5 children
    INSERT INTO persons (id, tenant_id, tree_id, sex, display_given_name, display_surname, is_living, is_deceased)
    VALUES
        -- Michael & Sarah's
        (v_noah,   v_tenant_id, v_tree_id, 'MALE',   'Noah',   'Smith',   true, false),
        (v_sophie, v_tenant_id, v_tree_id, 'FEMALE', 'Sophie', 'Smith',   true, false),
        (v_jack,   v_tenant_id, v_tree_id, 'MALE',   'Jack',   'Smith',   true, false),
        -- Emily & Daniel's
        (v_alice,  v_tenant_id, v_tree_id, 'FEMALE', 'Alice',  'Smith',   true, false),
        (v_ben,    v_tenant_id, v_tree_id, 'MALE',   'Ben',    'Smith',   true, false),
        -- Thomas & Laura's
        (v_grace,  v_tenant_id, v_tree_id, 'FEMALE', 'Grace',  'Smith',   true, false),
        -- Olivia & Ryan's
        (v_ethan,  v_tenant_id, v_tree_id, 'MALE',   'Ethan',  'Davis',   true, false),
        (v_chloe,  v_tenant_id, v_tree_id, 'FEMALE', 'Chloe',  'Davis',   true, false);

    -- FG5: Michael + Sarah → Noah, Sophie, Jack
    INSERT INTO family_groups (id, tenant_id, tree_id, union_type, parent1_id, parent2_id)
    VALUES (v_fg5, v_tenant_id, v_tree_id, 'MARRIAGE', v_michael, v_sarah);

    INSERT INTO family_group_members (id, tenant_id, tree_id, family_group_id, person_id, role)
    VALUES
        (gen_random_uuid(), v_tenant_id, v_tree_id, v_fg5, v_michael, 'PARENT'),
        (gen_random_uuid(), v_tenant_id, v_tree_id, v_fg5, v_sarah,   'PARENT'),
        (gen_random_uuid(), v_tenant_id, v_tree_id, v_fg5, v_noah,    'CHILD'),
        (gen_random_uuid(), v_tenant_id, v_tree_id, v_fg5, v_sophie,  'CHILD'),
        (gen_random_uuid(), v_tenant_id, v_tree_id, v_fg5, v_jack,    'CHILD');

    -- FG6: Emily + Daniel → Alice, Ben
    INSERT INTO family_groups (id, tenant_id, tree_id, union_type, parent1_id, parent2_id)
    VALUES (v_fg6, v_tenant_id, v_tree_id, 'MARRIAGE', v_emily, v_daniel);

    INSERT INTO family_group_members (id, tenant_id, tree_id, family_group_id, person_id, role)
    VALUES
        (gen_random_uuid(), v_tenant_id, v_tree_id, v_fg6, v_emily,  'PARENT'),
        (gen_random_uuid(), v_tenant_id, v_tree_id, v_fg6, v_daniel, 'PARENT'),
        (gen_random_uuid(), v_tenant_id, v_tree_id, v_fg6, v_alice,  'CHILD'),
        (gen_random_uuid(), v_tenant_id, v_tree_id, v_fg6, v_ben,    'CHILD');

    -- FG7: Thomas + Laura → Grace
    INSERT INTO family_groups (id, tenant_id, tree_id, union_type, parent1_id, parent2_id)
    VALUES (v_fg7, v_tenant_id, v_tree_id, 'MARRIAGE', v_thomas, v_laura);

    INSERT INTO family_group_members (id, tenant_id, tree_id, family_group_id, person_id, role)
    VALUES
        (gen_random_uuid(), v_tenant_id, v_tree_id, v_fg7, v_thomas, 'PARENT'),
        (gen_random_uuid(), v_tenant_id, v_tree_id, v_fg7, v_laura,  'PARENT'),
        (gen_random_uuid(), v_tenant_id, v_tree_id, v_fg7, v_grace,  'CHILD');

    -- FG8: Olivia + Ryan → Ethan, Chloe
    INSERT INTO family_groups (id, tenant_id, tree_id, union_type, parent1_id, parent2_id)
    VALUES (v_fg8, v_tenant_id, v_tree_id, 'MARRIAGE', v_olivia, v_ryan);

    INSERT INTO family_group_members (id, tenant_id, tree_id, family_group_id, person_id, role)
    VALUES
        (gen_random_uuid(), v_tenant_id, v_tree_id, v_fg8, v_olivia, 'PARENT'),
        (gen_random_uuid(), v_tenant_id, v_tree_id, v_fg8, v_ryan,   'PARENT'),
        (gen_random_uuid(), v_tenant_id, v_tree_id, v_fg8, v_ethan,  'CHILD'),
        (gen_random_uuid(), v_tenant_id, v_tree_id, v_fg8, v_chloe,  'CHILD');

    RAISE NOTICE 'Done. Added 12 persons (4 spouses + 8 Gen-5 children) and 4 new family groups.';
END $$;
