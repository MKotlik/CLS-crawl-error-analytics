import requests
from requests.exceptions import TooManyRedirects
import csv
import time
import sys
import traceback
import json
import unicodedata
from datetime import datetime
from bs4 import BeautifulSoup
from HTMLParser import HTMLParseError
from pprint import pprint
import searcher

# TODO: make error categories consistent
# TODO: turn timed_process_errors into a wrapped function
# TODO: improve printouts during processing (& allow them to be controllable)
# TODO: add timeouts to limit how long this takes
# TODO: add config file support
# TODO: add title field to errors to prevent double-scraping?

ERRORS_LIST_FILENAME = 'www-law-columbia-edu_20170619T193831Z_CrawlErrors.csv'


def timed_process_errors(errors_filename, start=0, end=None):
    print "======== BEGIN PROCESSING LINK ERRORS ========"
    time_start = time.time()
    print "TIME AT START: " + str(datetime.now())
    result = process_errors(errors_filename, start, end)
    print "======== END PROCESSING LINK ERRORS ========"
    time_end = time.time()
    print "TIME AT END: " + str(datetime.now())
    print "TIME TAKEN: " + str(round(time_end - time_start)) + "s"
    return result


def process_errors(errors_filename, start=0, end=None):
    errors_list = get_errors_list(errors_filename)
    if end is None:
        end = len(errors_list)
    print "LENGTH OF errors_list: " + str(len(errors_list))
    print "STARTING INDEX: " + str(start) + "; ENDING INDEX: " + str(end)
    print "---Checking for download links---"
    errors_list = ignore_downloads(errors_list, start, end)
    print "---Checking for already redirected pages---"
    print "HOSTS: Setting hosts file to point to new server"
    set_redirect(False)
    errors_list = check_new_redirects(errors_list, start, end)
    print "---Analyzing pages on old server---"
    print "HOSTS: Setting hosts file to point to old server"
    set_redirect(True)
    errors_list = parse_old_pages(errors_list, start, end)
    print "---Searching new server for possible matches---"
    print "HOSTS: Setting hosts file to point to new server"
    set_redirect(True)
    errors_list = get_possible_matches(errors_list, start, end)
    # Cleanup
    print "---Cleaning up---"
    print "HOSTS: Resetting hosts file to point to new server"
    set_redirect(False)
    return errors_list[start:end]


