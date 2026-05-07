from __future__ import annotations

from datetime import datetime


def upsert_submissions(cursor, submissions: list[tuple]):
    """
    Upserts submissions while maintaining the unique constraint and earliest time.

    Args:
        cursor: Database cursor
        submissions: List of tuples in either format:
            (external_id, platform_id, username, time, status, type)
            (external_id, platform_id, username, time, status, type, language, code)
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
                gen_random_uuid()::varchar
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
        RETURNING id
    """

    code_query = """
        INSERT INTO submission_code (submission_id, language, code)
        VALUES (%s, %s, %s)
        ON CONFLICT (submission_id) DO UPDATE SET
            language = COALESCE(EXCLUDED.language, submission_code.language),
            code = COALESCE(EXCLUDED.code, submission_code.code),
            updated_at = NOW()
    """

    for sub in submissions:
        if len(sub) == 6:
            external_id, platform_id, username, time, status, subtype = sub
            language = None
            code = None
        elif len(sub) == 8:
            external_id, platform_id, username, time, status, subtype, language, code = sub
        else:
            raise ValueError("Submissions must contain 6 or 8 values")

        cursor.execute(
            query,
            (
                # Problem upsert params
                external_id, platform_id, external_id,
                # Person lookup params
                username, platform_id,
                # Conflict check params
                status, external_id, platform_id,
                # Submission insert params
                external_id, platform_id,
                time, status, external_id, platform_id,
                status, subtype,
            ),
        )
        result = cursor.fetchone()
        if result and (language is not None or code is not None):
            cursor.execute(code_query, (result[0], language, code))
