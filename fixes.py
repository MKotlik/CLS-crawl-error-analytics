"""
fixes structure:

**Imports**
- imports url_matcher.py

**Fixing functions**
- load_all
- load_total
- finish_search
- finish_stage
"""

def load_all():
    first = load_json('data/processed_errors_0-500.json')
    second = load_json('data/processed_errors_500-1000.json')
    third = load_json('data/processed_errors_1000-1500.json')
    fourth = load_json('data/processed_errors_1500-2000.json')
    fifth = load_json('data/processed_errors_2000-2208.json')
    return first + second + third + fourth + fifth


def load_total():
    return load_json('data/processed_errors_0-2208.json')


def finish_search():
    # Finish searching through remaining links and merge
    main = load_json('data/processed_errors_0-2188.json')
    # Split the existing set by categories
    analysis = analyze_results(main)
    fixing = load_json('data/search-fix-2.json')
    # Split the search set into done and unfinished
    searched = [el for el in fixing if el['searchStatus'] != 'foundName']
    todo = [el for el in fixing if el['searchStatus'] == 'foundName']
    # Ensure that new server is being queried
    set_redirect(False)
    # Search for the remaining links
    results = get_possible_matches(todo)
    # Merge the previously searched and the new ones
    search_set = searched + todo
    # Go through analysis and merge all except 'noMatches' and 'matched'
    merged = []
    for cat in analysis:
        if (cat != 'results' and cat != 'report' and cat != 'no_matches' and
                cat != 'matched'):
            merged.extend(analysis[cat])
    # Merge search terms into it
    merged.extend(search_set)
    # Return the entire thing
    return merged


def finish_stage():
    # Redo-search for any links with web-stage or web-dev results
    main = load_json('data/processed_errors_0-2188.json')
    # Split the existing set by categories
    analysis = analyze_results(main)
    # Build the set of all links with such results
    fine = []
    redo = []
    # Look through all of the previously matched errors
    for item in analysis['matched']:
        matches = item['possibleUrls']
        i = 0
        search = False
        # Look through its matches until a bad link is found
        while search is False and i < len(matches):
            link = matches[i]['link']
            if 'web-stage' in link or 'web-dev' in link:
                # If bad link found, reset for re-searching
                item['searchStatus'] = 'foundName'
                item['possibleUrls'] = []
                redo.append(item)
                search = True
            i += 1
        if search is False:
            fine.append(item)
    # Ensure that new server is being queried
    set_redirect(False)
    # Search for the redo links
    results = get_possible_matches(redo)
    # Merge the fine and the redone
    matched = fine + redo
    # Go through analysis and merge all except 'noMatches' and 'matched'
    merged = []
    for cat in analysis:
        if cat != 'results' and cat != 'report' and cat != 'matched':
            merged.extend(analysis[cat])
    # Merge search terms into it
    merged.extend(matched)
    # Return the entire thing
    return merged
