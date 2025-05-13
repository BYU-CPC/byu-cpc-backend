# problems: (external_id, platform_id, rating, name)[]
def upsert_problems(cursor, problems: list[tuple[str, str, float | None, str]]):
    query = """
        INSERT INTO problem (external_id, platform_id, rating, name)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (external_id, platform_id) DO UPDATE SET
            rating = EXCLUDED.rating,
            name = EXCLUDED.name
    """
    cursor.executemany(query, problems)