def analyze_results(results):
    ignored = [er for er in results if er['searchStatus'] == 'ignoredDwnld']
    done = [er for er in results if er['searchStatus'] == 'alreadyRedirected']
    dead_page = [er for er in results if er['searchStatus'] == 'deadPage']
    server_404 = [er for er in results if er['searchStatus'] == 'server404']
    redirect_404 = [er for er in results if er[
        'searchStatus'] == 'redirect404']
    redirected = [er for er in results if er['searchStatus']
                  == 'serverRedirect']
    server_500 = [er for er in results if er['searchStatus'] == 'serverError']
    server_400 = [er for er in results if er['searchStatus'] == 'server400']
    redirects = [er for er in results if er['searchStatus']
                 == 'redirectsError']
    new_redirects = [er for er in results if er['searchStatus']
                     == 'newServerRedirectsError']
    new_unknown = [er for er in results if er['searchStatus']
                   == 'unknownNewRequestError']
    old_unknown = [er for er in results if er['searchStatus']
                   == 'unknownOldRequestError']
    parse_errors = [er for er in results if er['searchStatus']
                    == 'parseError']
    need_login = [er for er in results if er['searchStatus'] == 'needsLogin']
    check = [er for er in results if er['searchStatus'] == 'check']
    short_name = [er for er in results if er['searchStatus'] == 'shortName']
    found_name = [er for er in results if er['searchStatus'] == 'foundName']
    no_matches = [er for er in results if er['searchStatus'] == 'noMatches']
    matched = [er for er in results if er['searchStatus'] == 'matched']
    report = []
    report.append('===== ANALYSIS OF PROCESSED ERRORS =====')
    report.append("Length of Errors List: " + str(len(results)))
    report.append('Number of ignored downloads: ' + str(len(ignored)))
    report.append('Number of already redirected pages: ' + str(len(done)))
    report.append('Number of dead pages on old server: ' +
                  str(len(dead_page)))
    report.append('Number of 404 pages on old server: ' +
                  str(len(server_404)))
    report.append('Number of pages redirecting to 404 on old server: ' +
                  str(len(redirect_404)))
    report.append(
        'Number of pages giving error 500 on old server: ' + str(len(server_500)))
    report.append(
        'Number of pages giving error 400 on old server: ' + str(len(server_400)))
    report.append('Number of pages redirecting on old server: ' +
                  str(len(redirected)))
    report.append(
        'Number of pages giving redirection errors on old server: ' + str(len(redirects)))
    report.append(
        'Number of pages giving redirection errors on new server: ' + str(len(new_redirects)))
    report.append(
        'Number of pages giving unknown errors on old server: ' + str(len(old_unknown)))
    report.append(
        'Number of pages giving unknown errors on new server: ' + str(len(new_unknown)))
    report.append('Number of pages resulting in parser errors: ' +
                  str(len(parse_errors)))
    report.append(
        'Number of pages needing login on old server: ' + str(len(need_login)))
    report.append('Number of pages with one-word titles: ' +
                  str(len(short_name)))
    report.append('Number of pages with matcheable names: ' +
                  str(len(found_name)))
    report.append(
        'Number of pages requiring hand matching: ' + str(len(check)))
    report.append('Number of pages with no matches: ' + str(len(no_matches)))
    report.append('Number of pages that have been matched: ' +
                  str(len(matched)))
    report.append('===== END ANALYSIS OF PROCESSED ERRORS =====')
    report_str = "\n".join(report)
    analysis = {'results': results, 'ignored': ignored, 'done': done,
                'dead_pages': dead_page, 'server_errors': server_500,
                'old_redirects': redirects, 'new_redirects': new_redirects,
                'redirected': redirected, 'new_unknown_errors': new_unknown,
                'old_unknown_errors': old_unknown, 'need_login': need_login,
                'short_names': short_name, 'found_name': found_name,
                'no_matches': no_matches, 'matched': matched,
                'check': check, 'report': report_str,
                'parse_error': parse_errors, 'server_404': server_404,
                'redirect_404': redirect_404, 'server_400': server_400}
    print report_str
    return analysis


