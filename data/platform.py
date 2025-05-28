def add_platform(cursor, platform_id, display_name):
    cursor.execute("""
        INSERT INTO platform (id, display_name)
        VALUES (%s, %s)
        ON CONFLICT (id) DO NOTHING;
    """, (platform_id, display_name))

def add_platform_account(cursor, person_id, platform, username):
    cursor.execute("""
        INSERT INTO person_to_platform (person_id, platform_id, username)
        VALUES (%s, %s, %s)
        ON CONFLICT (person_id, platform_id) DO UPDATE
        SET username = EXCLUDED.username;
    """, (person_id, platform, username))

