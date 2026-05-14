import os
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"

from flask import Flask, request, render_template_string
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import re

app = Flask(__name__)

HTML_FORM = """
<!DOCTYPE html>
<html>
<head>
  <title>Retrieve Household Code</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">

  <style>
    * { box-sizing: border-box; }

    body {
      margin: 0;
      font-family: Arial, sans-serif;
      background: #f4f7f6;
      color: #333;
      display: flex;
      justify-content: center;
      padding: 40px 20px;
    }

    .container {
      background: #fff;
      max-width: 500px;
      width: 100%;
      padding: 30px;
      border-radius: 12px;
      box-shadow: 0 8px 20px rgba(0,0,0,0.08);
    }

    h2 {
      text-align: center;
      color: #d94d47;
      margin-bottom: 25px;
    }

    label {
      font-weight: bold;
      display: block;
      margin-bottom: 8px;
    }

    input[type="email"] {
      width: 100%;
      padding: 12px;
      margin-bottom: 18px;
      border: 1px solid #ccc;
      border-radius: 6px;
      font-size: 16px;
    }

    button {
      width: 100%;
      background: #d94d47;
      color: white;
      padding: 13px;
      border: none;
      border-radius: 6px;
      font-size: 16px;
      font-weight: bold;
      cursor: pointer;
    }

    button:hover {
      background: #c9433e;
    }

    .code {
      margin-top: 25px;
      text-align: center;
      font-size: 42px;
      color: #2e7d32;
      font-weight: bold;
      letter-spacing: 8px;
    }

    .error {
      margin-top: 20px;
      text-align: center;
      color: #d32f2f;
      font-weight: bold;
      line-height: 1.5;
    }

    .email-info {
      margin-top: 18px;
      text-align: center;
      color: #555;
      font-style: italic;
    }

    #loading {
      display: none;
      text-align: center;
      margin-top: 18px;
      color: #555;
      font-weight: bold;
    }

    .instructions {
      margin-top: 25px;
      padding-top: 20px;
      border-top: 1px solid #ddd;
      font-size: 14px;
      line-height: 1.6;
    }
  </style>
</head>

<body>
  <div class="container">
    <h2>Retrieve Household Code</h2>

    <form method="POST" id="code-form">
      <label>Enter Outlook / Hotmail Email:</label>
      <input type="email" name="email" placeholder="example@hotmail.com" required>
      <button type="submit">Get Household Code</button>

      <div id="loading">
        Checking code, please wait...
      </div>
    </form>

    {% if email %}
      <div class="email-info">Entered email: {{ email }}</div>
    {% endif %}

    {% if code %}
      <div class="code">{{ code }}</div>
    {% elif error %}
      <div class="error">{{ error }}</div>
    {% endif %}

    <div class="instructions">
      <b>Instruction:</b>
      <ol>
        <li>Enter the Outlook / Hotmail email.</li>
        <li>Click Get Household Code.</li>
        <li>Please wait around 5–15 seconds.</li>
        <li>If no code is found, please check the email and request the code again.</li>
      </ol>
    </div>
  </div>

  <script>
    document.getElementById("code-form").addEventListener("submit", function () {
      document.getElementById("loading").style.display = "block";
    });
  </script>
</body>
</html>
"""


def get_household_code_from_site(user_email):
    try:
        with sync_playwright() as p:

            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled"
                ]
            )

            page = browser.new_page()

            # shorter timeout
            page.set_default_timeout(15000)

            page.goto("https://yz.naifei.store/#/login")

            # input email
            page.locator("input").fill(user_email)

            # click red button
            page.locator("button").first.click()

            page.wait_for_timeout(2000)

            text = page.locator("body").inner_text()

            # NO DATA
            if "尚未获取到邮箱验证码数据" in text:
                browser.close()
                return None, "No household code found. Please request the code first."

            # popup confirm button
            confirm_btn = page.locator("button:has-text('确定')")

            if confirm_btn.count() > 0:

                with page.expect_popup() as popup_info:
                    confirm_btn.click()

                popup = popup_info.value

                popup.wait_for_load_state()

                popup.wait_for_timeout(3000)

                full_text = popup.locator("body").inner_text()

                match = re.search(r"\b\d{4}\b", full_text)

                browser.close()

                if match:
                    return match.group(0), None

                return None, "Code not found on verification page."

            browser.close()

            return None, "Verification popup not found."

    except Exception as e:
        return None, f"System error: {str(e)}"


@app.route("/", methods=["GET", "POST"])
@app.route("/outlook-code", methods=["GET", "POST"])
def outlook_code():
    code = None
    error = None
    user_email = ""

    if request.method == "POST":
        user_email = request.form["email"].strip()
        code, error = get_household_code_from_site(user_email)

    return render_template_string(
        HTML_FORM,
        code=code,
        error=error,
        email=user_email
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
