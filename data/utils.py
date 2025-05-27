from environment import DATABASE_URL
import psycopg2

con = psycopg2.connect(DATABASE_URL)
def get_db():
    global con
    if con.closed: con = psycopg2.connect(DATABASE_URL)
    cur = con.cursor()
    def close():
        con.commit()
        cur.close()
    return con.cursor(),close

