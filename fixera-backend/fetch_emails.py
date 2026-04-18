"""
Fixera Email Complaint Fetcher
==============================
Production-ready script that fetches UNSEEN complaint emails from Gmail via IMAP,
extracts data, and stores in CSV. Designed for cron/scheduler execution.

Usage:
    python fetch_emails.py

Environment variables required:
    EMAIL    - Gmail address
    PASSWORD - Gmail App Password (NOT regular password)
"""

import imaplib
import email
import csv
import os
import sys
import logging
from email.utils import parseaddr
from email.header import decode_header
from datetime import datetime

# ---- Configuration ----
CSV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'complaints.csv')
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fetch_emails.log')
IMAP_SERVER = 'imap.gmail.com'
IMAP_PORT = 993
MAILBOX = 'INBOX'

# ---- Logging Setup ----
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger('fixera-email')


def decode_subject(subject_header):
    """Decode email subject, handling various encodings."""
    if subject_header is None:
        return '(No Subject)'

    decoded_parts = decode_header(subject_header)
    parts = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            try:
                parts.append(part.decode(charset or 'utf-8', errors='ignore'))
            except (LookupError, UnicodeDecodeError):
                parts.append(part.decode('utf-8', errors='ignore'))
        else:
            parts.append(str(part))

    return ' '.join(parts).strip() or '(No Subject)'


def extract_body(msg):
    """Extract plain text body from email message (handles multipart)."""
    body = ''

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get('Content-Disposition', ''))

            # Skip attachments
            if 'attachment' in content_disposition:
                continue

            if content_type == 'text/plain':
                try:
                    charset = part.get_content_charset() or 'utf-8'
                    payload = part.get_payload(decode=True)
                    if payload:
                        body = payload.decode(charset, errors='ignore')
                        break
                except Exception:
                    continue
    else:
        try:
            charset = msg.get_content_charset() or 'utf-8'
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode(charset, errors='ignore')
        except Exception:
            body = ''

    # Clean up body text
    body = body.strip()
    # Limit length for CSV storage
    if len(body) > 5000:
        body = body[:5000] + '...'

    return body or '(No body content)'


def ensure_csv_exists():
    """Create CSV file with headers if it doesn't exist, or fix missing headers."""
    headers = ['email', 'subject', 'description', 'fetched_at']
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
        logger.info(f'Created CSV file: {CSV_FILE}')
        return

    # Check if header exists — fix if missing
    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        first_line = f.readline().strip().lower()
    if 'email' not in first_line or 'description' not in first_line:
        # Prepend header to existing data
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            existing = f.read()
        with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            f.write(existing)
        logger.info('Restored missing CSV headers.')


def append_to_csv(rows):
    """Append complaint rows to CSV file."""
    with open(CSV_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow(row)


def fetch_and_store_emails():
    """
    Main function: connects to Gmail, fetches UNSEEN emails,
    extracts complaint data, and stores in CSV.
    """

    # ---- Load credentials from environment ----
    email_addr = os.getenv('EMAIL')
    password = os.getenv('PASSWORD')

    if not email_addr or not password:
        logger.error('Missing EMAIL or PASSWORD environment variables.')
        logger.error('Set them with: export EMAIL="you@gmail.com" PASSWORD="your-app-password"')
        sys.exit(1)

    # ---- Ensure CSV file exists ----
    ensure_csv_exists()

    # ---- Connect to Gmail IMAP ----
    mail = None
    try:
        logger.info('Connecting to Gmail IMAP...')
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(email_addr, password)
        logger.info('Login successful.')

        mail.select(MAILBOX)

        # ---- Search for UNSEEN emails ----
        status, message_ids = mail.search(None, 'UNSEEN')

        if status != 'OK':
            logger.warning('Failed to search mailbox.')
            return

        ids = message_ids[0].split()

        if not ids:
            logger.info('No new (unseen) emails found.')
            return

        logger.info(f'Found {len(ids)} new email(s). Processing...')

        rows = []
        processed = 0
        errors = 0

        for msg_id in ids:
            try:
                # Fetch email
                status, msg_data = mail.fetch(msg_id, '(RFC822)')
                if status != 'OK':
                    logger.warning(f'Failed to fetch email ID {msg_id}')
                    errors += 1
                    continue

                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                # Extract sender email using parseaddr
                _, sender_email = parseaddr(msg.get('From', ''))
                if not sender_email:
                    sender_email = '(unknown)'

                # Extract subject using decode_header
                subject = decode_subject(msg.get('Subject'))

                # Extract body (multipart handling)
                body = extract_body(msg)

                # Timestamp
                fetched_at = datetime.now().isoformat()

                rows.append([sender_email, subject, body, fetched_at])
                processed += 1

                logger.info(f'  [{processed}] From: {sender_email} | Subject: {subject[:50]}')

                # Mark as SEEN (email is automatically marked as SEEN after FETCH with RFC822)
                # If needed explicitly: mail.store(msg_id, '+FLAGS', '\\Seen')

            except Exception as e:
                logger.error(f'Error processing email ID {msg_id}: {e}')
                errors += 1
                continue

        # ---- Save to CSV ----
        if rows:
            append_to_csv(rows)
            logger.info(f'Saved {processed} complaint(s) to {CSV_FILE}')

        if errors:
            logger.warning(f'{errors} email(s) had errors and were skipped.')

        logger.info('Done.')

    except imaplib.IMAP4.error as e:
        logger.error(f'IMAP error: {e}')
        logger.error('Check your EMAIL/PASSWORD. For Gmail, use an App Password.')
    except ConnectionError as e:
        logger.error(f'Connection failed: {e}')
    except Exception as e:
        logger.error(f'Unexpected error: {e}')
    finally:
        if mail:
            try:
                mail.close()
                mail.logout()
            except Exception:
                pass


# ---- Entry Point ----
if __name__ == '__main__':
    fetch_and_store_emails()
