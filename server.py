import os
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import DictCursor
from flask import Flask, render_template, request, redirect, current_app, url_for, session
from contextlib import contextmanager
import json
from authlib.integrations.flask_client import OAuth
from urllib.parse import quote_plus, urlencode

app = Flask(__name__)

pool = None
oauth = None

# auth stuff

@app.route("/login")
def login():
    return oauth.auth0.authorize_redirect(
        redirect_uri=url_for("callback", _external=True)
    )

@app.route("/callback", methods=["GET", "POST"])
def callback():
    token = oauth.auth0.authorize_access_token()
    # Optionally fetch userinfo:
    try:
        userinfo = oauth.auth0.userinfo()
        session["userinfo"] = userinfo
    except Exception:
        pass
    session["user"] = token
    return redirect(url_for("hello"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(
        "https://" + os.environ.get("AUTH0_DOMAIN")
        + "/v2/logout?"
        + urlencode(
            {
                "returnTo": url_for("hello", _external=True),
                "client_id": os.environ.get("AUTH0_CLIENT_ID"),
            },
            quote_via=quote_plus,
        )
    )

def setup():
    global pool, oauth
    DATABASE_URL = os.environ.get('DATABASE_URL')
    app.secret_key = os.environ.get("FLASK_SECRET")
    current_app.logger.info("creating db connection pool")
    pool = ThreadedConnectionPool(1, 100, dsn=DATABASE_URL, sslmode='require')

    oauth = OAuth(app)
    oauth.register(
        "auth0",
        client_id=os.environ.get("AUTH0_CLIENT_ID"),
        client_secret=os.environ.get("AUTH0_CLIENT_SECRET"),
        server_metadata_url=f'https://{os.environ.get("AUTH0_DOMAIN")}/.well-known/openid-configuration'
    )

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

@app.route('/', methods=['GET', 'POST'])
def hello():
    print(session)
    guest = request.form.get('guest')
    if request.method == 'POST':
        if guest:
            with get_db_cursor(commit=True) as cur:
                cur.execute(
                    "INSERT INTO guests (guest) VALUES (%s)",
                    (guest,)
                )
        return redirect("/")
    with get_db_cursor() as cur:
        cur.execute("SELECT guest FROM guests")
        rows = cur.fetchall()
    pretty = None
    if "userinfo" in session:
        pretty = json.dumps(session["userinfo"], indent=2)
    return render_template('hello.html', rows=rows, pretty=pretty)

with app.app_context():
    setup()

if __name__ == '__main__':
    app.run()