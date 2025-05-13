from environment import DATABASE_URL
import psycopg2

con = psycopg2.connect(DATABASE_URL)
cur = con.cursor()

# Drop all tables in correct order with CASCADE
cur.execute("""
    DROP TABLE IF EXISTS
        invitations,
        submission,
        problem_to_practice_set,
        link_to_practice_set,
        practice_set,
        person_to_platform,
        problem,
        crawler,
        leaderboard,
        person,
        platform
    CASCADE;
""")
con.commit()

# Create necessary extensions
cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

# Create tables
cur.execute("""
    CREATE TABLE platform (
        id VARCHAR PRIMARY KEY,
        display_name VARCHAR NOT NULL
    );
""")

cur.execute("""
    CREATE TABLE person (
        id VARCHAR PRIMARY KEY,
        display_name VARCHAR NOT NULL,
        last_checked TIMESTAMP NOT NULL
    );
""")

cur.execute("""
    CREATE TABLE leaderboard (
        id UUID PRIMARY KEY,
        name VARCHAR NOT NULL,
        start TIMESTAMP,
        finish TIMESTAMP,
        public_view BOOLEAN NOT NULL,
        public_join BOOLEAN NOT NULL,
        scoring JSONB,
        rules TEXT
    );
""")

cur.execute("""
    CREATE TABLE crawler (
        id VARCHAR PRIMARY KEY,
        value INTEGER NOT NULL
    );
""")

cur.execute("""
    CREATE TABLE problem (
        external_id VARCHAR NOT NULL,
        platform_id VARCHAR NOT NULL REFERENCES platform(id),
        rating FLOAT,
        name VARCHAR,
        PRIMARY KEY (external_id, platform_id)
    );
""")

cur.execute("""
    CREATE TABLE person_to_platform (
        person_id VARCHAR NOT NULL REFERENCES person(id),
        platform_id VARCHAR NOT NULL REFERENCES platform(id),
        username VARCHAR NOT NULL,
        PRIMARY KEY (person_id, platform_id)
    );
""")

cur.execute("""
    CREATE TABLE practice_set (
        id UUID PRIMARY KEY,
        leaderboard_id UUID NOT NULL REFERENCES leaderboard(id),
        description VARCHAR,
        start TIMESTAMP,
        finish TIMESTAMP
    );
""")

cur.execute("""
    CREATE TABLE problem_to_practice_set (
        external_id VARCHAR NOT NULL,
        platform_id VARCHAR NOT NULL,
        practice_set_id UUID NOT NULL REFERENCES practice_set(id),
        FOREIGN KEY (external_id, platform_id) REFERENCES problem (external_id, platform_id),
        PRIMARY KEY (external_id, platform_id, practice_set_id)
    );
""")

cur.execute("""
    CREATE TABLE link_to_practice_set (
        id UUID PRIMARY KEY,
        practice_set_id UUID NOT NULL REFERENCES practice_set(id),
        url VARCHAR NOT NULL,
        display_text VARCHAR NOT NULL,
        UNIQUE (id, practice_set_id)
    );
""")

cur.execute("""
    CREATE TABLE submission (
        id UUID PRIMARY KEY,
        time TIMESTAMP NOT NULL,
        status VARCHAR NOT NULL,
        external_id VARCHAR NOT NULL,
        platform_id VARCHAR NOT NULL,
        person_id VARCHAR NOT NULL REFERENCES person (id),
        type VARCHAR,
        FOREIGN KEY (external_id, platform_id) REFERENCES problem (external_id, platform_id),
        UNIQUE (status, external_id, platform_id, person_id)
    );
""")

cur.execute("""
    CREATE TABLE invitations (
        id UUID PRIMARY KEY,
        expires_at TIMESTAMP,
        leaderboard_id UUID NOT NULL REFERENCES leaderboard(id)
    );
""")

# Create indices
cur.execute("CREATE INDEX submission_person_id_idx ON submission (person_id);")
cur.execute("CREATE INDEX submission_platform_id_idx ON submission (platform_id);")
cur.execute("CREATE INDEX practice_set_leaderboard_id_idx ON practice_set (leaderboard_id);")
cur.execute("CREATE INDEX invitations_leaderboard_id_idx ON invitations (leaderboard_id);")

con.commit()
cur.close()
con.close()
