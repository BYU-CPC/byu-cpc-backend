from datetime import datetime
def add_person(cursor, id, display_name, last_checked = datetime.now() ):
    cursor.execute("""
        INSERT INTO person (id, display_name, last_checked)
        VALUES (%s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
    """, (id, display_name, last_checked))

