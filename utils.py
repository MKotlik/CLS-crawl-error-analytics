"""
utils structure:

**Procesing helpers**
- set_redirect
- parse_title
- timer

*Analysis helpers**
- get_verbose_status
- get_status_msg
- get_percent
- count_facade? [should be unnecessary]

**Storage helpers**
- load_json
- save_json
"""


# Processing helpers

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


def timer(method):
    def wrapper(*args, **kw):
        startTime = int(round(time.time() * 1000))
        result = method(*args, **kw)
        endTime = int(round(time.time() * 1000))

        print(endTime - startTime, 'ms')
        return result

    return wrapper


# Analysis helpers

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


def get_percent(count, total):
    return str(round((count / float(total)) * 100, 2)) + '%'


def count_facade(errors_list):
    cnt = 0
    for error in errors_list:
        if len(error['possibleUrls']) > 0:
            if 'facade1' in error['possibleUrls'][0]['link']:
                cnt += 1
    return cnt


# Storage helpers

def load_json(filename):
    with open(filename, 'r') as json_file:
        data = json.load(json_file)
        return data


def save_json(errors_list, start, end):
    filename = 'data/processed_errors_' + str(start) + '-' + str(end) + '.json'
    with open(filename, 'w') as errors_file:
        json.dump(errors_list, errors_file)
