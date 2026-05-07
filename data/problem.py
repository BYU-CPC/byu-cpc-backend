from __future__ import annotations

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


def replace_problem_tags(cursor, problem_tags: list[tuple[str, str, list[str]]]):
    """Replaces all tags for each provided problem.

    Args:
        cursor: Database cursor
        problem_tags: List of tuples in format (external_id, platform_id, tags)
    """
    if not problem_tags:
        return

    cursor.executemany(
        """
            DELETE FROM problem_tag
            WHERE external_id = %s AND platform_id = %s
        """,
        [(external_id, platform_id) for external_id, platform_id, _ in problem_tags],
    )

    rows = [
        (external_id, platform_id, tag)
        for external_id, platform_id, tags in problem_tags
        for tag in tags
    ]
    if not rows:
        return

    cursor.executemany(
        """
            INSERT INTO problem_tag (external_id, platform_id, tag)
            VALUES (%s, %s, %s)
            ON CONFLICT (external_id, platform_id, tag) DO NOTHING
        """,
        rows,
    )


def get_problem_tags(cursor, external_id: str, platform_id: str) -> list[str]:
    cursor.execute(
        """
            SELECT tag
            FROM problem_tag
            WHERE external_id = %s AND platform_id = %s
            ORDER BY tag
        """,
        (external_id, platform_id),
    )
    return [row[0] for row in cursor.fetchall()]


# deprecated
def get_all_problems(cursor):
    cursor.execute("SELECT external_id, platform_id, rating, name FROM problem")
    return cursor.fetchall()
