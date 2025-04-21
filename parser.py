import re

def is_url(s):
    return re.match(r'https?://\S+', s)

def is_email_or_user(s):
    return re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', s) or re.match(r'^[a-zA-Z0-9._-]{3,}$', s)

def extract_credentials(text):
    lines = text.splitlines()
    results = []

    for line in lines:
        parts = re.split(r'[ \t|:]+', line.strip())
        if len(parts) < 2:
            continue

        url, login, password = None, None, None

        for part in parts:
            if not url and is_url(part):
                url = part
            elif not login and is_email_or_user(part):
                login = part
            elif not password:
                password = part

        if url and login and password:
            results.append({
                "url": url,
                "login": login,
                "password": password
            })

    return results