def parse_old_pages(errors_list, start=0, end=None):
    # NOTE: combined with title scraper, since Soup-ing twice is inefficient
    for error in errors_list[start:end]:
        if error['searchStatus'] == 'check':
            try:
                resp = requests.get(error['url'])
                error['oldServerCode'] = resp.status_code
                # DEBUG
                # print "Url: " + resp.url + '; Code: ' + str(resp.status_code)
                if resp.status_code == 404:
                    error['searchStatus'] = 'server404'
                elif resp.status_code == 302 or resp.status_code == 301:
                    error['searchStatus'] = 'serverRedirect'
                elif resp.status_code == 500:
                    error['searchStatus'] = 'serverError'
                else:
                    soup = BeautifulSoup(resp.content, 'lxml')
                    title = soup.find('title')
                    pre_404 = soup.find('pre')
                    if title is not None:
                        title = title.text.lower()
                        if '404' in title:
                            # DEBUG PRINT STATEMENT FOR 404 TITLES
                            print 'FOUND TITLE 404 PAGE: ' + error['url']
                            error['old404Redirect'] = True
                            error['searchStatus'] = 'redirect404'
                        elif 'login' in title or 'sign in' in title:
                            # DEBUG PRINT STATEMENT FOR LOGIN TITLES
                            print 'FOUND TITLE LOGIN PAGE: ' + error['url']
                            error['searchStatus'] = 'needsLogin'
                        else:
                            # DEBUG ONLY
                            # print "LOOKING FOR TITLE"
                            heading, full_heading = parse_title(title)
                            if heading is not None:
                                # DEBUG ONLY
                                # print "TITLE IS NOT NONE"
                                if ' ' not in heading:
                                    # If name is one word, mark and hand check
                                    error['searchStatus'] = 'shortName'
                                else:
                                    # Mark that probable name was found
                                    error['searchStatus'] = 'foundName'
                                # Always set name to whatever was found
                                error['pageName'] = heading
                                error['fullName'] = full_heading
                            # Couldn't find meaninful title
                            # If page is an event page, look for JS title
                            elif 'calendar/event' in error['url']:
                                script_tags = soup.find_all('script')
                                # pprint(script_tags)
                                for script in script_tags:
                                    if 'document.title' in script.text:
                                        # print "FOUND TITLE SCRIPT"
                                        # print script.text
                                        js_ind = script.text.find(
                                            'document.title')
                                        title_ind = js_ind + 18
                                        end_ind = script.text.find(' |')
                                        js_title = script.text[
                                            title_ind: end_ind]
                                        error['pageName'] = js_title
                                        error['fullName'] = js_title + \
                                            " | " + soup.title.string
                                        if ' ' not in js_title:
                                            # If name is one word, mark and
                                            # hand check
                                            error['searchStatus'] = 'shortName'
                                        else:
                                            # Mark that probable name was found
                                            error['searchStatus'] = 'foundName'
                                        print 'PARSED TITLE FROM SCRIPT TAG IN: ' + error['url']
                    elif pre_404 is not None:
                        if '404' in pre_404.text:
                            # DEBUG PRINT STATEMENT FOR 404 TITLES
                            print 'FOUND TITLE 404 PAGE: ' + error['url']
                            error['old404Redirect'] = True
                            error['searchStatus'] = 'redirect404'
            except TooManyRedirects as e:
                error['searchStatus'] = 'redirectsError'
                log_error(error['url'])
                print "TOO MANY REDIRECTS ERROR for " + error['url']
            except HTMLParseError as e:
                error['searchStatus'] = 'parseError'
                log_error(error['url'])
                print "GOT AN HTMLParseError! Needs hand checking!"
                for item in sys.exc_info():
                    print item
                print 'CONTINUING'
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                error['searchStatus'] = 'unknownOldRequestError'
                log_error(error['url'])
                print 'CAUGHT UNKNOWN ERROR WHILE QUERYING OLD SERVER'
                for item in sys.exc_info():
                    print item
                print 'CONTINUING'
        # Completion DEBUG
        print 'Parsed old: ' + error['url'] + '; Status: ' + error['searchStatus']
    return errors_list


def check_new_redirects(errors_list, start=0, end=None):
    for error in errors_list[start:end]:
        if error['searchStatus'] == 'check':
            try:
                resp = requests.get(error['url'])
                error['newServerCode'] = resp.status_code
                if resp.status_code == 200:
                    # DEBUG PRINT STATEMENT FOR REDIRECTED PAGES
                    print 'FOUND REDIRECTED PAGE: ' + error['url']
                    error['searchStatus'] = 'alreadyRedirected'
            except TooManyRedirects as e:
                print "TOO MANY REDIRECTS ERROR for " + error['url']
                log_error(error['url'])
                error['searchStatus'] = 'newServerRedirectsError'
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                error['searchStatus'] = 'unknownNewRequestError'
                log_error(error['url'])
                print 'CAUGHT UNKNOWN ERROR WHILE QUERYING NEW SERVER'
                for item in sys.exc_info():
                    print item
                print 'CONTINUING'
        # Completion DEBUG
        print 'Parsed new: ' + error['url'] + '; Status: ' + error['searchStatus']
    return errors_list


def ignore_downloads(errors_list, start=0, end=None):
    for error in errors_list[start:end]:
        has_null = error['url'].startswith('http://www.law.columbia.edu/null')
        if has_null or 'filemgr' in error['url']:
            error['searchStatus'] = 'ignoredDwnld'
    return errors_list


