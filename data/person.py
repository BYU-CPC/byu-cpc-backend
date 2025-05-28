from datetime import datetime, timedelta
def add_person(cursor, id, display_name, last_checked = datetime.now() ):
    cursor.execute("""
        INSERT INTO person (id, display_name, last_checked)
        VALUES (%s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
    """, (id, display_name, last_checked))



def refresh_and_get_oldest_codeforces_users(cursor, limit: int = 5) -> list[tuple[str, datetime]]:
    """
    Atomically gets oldest codeforces users, updates their last_checked to NOW(),
    and returns (username, original_last_checked) tuples
    """
    query = """
        WITH get_users AS (
            SELECT ptp.username, p.id, p.last_checked AS original_last_checked
            FROM person_to_platform ptp
            INNER JOIN person p ON ptp.person_id = p.id
            WHERE ptp.platform_id = 'codeforces'
            ORDER BY p.last_checked ASC
            LIMIT %s
        ),
        update_times AS (
            UPDATE person p
            SET last_checked = NOW()
            FROM get_users gu
            WHERE p.id = gu.id
            RETURNING gu.username, gu.original_last_checked
        )
        SELECT username, original_last_checked FROM update_times;
    """
    
    cursor.execute(query, (limit,))
    results = []
    for username, last_checked in cursor.fetchall():
        results.append((username, last_checked - timedelta(minutes= 60)))
    return results

def upsert_platform_login(cursor, person_id, username, platform_id):
    cursor.execute("""
        INSERT INTO person_to_platform (person_id, username, platform_id)
        VALUES (%s, %s, %s)
        ON CONFLICT (person_id, platform_id) DO UPDATE SET
            username = EXCLUDED.username
    """, (person_id, username, platform_id))

def get_user_profile(cursor, person_id: str) -> dict | None:
    query = """
        SELECT 
            p.display_name,
            ptp.platform_id,
            ptp.username
        FROM person p
        LEFT JOIN person_to_platform ptp
            ON p.id = ptp.person_id
        WHERE p.id = %s;
    """
    
    cursor.execute(query, (person_id,))
    rows = cursor.fetchall()
    
    if not rows:
        return None
    
    result = {
        "display_name": rows[0][0],
        "usernames": {}
    }
    
    for row in rows:
        platform_id = row[1]
        username = row[2]
        if platform_id and username:  # Handle possible NULLs from LEFT JOIN
            result["usernames"][platform_id] = username
            
    return result

# deprecated
def get_all_users(cursor):
    query = """
    SELECT 
        p.id, 
        p.display_name, 
        COALESCE(kattis.username, '') AS kattis_username, 
        COALESCE(cf.username, '') AS codeforces_username,
        COALESCE(s.submissions, '{}'::jsonb) AS submissions  -- Handle NULL cases explicitly
    FROM person p 
    LEFT JOIN person_to_platform kattis 
        ON p.id = kattis.person_id 
        AND kattis.platform_id = 'kattis' 
    LEFT JOIN person_to_platform cf 
        ON p.id = cf.person_id 
        AND cf.platform_id = 'codeforces' 
    LEFT JOIN (
        SELECT 
            person_id,
            jsonb_object_agg(  -- No COALESCE needed here; handled in outer COALESCE
                external_id,
                jsonb_build_object('platform', platform_id, 'type', type, 'time', EXTRACT(EPOCH FROM time))
            ) AS submissions
        FROM submission 
        GROUP BY person_id
    ) s ON p.id = s.person_id;
    """
    cursor.execute(query)
    return cursor.fetchall()
