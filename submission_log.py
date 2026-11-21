"""Store submitted purchase form inputs through the Supabase Data API."""
import json
import logging
import re
from http.client import HTTPException, HTTPSConnection


def record_submission(project_url, secret_key, inputs):
    """Return whether Supabase confirmed the insert."""
    if not isinstance(project_url, str) or not isinstance(secret_key, str):
        logging.warning('Invalid Supabase submission log configuration.')
        return False

    project = re.fullmatch(r'https://([a-z0-9-]+\.supabase\.co)/?', project_url)
    if not project or not secret_key.startswith('sb_secret_'):
        logging.warning('Invalid Supabase submission log configuration.')
        return False

    connection = HTTPSConnection(project.group(1), timeout=4)
    try:
        connection.request(
            'POST', '/rest/v1/purchase_submissions',
            body=json.dumps({'inputs': inputs}),
            headers={
                'apikey': secret_key,
                'Content-Type': 'application/json',
                'Prefer': 'return=minimal',
            },
        )
        status = connection.getresponse().status
        if status == 201:
            return True
        logging.warning('Supabase submission insert returned HTTP %d.', status)
    except (OSError, HTTPException, ValueError):
        logging.warning('The Supabase submission log request failed.')
    finally:
        connection.close()
    return False