def get_possible_matches(errors_list, start=0, end=None):
    if end is None:
        end = len(errors_list)
    # Configure searcher module
    api_key = searcher.load_config()
    cse_id = "013164244572636035941:csl0bhjaaa4"
    base_url = searcher.get_base_url(api_key, cse_id)
    print "start: " + str(start)
    print "end: " + str(end)
    for error in errors_list[start:end]:
        # Only search for links with found names
        if error['searchStatus'] == 'foundName':
            # Try searching for exact match first
            quoted = '"' + error['pageName'] + '"'
            matches = searcher.search(base_url, quoted)
            if matches is None:  # Stop if searcher error occurred
                break
            elif len(matches) == 0:
                # Search for all keywords if no exact match found
                reg_matches = searcher.search(base_url, error['pageName'])
                # Label as noMatches if still nothing found
                if len(reg_matches) == 0:
                    error['searchStatus'] = 'noMatches'
                else:
                    # Save top 10, but only print top 3 in csv
                    error['possibleUrls'] = reg_matches[0:10]
                    error['searchStatus'] = 'matched'
            else:
                # Save top 10, but only print top 3 in csv
                error['possibleUrls'] = matches[0:10]
                error['searchStatus'] = 'matched'
        print 'Searched for: ' + error['url'] + '; Status: ' + error['searchStatus']
    return errors_list


def parse_title(page_title):
    # Return tuple of first element of title and string of all title parts
    if '|' in page_title:
        title_parts = page_title.split('|')
    elif ':' in page_title:
        title_parts = page_title.split(':')
    else:
        title_parts = [page_title]
    heading = None
    full_heading = []
    for part in title_parts:
        part = part.strip().lower()
        if part != 'columbia law school' and part != 'event':
            full_heading.append(part)
            # First element of title is most likely name, so use only that
            if heading is None:
                heading = part
    # return (heading, ' '.join(full_heading))
    return (heading, page_title)


def get_errors_list(errors_filename):
    errors_list = []
    with open(errors_filename, 'rb') as errors_csv:
        error_reader = csv.DictReader(errors_csv)
        for row in error_reader:
            errors_list.append({'url': row['URL'],
                                'lastCrawled': row['Last crawled'],
                                'origCode': row['Response Code'],
                                'oldServerCode': None,
                                'old404Redirect': False,
                                'newServerCode': None,
                                'searchStatus': 'check',
                                'pageName': None,
                                'fullName': None,
                                'possibleUrls': []})
    return errors_list


def set_redirect(bool):
    hosts_rule = '128.59.176.155   www.law.columbia.edu\n'
    if bool is True:  # Add rule to hosts file
        with open('/etc/hosts', 'r') as hosts_file:
            hosts_lines = hosts_file.readlines()
        if hosts_lines[-1] == hosts_rule:
            print "HOSTS: Hosts file already set for old server"
        else:
            with open('/etc/hosts', 'a') as hosts_file:
                hosts_file.write(hosts_rule)
    else:  # Remove rule from hosts file
        with open('/etc/hosts', 'r') as hosts_file:
            hosts_lines = hosts_file.readlines()
        if hosts_lines[-1] != hosts_rule:
            print "HOSTS: Hosts file already set for new server"
        else:
            with open('/etc/hosts', 'w') as hosts_file:
                for line in hosts_lines[:-2]:
                    hosts_file.write(line)


def load_json(filename):
    with open(filename, 'r') as json_file:
        data = json.load(json_file)
        return data


def save_json(errors_list, start, end):
    filename = 'data/processed_errors_' + str(start) + '-' + str(end) + '.json'
    with open(filename, 'w') as errors_file:
        json.dump(errors_list, errors_file)


