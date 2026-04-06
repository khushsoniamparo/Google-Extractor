import psycopg2
try:
    conn = psycopg2.connect(dbname='postgres', user='postgres', password='22embit023', host='127.0.0.1')
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute('CREATE DATABASE scraper_db')
    cur.close()
    conn.close()
    print('SUCCESS')
except Exception as e:
    if 'already exists' in str(e):
        print('SUCCESS')
    else:
        print(f'ERROR: {e}')
