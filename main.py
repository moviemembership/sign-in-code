from flask import Flask, request, render_template_string, redirect
from datetime import datetime, timedelta, timezone
import imaplib
import email
import re
import os

app = Flask(__name__)

IMAP_HOST = "mail.mantapnet.com"
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL")
ADMIN_PASS = os.environ.get("ADMIN_PASS")

HTML_FORM = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Redeem Access Code</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0;
      padding: 0;
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      background-color: #f4f7f6;
      color: #333;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 40px 20px;
    }
    .container {
      background: #ffffff;
      max-width: 500px;
      width: 100%;
      padding: 30px 40px;
      border-radius: 12px;
      box-shadow: 0 8px 20px rgba(0,0,0,0.08);
    }
    h2 {
      text-align: center;
      color: #4CAF50;
      margin-bottom: 20px;
    }
    label {
      font-weight: bold;
      display: block;
      margin-bottom: 6px;
    }
    input[type="email"] {
      width: 100%;
      padding: 12px;
      margin-bottom: 20px;
      border: 1px solid #ccc;
      border-radius: 6px;
      font-size: 16px;
    }
    input[type="submit"] {
      background-color: #4CAF50;
      color: white;
      padding: 12px 20px;
      font-size: 16px;
      border: none;
      border-radius: 6px;
      cursor: pointer;
      width: 100%;
      transition: background-color 0.3s ease;
    }
    input[type="submit"]:hover {
      background-color: #43a047;
    }
    .code-display {
      font-size: 30px;
      color: #2e7d32;
      text-align: center;
      margin-top: 20px;
      font-weight: bold;
    }
    .error {
      color: #d32f2f;
      text-align: center;
      margin-top: 20px;
      font-weight: bold;
    }
    .email-info {
      text-align: center;
      margin-top: 10px;
      font-style: italic;
      color: #555;
    }
    .instructions {
      margin-top: 50px;
      max-width: 900px;
      background: #ffffff;
      padding: 25px;
      border-radius: 10px;
      box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
    }
    .instructions h3 {
      color: #388e3c;
      margin-top: 0;
    }
    .instructions ol {
      padding-left: 20px;
    }
    .instructions li {
      margin-bottom: 10px;
    }
    .instructions img {
      max-width: 100%;
      border-radius: 10px;
      margin: 10px 0;
    }
    #loading {
      display: none;
      text-align: center;
      margin-top: 20px;
    }
    #loading img {
      width: 40px;
    }
  </style>
</head>
<body>

  <div class="container">
    <h2>Redeem Your Access Code</h2>
    <form method="POST" id="redeem-form">
      <label for="email">Enter your @mantapnet.com email:</label>
      <input type="email" name="email" placeholder="contoh@mantapnet.com" required>
      <input type="submit" value="Get Code">

      <div id="loading">
        <img src="/loading.gif" alt="Loading...">
        <p>Checking for your code...</p>
      </div>
    </form>

    {% if email %}
      <div class="email-info">Entered email: {{ email }}</div>
    {% endif %}
    {% if code %}
      <div class="code-display">{{ code }}</div>
    {% elif error %}
      <div class="error">{{ error }}</div>
    {% endif %}
  </div>

  <div class="instructions">
    <h3>How To Use:</h3>
    <video controls width="600">
      <source src="https://github.com/moviemembership/sign-in-code/raw/37911e20063a9614b02e63b8dee780ea08882b44/SIGNINCODE.mp4" type="video/mp4">
      Your browser does not support the video tag.
    </video>
    <ol>
    <li>Click Send Sign in Code on Netflix</li>
    <li>Redeem Code Here</li>
    </ol>
  </div>

  <script>
    document.getElementById("redeem-form").addEventListener("submit", function () {
      document.getElementById("loading").style.display = "block";
    });
  </script>

</body>
</html>
"""

def extract_email_body(msg):
    try:
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() in ["text/plain", "text/html"]:
                    payload = part.get_payload(decode=True)
                    return payload.decode(errors="ignore") if isinstance(payload, bytes) else str(payload)
        else:
            payload = msg.get_payload(decode=True)
            return payload.decode(errors="ignore") if isinstance(payload, bytes) else str(payload)
    except Exception:
        return ""

def safe_search(mail, criteria):
  status, data = mail.search(None, criteria)
  if status == "OK":
      # Ensure data[0] is bytes before splitting
      return data[0].split() if isinstance(data[0], bytes) else []
  else:
      return []

@app.route("/", methods=["GET", "POST"])
def redeem():
    code = None
    error = None
    original_email = ""

    if request.method == "POST":
        original_email = request.form["email"].strip()
        try:
            mail = imaplib.IMAP4_SSL(IMAP_HOST)
            mail.login(ADMIN_EMAIL, ADMIN_PASS)
            mail.select("inbox")

            # Search: last 1 day + subjects
            since_1day = (datetime.utcnow() - timedelta(days=1)).strftime("%d-%b-%Y")
            search_criteria = f'(SINCE {since_1day} OR (SUBJECT "Your sign-in code") (SUBJECT "Kod daftar masuk anda"))'
            status, data = mail.uid("search", None, search_criteria)
            if status != "OK" or not data or not data[0]:
                error = "No recent sign-in email found."
                return render_template_string(HTML_FORM, code=code, error=error, email=original_email)

            uids = data[0].split()

            # Prepare UTC-aware cutoff time
            now_utc = datetime.now(timezone.utc)
            time_limit_utc = now_utc - timedelta(minutes=15)

            # Check only newest ~30 messages
            for uid in reversed(uids[-30:]):
                # Fetch headers only
                status, hdr_data = mail.uid("fetch", uid, '(BODY.PEEK[HEADER.FIELDS (DATE SUBJECT TO FROM)])')
                if status != "OK" or not hdr_data or not hdr_data[0]:
                    continue

                msg_hdr = email.message_from_bytes(hdr_data[0][1])

                # --- UTC-aware date parsing ---
                date_str = msg_hdr.get("Date")
                date_tuple = email.utils.parsedate_tz(date_str)
                if not date_tuple:
                    continue  # skip if no valid date

                sent_ts = email.utils.mktime_tz(date_tuple)  # UTC timestamp
                sent_dt_utc = datetime.fromtimestamp(sent_ts, tz=timezone.utc)

                # If older than 15 min, stop loop (fast exit)
                if sent_dt_utc < time_limit_utc:
                    break

                # Fetch full body only for recent messages
                status, body_data = mail.uid("fetch", uid, "(BODY.PEEK[])")
                if status != "OK" or not body_data or not body_data[0]:
                    continue

                body = extract_email_body(email.message_from_bytes(body_data[0][1]))
                if original_email.lower() in body.lower():
                    match = re.search(r"\b\d{4}\b", body)
                    if match:
                        code = match.group(0)
                        break

            if not code:
                error = "No recent sign-in email found for this address. Make sure you request it and try again within 15 minutes."

            mail.logout()

        except Exception as e:
            error = f"Error: {str(e)}"

    return render_template_string(HTML_FORM, code=code, error=error, email=original_email if request.method == "POST" else "")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