def save_csv(errors_list, start=0, end=None, sort=True):
    if end is None:
        end = len(errors_list)
    # Run analysis to separate matches from the rest
    analysis = analyze_results(errors_list)
    overall_filename = 'data/report_' + str(start) + '-' + str(end) + '.csv'
    match_filename = 'data/matchesfor_' + str(start) + '-' + str(end) + '.csv'
    hand_filename = 'data/byhand_' + str(start) + '-' + str(end) + '.csv'
    # Write overall report
    with open(overall_filename, 'wb') as csv_file:
        field_names = ['URL', 'Search Status', 'Last Crawled', 'Page Title',
                       'Full Name', 'Explanation', 'Status on New Server',
                       'Status on Old Server',
                       'Redirect on Old Server', 'Original Status']
        file_writer = csv.DictWriter(csv_file, fieldnames=field_names)
        file_writer.writeheader()
        rows = []
        for item in errors_list:
            # entry = {i: item[i] for i in item if i != 'possibleUrls'}
            is_courses = item['url'].startswith(
                'http://www.law.columbia.edu/courses')
            entry = {'URL': item['url'],
                     'Search Status': get_verbose_status(item['searchStatus']),
                     'Last Crawled': item['lastCrawled'],
                     'Page Title': item['pageName'],
                     'Full Name': item['fullName'],
                     'Explanation': get_status_msg(item['searchStatus']),
                     'Status on New Server': item['newServerCode'],
                     'Status on Old Server': item['oldServerCode'],
                     'Redirect on Old Server': item['old404Redirect'],
                     'Original Status': item['origCode']
                     }
            if is_courses and item['searchStatus'] == 'matched':
                entry['Search Status'] = 'Ignored Courses Page'
                entry['Explanation'] = 'Old course manager pages should no longer be accessible.'
            # if ',' in entry['URL']:
            #     entry['URL'] = '"' + entry['URL'] + '"'
            #     print 'GOT COMMA IN REPORT URL, NEW URL: ' + entry['URL']
            rows.append(entry)
        if sort:
            rows = sorted(rows, key=lambda k: k['Search Status'])
        for entry in rows:
            try:
                file_writer.writerow(entry)
            except UnicodeEncodeError:
                print "GOT UNICODE ERROR, TRYING AGAIN:"
                entry['Page Title'] = unicodedata.normalize(
                    'NFKD', entry['Page Title']).encode('ascii', 'ignore')
                entry['Full Name'] = unicodedata.normalize(
                    'NFKD', entry['Full Name']).encode('ascii', 'ignore')
                pprint(entry)
                file_writer.writerow(entry)
    # Write matches file
    with open(match_filename, 'wb') as csv_file:
        field_names = ['URL', 'Page Title', 'Full Name', 'Match Name',
                       'Match URL']
        file_writer = csv.DictWriter(csv_file, fieldnames=field_names)
        file_writer.writeheader()
        for item in analysis['matched']:
            is_courses = item['url'].startswith(
                'http://www.law.columbia.edu/courses')
            # RESTRICT MATCHES TO TOP 3
            if not is_courses:
                for match in item['possibleUrls'][0:3]:
                    match_row = {'URL': item['url'], 'Page Title': item['pageName'],
                                 'Full Name': item['fullName'],
                                 'Match Name': match['title'],
                                 'Match URL': match['link']}
                    # if ',' in match_row['URL']:
                    #     print 'GOT COMMA IN MATCH URL: ' + match_row['URL']
                    #     match_row['URL'] = '"' + match_row['URL'] + '"'
                    try:
                        # pprint(match_row)
                        file_writer.writerow(match_row)
                    except UnicodeEncodeError:
                        print "GOT UNICODE ERROR, TRYING AGAIN:"
                        match_row['Page Title'] = unicodedata.normalize(
                            'NFKD', match_row['Page Title']).encode('ascii', 'ignore')
                        match_row['Full Name'] = unicodedata.normalize(
                            'NFKD', match_row['Full Name']).encode('ascii', 'ignore')
                        match_row['Match Name'] = unicodedata.normalize(
                            'NFKD', match_row['Match Name']).encode('ascii', 'ignore')
                        pprint(match_row)
                        file_writer.writerow(match_row)
    # Write hand matching file, for short names, no names, or parse errors
    with open(hand_filename, 'wb') as csv_file:
        field_names = ['URL', 'Page Title', 'Full Name']
        file_writer = csv.DictWriter(csv_file, fieldnames=field_names)
        file_writer.writeheader()
        by_hand = analysis['short_names'] + \
            analysis['check'] + analysis['parse_error']
        for item in by_hand:
            row = {'URL': item['url'], 'Page Title': item['pageName'],
                   'Full Name': item['fullName']}
            # if ',' in row['URL']:
            #     print 'GOT COMMA IN BY HAND URL: ' + row['URL']
            #     row['URL'] = '"' + row['URL'] + '"'
            try:
                # pprint(row)
                file_writer.writerow(row)
            except UnicodeEncodeError:
                print "GOT UNICODE ERROR, TRYING AGAIN:"
                row['Page Title'] = unicodedata.normalize(
                    'NFKD', row['Page Title']).encode('ascii', 'ignore')
                row['Full Name'] = unicodedata.normalize(
                    'NFKD', row['Full Name']).encode('ascii', 'ignore')
                pprint(row)
                file_writer.writerow(row)


