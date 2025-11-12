from __future__ import annotations

from pathlib import Path
import argparse
import html as html_lib

from spacy import displacy

from split_text import split_sumario_and_body

from relation_extractor import RelationExtractor, RelationExtractorSerieIII, export_relations_items_minimal_json, export_serieIII_items_minimal_json

from pdf_markup import extract_pdf_to_markdown

from spacy_modulo import get_nlp, setup_entities, OPTIONS

from body_extraction import divide_body_by_org_and_docs, divide_body_by_org_and_docs_serieIII

from testing_results import summarize_results

from collections import defaultdict

import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path("pdf_ingest.db")

# -----------------------
# Config knobs
# -----------------------
DEFAULT_INPUT_DIR = Path("input_pdfs")
CROP_TOP_RATIO = 0.10
SKIP_LAST_PAGE = True


def is_serie_iii(filename: str) -> bool:
    """Decide if this is Serie III by filename heuristic."""
    return "iiiserie" in filename.lower()


def load_text_from_pdf(pdf_path: Path) -> str:
    return extract_pdf_to_markdown(
        pdf_path
    )


def build_docs(nlp, full_text: str):
    """
    Returns (doc, doc_sumario, doc_body, sumario_text, body_text, meta)
    """
    doc = nlp(full_text)
    sumario_text, body_text, meta = split_sumario_and_body(doc, None)
    doc_sumario = nlp(sumario_text)
    doc_body = nlp(body_text)
    return doc, doc_sumario, doc_body, sumario_text, body_text, meta


def extract_relations_and_payload(doc_sumario, serie_iii: bool):
    if serie_iii:
        rex = RelationExtractorSerieIII(debug=True)
        rels = rex.extract(doc_sumario)
        payload = export_serieIII_items_minimal_json(rels)
    else:
        rex = RelationExtractor(debug=True)
        rels = rex.extract(doc_sumario)
        payload = export_relations_items_minimal_json(rels, path=None)
    return rels, payload


def split_body(doc_body, payload, serie_iii: bool):
    if serie_iii:
        # IMPORTANT: pass the same pipeline used to build doc_body
        results, summary = divide_body_by_org_and_docs_serieIII(
            doc_body,
            payload,

        )
    else:
        # Keep your Serie I/II path as-is if you still use it elsewhere
        

        results,summary = divide_body_by_org_and_docs(
            doc_body,
            payload,
            write_org_files=False,
            write_doc_files=False,
        )
    return results,summary


import argparse
import sqlite3
import json
from datetime import datetime
from pathlib import Path

# your existing imports stay here
# from yourmodule import (
#     is_serie_iii, get_nlp, load_text_from_pdf,
#     build_docs, extract_relations_and_payload,
#     split_body, summarize_results
# )

def already_stored(conn, abs_path: str) -> bool:
    # Skip if we have ANY record for this absolute path (ok or error)
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM file_captures WHERE abs_path = ? COLLATE NOCASE LIMIT 1",
        (abs_path,),
    )
    return cur.fetchone() is not None



DB_PATH = Path("pdf_ingest.db")
DEFAULT_INPUT_DIR = Path("D:\\joram")

