from pprint import pprint

from flask import Flask, request, render_template, redirect
from requests.exceptions import RequestException
from bs4 import BeautifulSoup
import requests
import sqlite3
from datetime import datetime
import re
from markupsafe import Markup
from modules.language import Language

language = Language()

app = Flask(__name__)

# Inject language and translations into all templates
@app.context_processor
def inject_language():
    return {
        'language': language,           # the Language instance
        't': language.language_data,    # the raw translations dict for simple access like {{ t.title }}
        'translate': language.get_translation  # helper function: {{ translate('key') }}
    }

DB_NAME = "data.db"


def highlight(text, word):
    if not word:
        return text
    pattern = re.compile(re.escape(word), re.IGNORECASE)

    return_value = Markup(pattern.sub(lambda m: f'<mark>{m.group(0)}</mark>', text))
    print(f"Highlighting '{word}' in text: {return_value}")
    return return_value


# Init db
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS webpages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                content TEXT,
                created_at TEXT
            )
        ''')
        conn.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS webpages_fts USING fts5(
                url, content,
                content='webpages',
                content_rowid='id',
                prefix='2 3 4 5 6 7 8 9 10'
            )
        ''')


@app.route("/delete/<int:entry_id>", methods=["POST"])
def delete_entry(entry_id):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("DELETE FROM webpages WHERE id = ?", (entry_id,))
        conn.execute("DELETE FROM webpages_fts WHERE rowid = ?", (entry_id,))
    return redirect(request.referrer or "/")

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        url = request.form.get("url") or request.args.get("url") or ""

        with sqlite3.connect(DB_NAME) as conn:
            existing = conn.execute("SELECT id FROM webpages WHERE url = ?", (url,)).fetchone()
            if existing and request.form.get("confirm_update") != "1":
                return redirect("/?exists=1&url=" + url)

        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            html = response.text
        except RequestException as e:
            print(f"{language.get_translation('network_error')} {e}")
            return redirect("/?error=1&url=" + url)

        try:
            soup = BeautifulSoup(html, "html.parser")
            elements = soup.find_all(
                ['p', 'h1', 'h2', 'h3', 'li', 'input', 'textarea',
                 'select',
                 'option',
                 'a',
                 'div',
                 'span',
                 'button',
                 "script",])
            structured = []

            for elem in elements:
                key = (
                        elem.get('aria-label') or
                        elem.get('label') or
                        elem.get('name') or
                        elem.get('id') or
                        (elem.get('class') and ' '.join(elem.get('class'))) or
                        elem.name
                )

                if elem.name == 'input':
                    value = elem.get('value', '')
                elif elem.name == 'textarea':
                    value = elem.text.strip()
                elif elem.name == 'select':
                    selected = elem.find('option', selected=True)
                    value = selected.text.strip() if selected else ''
                elif elem.name == 'option':
                    value = elem.text.strip()
                else:
                    value = elem.get_text(strip=True)

                if value:
                    structured.append(f"{key}: {value}")

            text = '\n'.join(structured)

            with sqlite3.connect(DB_NAME) as conn:
                if existing:
                    conn.execute("UPDATE webpages SET content = ?, created_at = ? WHERE url = ?",
                                 (text, datetime.now().isoformat(), url))
                    entry_id = existing[0]
                    conn.execute("DELETE FROM webpages_fts WHERE rowid = ?", (entry_id,))
                    conn.execute("INSERT INTO webpages_fts(rowid, url, content) VALUES (?, ?, ?)",
                                 (entry_id, url, text))
                else:
                    conn.execute("INSERT INTO webpages (url, content, created_at) VALUES (?, ?, ?)",
                                 (url, text, datetime.now().isoformat()))
                    entry_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                    conn.execute("INSERT INTO webpages_fts(rowid, url, content) VALUES (?, ?, ?)",
                                 (entry_id, url, text))

            return redirect("/")
        except Exception as e:
            print(f"{language.get_translation('data_parsing_error')} {e}")
            return redirect("/?error=1&url=" + url)

    query = request.args.get("q", "").strip()

    with sqlite3.connect(DB_NAME) as conn:
        if query:
            fts_query = f'"{query}*"'
            rows = conn.execute("""
                SELECT id, url, content, created_at
                FROM webpages
                WHERE id IN (
                    SELECT rowid FROM webpages_fts WHERE webpages_fts MATCH ?
                )
                OR url LIKE ?
            """, (fts_query, f"%{query}%")).fetchall()
        else:
            rows = conn.execute("SELECT id, url, content, created_at FROM webpages ORDER BY id DESC").fetchall()

    def shorten(message, length=200):
        return message[:length].rstrip() + ("..." if len(message) > length else "")

    entries = []
    for row in rows:
        short = shorten(row[2])
        is_truncated = len(row[2]) > 200
        entries.append((
            row[0],
            highlight(row[1], query),  # URL highlight
            highlight(short, query),  # text highlight
            row[3],
            is_truncated
        ))

    return render_template("index.html", entries=entries, query=query)



@app.route("/list")
def list_entries():
    with sqlite3.connect(DB_NAME) as conn:
        debug = conn.execute("SELECT rowid, url FROM webpages_fts").fetchall()
        print(language.get_translation("fts_content"))
        for row in debug:
            print(row)
        print("FTS5 status:")
        debug_rows = conn.execute("SELECT rowid, url FROM webpages_fts").fetchall()
        for row in debug_rows:
            print(row)
    query = request.args.get("q", "").strip()
    print(f"{language.get_translation('query_keyword')} '{query}'")

    with sqlite3.connect(DB_NAME) as conn:
        if query:
            fts_query = f'"{query}*"'
            rows = conn.execute("""
                                SELECT id, url, content, created_at
                                FROM webpages
                                WHERE id IN (SELECT rowid
                                             FROM webpages_fts
                                             WHERE webpages_fts MATCH ?)
                                   OR url LIKE ?
                                """, (fts_query, f"%{query}%")).fetchall()
            print(f"{language.get_translation('found_entry_length')} {len(rows)}")
        else:
            rows = conn.execute("SELECT id, url, content, created_at FROM webpages").fetchall()

    def shorten(text, length=200):
        return text[:length].rstrip() + ("..." if len(text) > length else "")


    entries = []
    for row in rows:
        short = shorten(row[2])
        is_truncated = len(row[2]) > 200
        entries.append((
            row[0],
            highlight(row[1], query),  # URL highlight
            highlight(short, query),  # text shortened, highlighted
            row[3],
            is_truncated
        ))

    return render_template("list.html", entries=entries, query=query)


@app.route("/entry/<int:entry_id>")
def show_entry(entry_id):
    with sqlite3.connect(DB_NAME) as conn:
        row = conn.execute("SELECT * FROM webpages WHERE id = ?", (entry_id,)).fetchone()
        if not row:
            return f"{language.get_translation('no_such_entry')}: {entry_id}"
        # SQLite row: (id, url, content, created_at)
        keys = ["ID", "URL", "CONTENT", "CREATED AT"]
        entry = dict(zip(keys, row))
        pprint(entry)
        print(f"{language.get_translation('data_of_entry')} {entry.get('ID')}")
    return render_template("entry.html", entry=entry)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
