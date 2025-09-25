import os
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import DictCursor
from flask import Flask, render_template, request, redirect, current_app
from contextlib import contextmanager

pool = None

def setup():
    global pool
    DATABASE_URL = os.environ['DATABASE_URL']
    current_app.logger.info(f"creating db connection pool")
    pool = ThreadedConnectionPool(1, 100, dsn=DATABASE_URL, sslmode='require')

@contextmanager
def get_db_connection():
    connection = None
    try:
        connection = pool.getconn()
        yield connection
    finally:
        if connection:
            pool.putconn(connection)


@contextmanager
def get_db_cursor(commit=False):
    with get_db_connection() as connection:
      cursor = connection.cursor(cursor_factory=DictCursor)
      try:
          yield cursor
          if commit:
              connection.commit()
      finally:
          cursor.close()

def create_app():
    app = Flask(__name__)
    with app.app_context():
        setup()

    @app.route('/', methods=['GET', 'POST'])
    def hello():
        guest = request.form.get('guest')
        if request.method == 'POST':
            with get_db_cursor(commit=True) as cur:
                cur.execute(
                    """INSERT INTO guests (guest) 
                        VALUES (%s)""",
                    (guest,)
                )
            return redirect("/")
        if request.method == 'GET':
            with get_db_cursor() as cur:
                cur.execute("""
                        SELECT guest
                        FROM guests
                    """)
                rows = cur.fetchall()
            return render_template('hello.html', rows=rows)
    return app

if __name__ == '__main__':
    app = create_app()
    app.run()