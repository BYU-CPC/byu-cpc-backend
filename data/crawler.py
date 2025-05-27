def upsert_crawler(cursor, id, value):
    cursor.execute("""
        INSERT INTO crawler (id, value)
        VALUES (%s, %s)
        ON CONFLICT (id) DO UPDATE
        SET value = EXCLUDED.value;
    """, (id, value))

def get_crawler(cursor, id):
    cursor.execute("SELECT value FROM crawler where id = %s;", (id,))
    return cursor.fetchall()[0][0]