def get_verbose_status(searchStatus):
    if searchStatus == 'alreadyRedirected':
        return 'Already Redirected'
    elif searchStatus == 'ignoredDwnld':
        return 'Ignored Download Page'
    elif searchStatus == 'deadPage':
        return 'Dead Page'
    elif searchStatus == 'server404':
        return '404 on Old Server'
    elif searchStatus == 'redirect404':
        return 'Redirect to 404 on Old Server'
    elif searchStatus == 'serverError':
        return '500 on Old Server'
    elif searchStatus == 'server400':
        return '400 on Old Server'
    elif searchStatus == 'redirectsError':
        return 'Redirects Timeout on Old Server'
    elif searchStatus == 'newServerRedirectsError':
        return 'Redirects Timeout on New Server'
    elif searchStatus == 'unknownNewRequestError':
        return 'SSL Cert Error on New Server'
    elif searchStatus == 'unknownOldRequestError':
        return 'SSL Cert Error on Old Server'
    elif searchStatus == 'parseError':
        return 'Error while parsing page'
    elif searchStatus == 'needsLogin':
        return 'Page Needs Login'
    elif searchStatus == 'check':
        return 'No Title Found on Old Server'
    elif searchStatus == 'shortName':
        return 'Title Too Short'
    elif searchStatus == 'foundName':
        return 'Found Name, Needs Matching'
    elif searchStatus == 'noMatches':
        return 'No Matches Found on New Server'
    elif searchStatus == 'matched':
        return 'Matched'


def get_status_msg(searchStatus):
    if searchStatus == 'alreadyRedirected':
        return 'Link points to a page on the new server (200 response).'
    elif searchStatus == 'ignoredDwnld':
        return 'Link points to download manager on old server.'
    elif searchStatus == 'deadPage':
        return 'Page does not exist on the old server.'
    elif searchStatus == 'server404':
        return 'Old server returns a 404 response for this page.'
    elif searchStatus == 'redirect404':
        return 'Old server attempts to redirect to a 404 page for this page.'
    elif searchStatus == 'serverError':
        return 'Old server returns a 500 (server error) response for this page.'
    elif searchStatus == 'server400':
        return 'Link results in a bad request to the server.'
    elif searchStatus == 'redirectsError':
        return 'Accessing this page on the old server creates a redirect loop, resulting in a timeout.'
    elif searchStatus == 'newServerRedirectsError':
        return 'Accessing this page on the new server creates a redirect loop, resulting in a timeout.'
    elif searchStatus == 'unknownNewRequestError':
        return 'Page cannot be accessed on new server due to SSL or unknown error.'
    elif searchStatus == 'unknownOldRequestError':
        return 'Page cannot be accessed on old server due to SSL or unknown error.'
    elif searchStatus == 'parseError':
        return 'Error while parsing page (the script failed).'
    elif searchStatus == 'needsLogin':
        return 'Page requires login to view, was most likely purposefully hidden by admin.'
    elif searchStatus == 'check':
        return 'Script couldn\'t extract a page name, needs to be matched by hand'
    elif searchStatus == 'shortName':
        return 'Page name is only one word long, too short for accurate search. Match by hand.'
    elif searchStatus == 'foundName':
        return 'Found name, needs matching by script.'
    elif searchStatus == 'noMatches':
        return 'No matches found'
    elif searchStatus == 'matched':
        return 'Script found likely matching urls; check matches spreadsheet.'


