import time
import re
import pandas as pd
from habanero import Crossref

# Initialize Crossref with a polite mailto and increased timeout
cr = Crossref(mailto="25D0222@iitb.ac.in", timeout=30)

def safe_works_call(**kwargs):
    """Wrapper for Crossref.works with retry logic and exponential backoff."""
    retries = 3
    for attempt in range(retries):
        try:
            return cr.works(**kwargs)
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
            else:
                raise e

def chunk_keywords(keywords, chunk_size=3):
    """Yield successive n-sized chunks from keywords."""
    for i in range(0, len(keywords), chunk_size):
        yield keywords[i:i + chunk_size]


def normalise_text(text):
    """Normalize text by converting to lowercase and handling subscripts."""
    if not text:
        return ""

    text = text.lower()

    # Handle subscript characters (₂, ₃, etc.)
    subscript_map = {
        '₂': '2', '₃': '3', '₁': '1', '₀': '0',
        '₄': '4', '₅': '5', '₆': '6', '₇': '7', '₈': '8', '₉': '9'
    }

    for sub, normal in subscript_map.items():
        text = text.replace(sub, normal)

    return text


def check_keyword_match(keyword, text):
    """Smart keyword matching with plural handling."""
    if keyword in text:
        return True
    if keyword.endswith('s') and keyword[:-1] in text:
        return True
    if not keyword.endswith('s') and keyword + "s" in text:
        return True
    return False


def run_search(keywords, threshold, output_limit, year_range=None, selected_publishers=None, progress_callback=None):
    """
    Executes the search using Crossref API with robustness features.
    """
    # Safety checks
    MAX_KEYWORDS = 10
    if len(keywords) > MAX_KEYWORDS:
        # The app layer handles this with an error message, but safety first
        raise ValueError(f"Maximum {MAX_KEYWORDS} keywords allowed.")

    SEARCH_SPACE_LIMIT = 2000 
    relevant_papers_dict = {} 
    total_checked = 0
    
    # Publisher selection (DOI Prefixes)
    PUBLISHER_MAP = {
        "ACS": "10.1021",
        "RSC": "10.1039",
        "Wiley": "10.1002", # Simplified to primary prefix
        "Elsevier": "10.1016",
        "Springer": "10.1007",
        "Science": "10.1126"
    }
    
    allowed_prefixes = [PUBLISHER_MAP[p] for p in selected_publishers] if selected_publishers else []

    # Process keywords in chunks to improve Crossref relevance
    for kw_chunk in chunk_keywords(keywords, chunk_size=3):
        if total_checked >= SEARCH_SPACE_LIMIT:
            break
            
        query_string = " ".join(kw_chunk)
        
        # Build Filter
        search_filter = {'type': 'journal-article'}
        if year_range:
            start_year, end_year = year_range
            search_filter['from-pub-date'] = f"{start_year}-01-01"
            search_filter['until-pub-date'] = f"{end_year}-12-31"

        try:
            response_generator = safe_works_call(
                query_title=query_string,
                filter=search_filter,
                select=['DOI', 'title', 'author', 'issued', 'container-title'],
                sort='relevance',
                order='desc',
                limit=100,
                cursor="*",
                cursor_max=SEARCH_SPACE_LIMIT // 2 
            )

            for page in response_generator:
                items = page.get('message', {}).get('items', [])
                if not items:
                    break

                for item in items:
                    doi = item.get('DOI')
                    if not doi or doi in relevant_papers_dict:
                        continue
                    
                    # Publisher Filtering (Check Prefix)
                    if allowed_prefixes:
                        if not any(doi.startswith(prefix) for prefix in allowed_prefixes):
                            continue

                    total_checked += 1
                    if progress_callback and total_checked % 20 == 0:
                        progress_callback(total_checked, len(relevant_papers_dict))

                    if total_checked > SEARCH_SPACE_LIMIT:
                        break

                    title = item.get('title', [''])[0]
                    if not title:
                        continue

                    title_normalized = normalise_text(title)
                    matches = []
                    for kw in keywords:
                        kw_norm = normalise_text(kw)
                        if check_keyword_match(kw_norm, title_normalized):
                            matches.append(kw)

                    if len(set(matches)) >= threshold:
                        relevant_papers_dict[doi] = {
                            'DOI': doi,
                            'Title': title,
                            'Journal': item.get('container-title', [''])[0],
                            'First_Author': item.get('author', [{}])[0].get('family', ''),
                            'Year': item.get('issued', {}).get('date-parts', [[0]])[0][0],
                            'Matched_Keywords': ", ".join(matches),
                            'Match_Count': len(matches),
                            'Abstract': '' 
                        }
                    
                    if len(relevant_papers_dict) >= output_limit:
                        break
                
                if len(relevant_papers_dict) >= output_limit or total_checked > SEARCH_SPACE_LIMIT:
                    break

        except Exception as e:
            raise e

    if progress_callback:
        progress_callback(total_checked, len(relevant_papers_dict))

    df = pd.DataFrame(list(relevant_papers_dict.values()))
    if not df.empty:
        df = df.sort_values(['Match_Count', 'Year'], ascending=[False, False])
        
    return df

