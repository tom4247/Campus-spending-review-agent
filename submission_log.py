"""Store purchase submissions and chat review snapshots through Supabase."""
import json
import logging
import re
from http.client import HTTPException, HTTPSConnection


def record_submission(project_url, secret_key, inputs):
    return _write(project_url, secret_key, 'purchase_submissions', {'inputs': inputs})


def save_review(project_url, secret_key, snapshot):
    return _write(project_url, secret_key, 'purchase_reviews', snapshot, upsert=True)


def _write(project_url, secret_key, table, row, *, upsert=False):
    if not isinstance(project_url, str) or not isinstance(secret_key, str):
        logging.warning('Invalid Supabase submission log configuration.')
        return False

    project = re.fullmatch(r'https://([a-z0-9-]+\.supabase\.co)/?', project_url)
    if not project or not secret_key.startswith('sb_secret_'):
        logging.warning('Invalid Supabase submission log configuration.')
        return False

    connection = HTTPSConnection(project.group(1), timeout=4)
    try:
        preference = 'resolution=merge-duplicates,return=minimal' if upsert else 'return=minimal'
        connection.request(
            'POST', f'/rest/v1/{table}',
            body=json.dumps(row),
            headers={
                'apikey': secret_key,
                'Content-Type': 'application/json',
                'Prefer': preference,
            },
        )
        status = connection.getresponse().status
        if status in (200, 201, 204):
            return True
        logging.warning('Supabase write to %s returned HTTP %d.', table, status)
    except (OSError, HTTPException, ValueError):
        logging.warning('The Supabase submission log request failed.')
    finally:
        connection.close()
    return False
