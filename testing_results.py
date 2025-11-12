def summarize_results(results):
    org_count = len(results)

    total_texts = 0  # number of docs with a non-empty 'text'
    empty_text_count = 0  # number of docs where 'text' missing/empty
    empty_docs_orgs = 0  # number of org entries whose 'docs' is empty

    for item in results:
        docs = item.get("docs", [])
        if not docs:
            empty_docs_orgs += 1
        for d in docs:
            txt = d.get("text")
            if isinstance(txt, str) and txt.strip():
                total_texts += 1
            else:
                empty_text_count += 1

    return {
        "org_count": org_count,
        "text_count": total_texts,
        "empty_docs": {
            "exists": empty_docs_orgs > 0,
            "count": empty_docs_orgs,  # number of orgs with an empty 'docs' list
        },
        "empty_text": {
            "exists": empty_text_count > 0,
            "count": empty_text_count,  # number of docs with missing/empty 'text'
        },
    }
