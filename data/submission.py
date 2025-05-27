from datetime import datetime
def upsert_submissions(cursor, submissions: list[tuple[str, str, str, datetime, str, str | None]]):
    """
    Upserts submissions while maintaining the unique constraint and earliest time
    Args:
        cursor: Database cursor
        submissions: List of tuples in format (external_id, platform_id, username, time, status, type)
    """
    query = """
        WITH problem_upsert AS (
            INSERT INTO problem (external_id, platform_id, name)
            VALUES (%s, %s, %s)  -- Default name for new problems
            ON CONFLICT (external_id, platform_id) DO NOTHING
        ),
        person_lookup AS (
            SELECT ptp.person_id, ptp.platform_id, ptp.username
            FROM person_to_platform ptp
            WHERE ptp.username = %s AND ptp.platform_id = %s
        )
        INSERT INTO submission (
            id, 
            external_id, 
            platform_id, 
            person_id, 
            time, 
            status, 
            type
        )
        SELECT 
            COALESCE(
                (SELECT s.id FROM submission s 
                 WHERE s.status = %s 
                   AND s.external_id = %s 
                   AND s.platform_id = %s 
                   AND s.person_id = pl.person_id),
                gen_random_uuid()
            ),
            %s,  -- external_id
            %s,  -- platform_id
            pl.person_id,
            LEAST(%s, (SELECT s.time FROM submission s 
                       WHERE s.status = %s 
                         AND s.external_id = %s 
                         AND s.platform_id = %s 
                         AND s.person_id = pl.person_id)),
            %s,  -- status
            %s   -- type
        FROM person_lookup pl
        ON CONFLICT (status, external_id, platform_id, person_id) DO UPDATE SET
            time = LEAST(submission.time, EXCLUDED.time),
            type = COALESCE(EXCLUDED.type, submission.type)
    """
    
    params = []
    for sub in submissions:
        (external_id, platform_id, username, time, status, subtype) = sub
        params.append((
            # Problem upsert params
            external_id, platform_id, external_id,
            # Person lookup params
            username, platform_id,
            # Conflict check params
            status, external_id, platform_id,
            # Submission insert params
            external_id, platform_id,
            time, status, external_id, platform_id,
            status, subtype
        ))
    
    cursor.executemany(query, params)
