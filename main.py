from flask import Flask, request, render_template_string, redirect
from datetime import datetime, timedelta
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

    if request.method == "POST":
        user_email = request.form["email"].strip().lower()

        try:
            mail = imaplib.IMAP4_SSL(IMAP_HOST)
            mail.login(ADMIN_EMAIL, ADMIN_PASS)
            mail.select("inbox")

            since_date = (datetime.now() - timedelta(days=1)).strftime("%d-%b-%Y")
          
            # Search both subjects
            message_ids1 = safe_search(mail, f'(SINCE {since_date} SUBJECT "Your sign-in code")')
            message_ids2 = safe_search(mail, f'(SINCE {since_date} SUBJECT "Kod daftar masuk anda")')
  
            # Combine both message ID lists
            message_ids = message_ids1 + message_ids2

            matched = False

            for msg_id in reversed(message_ids):
                status, msg_data = mail.fetch(msg_id, "(RFC822)")
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                # Check if email is within last 15 minutes
                date_tuple = email.utils.parsedate_tz(msg["Date"])
                if date_tuple:
                    email_time = datetime.fromtimestamp(email.utils.mktime_tz(date_tuple))
                    if datetime.now() - email_time > timedelta(minutes=15):
                        continue

                # Check body for user's email and 4-digit code
                body = extract_email_body(msg)
                if user_email in body:
                    match = re.search(r'\b\d{4}\b', body)
                    if match:
                        code = match.group(0)
                        matched = True
                        break

            if not matched:
                error = "No recent sign-in email found for this address. Make sure you request it and try again within 15 minutes."

            mail.logout()

        except Exception as e:
            error = f"Error: {str(e)}"

    return render_template_string(HTML_FORM, code=code, error=error, email=user_email if request.method == "POST" else "")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
