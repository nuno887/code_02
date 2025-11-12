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
from typing import Optional


DEFAULT_INPUT_DIR = Path("input_pdfs")
CROP_TOP_RATIO = 0.10
SKIP_LAST_PAGE = True


def is_serie(filename: str) -> Optional[int]:

    if "iiiserie" in filename.lower():
        return 3
    if "iiserie" in filename.lower():
        return 2
    if "iserie" in filename.lower():
        return 1
    if "ivserie" in filename.lower():
        return 4
    return None


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



def main():

    file = Path("input_pdfs") / "doc"


    serie = is_serie(file.name)
    nlp = get_nlp(serie)
    text= load_text_from_pdf(file)
    nlp.max_length = max(nlp.max_length, len(text) + 1)

    doc, doc_sumario, doc_body, sumario_text, body_text, _meta = build_docs(nlp, text)
    rels, payload = extract_relations_and_payload (doc_sumario, serie)
    results, summary = split_body(doc_body, payload, serie)

    