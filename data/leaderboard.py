def upsert_leaderboard(cursor, name, start, finish, period, public_view, public_join, 
                      scoring, rules, created_by_id, leaderboard_id=None):
    cursor.execute("""
        INSERT INTO leaderboard (
            id, name, start, finish, period, 
            public_view, public_join, scoring, rules, created_by_id
        )
        VALUES (
            COALESCE(%s, gen_random_uuid()::varchar),  -- Use provided ID or generate new
            %s, %s, %s, %s, 
            %s, %s, %s, %s, %s
        )
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            start = EXCLUDED.start,
            finish = EXCLUDED.finish,
            period = EXCLUDED.period,
            public_view = EXCLUDED.public_view,
            public_join = EXCLUDED.public_join,
            scoring = EXCLUDED.scoring,
            rules = EXCLUDED.rules
        RETURNING id;
    """, (leaderboard_id, name, start, finish, period, 
          public_view, public_join, scoring, rules, created_by_id))
    
    new_leaderboard_id = cursor.fetchone()[0]
    if new_leaderboard_id == leaderboard_id:
        return leaderboard_id

    leaderboard_id = new_leaderboard_id
    cursor.execute("""
        INSERT INTO invitation (id, leaderboard_id)
        VALUES (gen_random_uuid(), %s)
    """, (leaderboard_id,))
    
    cursor.execute("""
        INSERT INTO person_to_leaderboard (person_id, leaderboard_id)
        VALUES (%s, %s)
        ON CONFLICT (person_id, leaderboard_id) DO NOTHING;
    """, (created_by_id, leaderboard_id))
    
    return leaderboard_id

def leaderboard_auth(where = ""):
    return f"""
        SELECT
            l.id, l.name, l.start, l.finish, l.period, l.rules, l.scoring, l.created_by_id, l.public_view, l.public_join,
            (l.finish IS NULL OR l.finish > NOW()) AND (l.public_join OR (i.id IS NOT NULL AND (i.expires_at IS NULL OR i.expires_at > NOW()))) AND p.person_id IS NULL AS can_join,
            (%s IS NOT NULL AND l.created_by_id = %s) OR l.public_view OR p.person_id IS NOT NULL OR (i.id IS NOT NULL AND (i.expires_at IS NULL OR i.expires_at > NOW())) AS can_view,  --  person_id, person_id
            p.person_id IS NOT NULL AS has_joined
        FROM leaderboard l
        LEFT JOIN invitation i 
            ON i.id = %s   --   invitation_id
            AND i.leaderboard_id = l.id
        LEFT JOIN person_to_leaderboard p
            ON p.person_id = %s   --   person_id
            AND p.leaderboard_id = l.id
        {where}
    """

def add_person_to_leaderboard(cursor, person_id, invitation_id, leaderboard_id):
    cursor.execute(f"""
        WITH leaderboard_auth AS ({leaderboard_auth("WHERE l.id = %s")})
        INSERT INTO person_to_leaderboard (person_id, leaderboard_id)
        SELECT %s, %s
        FROM leaderboard_auth
        WHERE can_join
    """, ( person_id, person_id, invitation_id, person_id, leaderboard_id, person_id, leaderboard_id ))
    return cursor.rowcount > 0

def get_leaderboard_details(cursor, person_id, leaderboard_id, invitation_id):
    cursor.execute(f"""
        WITH leaderboard_auth AS({leaderboard_auth("WHERE l.id = %s")}),
        participants AS (
            SELECT array_agg(person_id) AS members
            FROM person_to_leaderboard
            WHERE leaderboard_id = %s
        )
        SELECT name, start, finish, rules, scoring, created_by_id, members, can_join, has_joined
        FROM leaderboard_auth, participants
        WHERE can_view
    """, (person_id, person_id, invitation_id, person_id, leaderboard_id, leaderboard_id))
    
    result = cursor.fetchone()
    if not result:
        return None
        
    columns = [desc[0] for desc in cursor.description]
    data = dict(zip(columns, result))
    data["start"] = data["start"].timestamp() if data["start"] else None
    data["finish"] = data["finish"].timestamp() if data["finish"] else None
    return data

def get_accessible_leaderboards(cursor, person_id):
    cursor.execute(f"""
        WITH leaderboard_auth AS ({leaderboard_auth()})
        SELECT
            l.id,
            l.name,
            l.start,
            l.finish,
            l.period,
            l.public_view,
            l.public_join,
            l.scoring,
            l.rules,
            l.created_by_id
        FROM leaderboard_auth l
        WHERE l.can_view
    """, (person_id, person_id, None, person_id))
    
    leaderboards = []
    columns = [desc[0] for desc in cursor.description]
    for row in cursor.fetchall():
        data = dict(zip(columns, row))
        data["finish"] = data["finish"].timestamp() if data["finish"] else None
        data["start"] = data["start"].timestamp() if data["start"] else None
        leaderboards.append(data)
    return leaderboards

def get_created_leaderboards(cursor, person_id):
    cursor.execute("""
        SELECT DISTINCT ON (l.id)
            l.id,
            l.name,
            l.start,
            l.finish,
            l.public_view,
            l.public_join,
            i.id AS invitation_id
        FROM leaderboard l
        LEFT JOIN invitation i  -- Corrected table name (matches your schema)
            ON i.leaderboard_id = l.id
            AND (i.expires_at > NOW() OR i.expires_at IS NULL)
        WHERE l.created_by_id = %s
        ORDER BY l.id, i.expires_at DESC NULLS LAST;
    """, (person_id,))
    leaderboards = []
    columns = [desc[0] for desc in cursor.description]
    for row in cursor.fetchall():
        data = dict(zip(columns, row))
        data["finish"] = data["finish"].timestamp() if data["finish"] else None
        data["start"] = data["start"].timestamp() if data["start"] else None
        leaderboards.append(data)
    return leaderboards

def get_joined_leaderboards(cursor, person_id):
    cursor.execute("""
        SELECT id
        FROM leaderboard l
        JOIN person_to_leaderboard p
        ON l.id = p.leaderboard_id
        WHERE p.person_id = %s;
    """, (person_id,))
    return [row[0] for row in cursor.fetchall()]