def log_error(url):
    error_time = str(datetime.now())
    report = "=============ERROR=============\n"
    report += "TIME: " + error_time + "\n"
    report += "URL: " + url + "\n"
    report += "ERROR CLASS: " + str(sys.exc_info()[0]) + "\n"
    report += traceback.format_exc()
    report += "-------------------------------\n"
    with open('matcher_errors.log', 'a') as log_file:
        log_file.write(report)


def timer(method):
    def wrapper(*args, **kw):
        startTime = int(round(time.time() * 1000))
        result = method(*args, **kw)
        endTime = int(round(time.time() * 1000))

        print(endTime - startTime, 'ms')
        return result

    return wrapper


def redo_dead_pages(errors_list):
    analysis = analyze_results(errors_list)
    dead_pages = analysis['dead_pages']
    cnt = len(dead_pages)
    print "FINDING SPECIFIC 404 ISSUES FOR " + str(cnt) + " DEAD_PAGES"
    for page in dead_pages:
        page['searchStatus'] = 'check'
    set_redirect(True)
    redo = parse_old_pages(dead_pages)
    corrected = []
    # Stitch analysis categories into almost full corrected list
    for cat in analysis:
        if cat != 'results' and cat != 'report' and cat != 'dead_pages':
            corrected.extend(analysis[cat])
    # Add more specific 404 cats into list
    corrected.extend(redo)
    print "END CORRECTED DEAD_PAGES SPECIFICITY"
    return corrected


def load_all():
    first = load_json('data/processed_errors_0-500.json')
    second = load_json('data/processed_errors_500-1000.json')
    third = load_json('data/processed_errors_1000-1500.json')
    fourth = load_json('data/processed_errors_1500-2000.json')
    fifth = load_json('data/processed_errors_2000-2208.json')
    return first + second + third + fourth + fifth


def load_total():
    return load_json('data/processed_errors_0-2208.json')


def save_statistics(errors_list, start=0, end=None, sort=True):
    if end is None:
        end = len(errors_list)
    analysis = analyze_results(errors_list[start:end])
    total_cnt = len(errors_list)
    rows = []
    field_names = ['Search Status', 'Count', '% of Total', "Explanation"]
    for key in analysis:
        isnt_meta = (key != 'results' and key != 'report')
        isnt_error = (key != 'dead_pages' and key != 'new_unknown_errors')
        isnt_redirect = (key != 'redirected' and key != 'new_redirects')
        isnt_four = (key != 'parse_error' and key != 'found_name')
        nempty = len(analysis[key]) > 0
        if isnt_meta and isnt_error and isnt_redirect and isnt_four and nempty:
            # print key
            status = get_verbose_status(analysis[key][0]['searchStatus'])
            explain = get_status_msg(analysis[key][0]['searchStatus'])
            cnt = len(analysis[key])
            stat = {'Search Status': status, 'Count': cnt,
                    '% of Total': get_percent(cnt, total_cnt),
                    'Explanation': explain}
            rows.append(stat)
    rows.append({'Search Status': 'Total', 'Count': total_cnt,
                 '% of Total': '100%'})
    if sort:
        rows_sorted = sorted(rows, key=lambda k: k['Count'])
    else:
        rows_sorted = rows
    filename = 'data/stats_' + str(start) + '-' + str(end) + '.csv'
    with open(filename, 'wb') as csv_file:
        file_writer = csv.DictWriter(csv_file, fieldnames=field_names)
        file_writer.writeheader()
        for row in rows_sorted:
            file_writer.writerow(row)


def get_percent(count, total):
    return str(round((count / float(total)) * 100, 2)) + '%'


def count_facade(errors_list):
    cnt = 0
    for error in errors_list:
        if len(error['possibleUrls']) > 0:
            if 'facade1' in error['possibleUrls'][0]['link']:
                cnt += 1
    return cnt


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


if __name__ == "__main__":
    pprint(process_errors(ERRORS_LIST_FILENAME, 0, 10))