# ---------------------------------------------------------------
# Create the database tables if not existing
# ---------------------------------------------------------------
def ensure_db(conn):
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS import_runs (
        id INTEGER PRIMARY KEY,
        started_at TEXT NOT NULL,
        finished_at TEXT,
        root_path TEXT NOT NULL,
        status TEXT DEFAULT 'ok'
    );

    CREATE TABLE IF NOT EXISTS file_captures (
        id INTEGER PRIMARY KEY,
        import_run_id INTEGER NOT NULL REFERENCES import_runs(id) ON DELETE CASCADE,
        abs_path TEXT NOT NULL,
        file_name TEXT NOT NULL,
        captured_at TEXT NOT NULL,
        ingestion_status TEXT DEFAULT 'ok',
        ingestion_error TEXT
    );

    CREATE TABLE IF NOT EXISTS pdf_analysis_summaries (
        id INTEGER PRIMARY KEY,
        file_capture_id INTEGER NOT NULL REFERENCES file_captures(id) ON DELETE CASCADE,
        summary_json TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS details_snapshots (
        id INTEGER PRIMARY KEY,
        file_capture_id INTEGER NOT NULL REFERENCES file_captures(id) ON DELETE CASCADE,
        details_json TEXT NOT NULL
    );
    """)

# ---------------------------------------------------------------
# Main recursive PDF processor
# ---------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Process all PDFs recursively under input_pdfs/")
    parser.add_argument(
        "folder",
        nargs="?",
        default=str(DEFAULT_INPUT_DIR),
        help="Root folder to search for PDFs (default: input_pdfs/)"
    )
    args = parser.parse_args()

    root = Path(args.folder).resolve()
    if not root.exists():
        raise FileNotFoundError(f"Root folder not found: {root}")

    # connect to the SQLite DB
    conn = sqlite3.connect(DB_PATH)
    ensure_db(conn)
    cur = conn.cursor()

    # record import run
    started_at = datetime.now().isoformat()
    cur.execute(
        "INSERT INTO import_runs (started_at, root_path) VALUES (?, ?)",
        (started_at, str(root))
    )
    import_run_id = cur.lastrowid
    conn.commit()

    print(f"\n🟢 Started run {import_run_id} scanning {root}\n")

    # find all PDFs recursively
    pdf_files = list(root.rglob("*.pdf"))
    print(f"Found {len(pdf_files)} PDFs\n")

    for pdf_path in pdf_files:
        print(f"→ Processing: {pdf_path.name}")
        abs_path_str = str(pdf_path.resolve())

        if already_stored(conn, abs_path_str):
            print("Skipped (alredy stored)")
            continue
        try:
            # === your existing pipeline ===
            serie_iii = is_serie_iii(pdf_path.name)
            nlp = get_nlp(disable_ner=True, SerieIII=serie_iii)
            text = load_text_from_pdf(pdf_path)
            nlp.max_length = max(nlp.max_length, len(text) + 1)

            doc, doc_sumario, doc_body, sumario_text, body_text, _meta = build_docs(nlp, text)
            rels, payload = extract_relations_and_payload(doc_sumario, serie_iii)
            results, summary = split_body(doc_body, payload, serie_iii)
            test = summarize_results(results)
            # ================================

            # log the file in DB
            cur.execute(
                "INSERT INTO file_captures (import_run_id, abs_path, file_name, captured_at) VALUES (?, ?, ?, ?)",
                (import_run_id, str(pdf_path), pdf_path.name, datetime.now().isoformat())
            )
            file_capture_id = cur.lastrowid

            # save summary + details
            cur.execute(
                "INSERT INTO pdf_analysis_summaries (file_capture_id, summary_json) VALUES (?, ?)",
                (file_capture_id, json.dumps(test, ensure_ascii=False))
            )
            cur.execute(
                "INSERT INTO details_snapshots (file_capture_id, details_json) VALUES (?, ?)",
                (file_capture_id, json.dumps(results, ensure_ascii=False))
            )

            conn.commit()
            print(f"   ✅ Stored {pdf_path.name}")

        except Exception as e:
            print(f"   ❌ Error processing {pdf_path.name}: {e}")
            cur.execute(
                "INSERT INTO file_captures (import_run_id, abs_path, file_name, captured_at, ingestion_status, ingestion_error) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    import_run_id,
                    str(pdf_path),
                    pdf_path.name,
                    datetime.now().isoformat(),
                    "error",
                    str(e)
                )
            )
            conn.commit()
            continue

    # finalize run
    finished_at = datetime.now().isoformat()
    cur.execute(
        "UPDATE import_runs SET finished_at = ?, status = ? WHERE id = ?",
        (finished_at, "done", import_run_id)
    )
    conn.commit()
    conn.close()

    print(f"\n🏁 Run {import_run_id} completed at {finished_at}\n")

# ---------------------------------------------------------------
if __name__ == "__main__":
    main()
