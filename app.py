import os
import random
import smtplib
import ssl
from datetime import datetime, timedelta
from flask import Flask, request, render_template, send_from_directory, jsonify, session
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "defaultsecretkey")

# Load email credentials from environment variables
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")

# Email verification state
VERIFICATION_CODES = {}

@app.route("/")
def index():
    roles = {
        "volunteer": ["volunteer_agreement", "media_release", "privacy_policy"],
        "donor": ["donor_agreement", "nda", "privacy_policy"],
        "board_member": ["board_member_agreement", "conflict_policy", "nda", "privacy_policy"],
        "partner": ["fiscal_sponsorship", "mou", "nda", "privacy_policy"],
    }
    return render_template("index.html", roles=roles.keys())

@app.route("/send_code", methods=["POST"])
def send_code():
    email = request.json.get("email")
    code = "{:06}".format(random.randint(0, 999999))
    VERIFICATION_CODES[email] = {
        "code": code,
        "expires_at": datetime.utcnow() + timedelta(minutes=5)
    }

    msg = MIMEMultipart()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = email
    msg["Subject"] = "Your Verification Code - Hilde B Foundation"

    msg.attach(MIMEText(f"Your verification code is: {code}. It is valid for 5 minutes.", "plain"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, email, msg.as_string())

    return jsonify({"status": "success"})

@app.route("/verify_code", methods=["POST"])
def verify_code():
    email = request.json.get("email")
    code = request.json.get("code")

    data = VERIFICATION_CODES.get(email)
    if not data:
        return jsonify({"status": "fail", "message": "Code not found."}), 400

    if datetime.utcnow() > data["expires_at"]:
        return jsonify({"status": "fail", "message": "Code expired."}), 400

    if code != data["code"]:
        return jsonify({"status": "fail", "message": "Incorrect code."}), 400

    session["verified_email"] = email
    return jsonify({"status": "success"})

@app.route("/static/pdf_templates/<path:filename>")
def serve_pdf(filename):
    return send_from_directory("pdf_templates", filename)
