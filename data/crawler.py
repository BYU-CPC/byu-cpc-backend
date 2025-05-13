def upsert_crawler(cursor, id, value):
    cursor.execute("""
        INSERT INTO crawler (id, value)
        VALUES (%s, %s)
        ON CONFLICT (id) DO UPDATE
        SET value = EXCLUDED.value;
    """, (id, value))
