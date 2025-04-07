import os
import io
import random
import time
import smtplib
from flask import Flask, render_template, request, send_file, jsonify
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader, PdfWriter
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from PIL import Image
import base64

app = Flask(__name__)

EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")

roles_to_pdfs = {
    "volunteer": ["volunteer_agreement.pdf", "privacy_policy.pdf", "conflict_policy.pdf"],
    "donor": ["donor_agreement.pdf", "privacy_policy.pdf", "nda.pdf"],
    "board_member": ["board_member_agreement.pdf", "privacy_policy.pdf", "conflict_policy.pdf", "nda.pdf"],
    "media_contributor": ["media_release.pdf", "privacy_policy.pdf", "nda.pdf"],
    "fiscal_sponsor": ["fiscal_sponsorship.pdf", "privacy_policy.pdf"],
    "partner": ["mou.pdf", "privacy_policy.pdf"],
}

verification_codes = {}

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", roles=roles_to_pdfs.keys())

@app.route("/send_code", methods=["POST"])
def send_code():
    data = request.json
    email = data.get("email")
    if not email:
        return jsonify({"success": False, "error": "Missing email"}), 400

    code = str(random.randint(100000, 999999))
    verification_codes[email] = {"code": code, "timestamp": time.time()}

    send_email(
        to=email,
        subject="Your Hilde B Foundation Verification Code",
        body=f"Your verification code is: {code}\n\nThis code is valid for 5 minutes."
    )

    return jsonify({"success": True})

@app.route("/verify_code", methods=["POST"])
def verify_code():
    data = request.json
    email = data.get("email")
    code = data.get("code")

    if email not in verification_codes:
        return jsonify({"success": False, "error": "No code requested for this email"}), 400

    entry = verification_codes[email]
    if time.time() - entry["timestamp"] > 300:
        return jsonify({"success": False, "error": "Code expired"}), 400

    if entry["code"] != code:
        return jsonify({"success": False, "error": "Incorrect code"}), 400

    return jsonify({"success": True})

@app.route("/sign", methods=["POST"])
def sign():
    name = request.form["name"]
    email = request.form["email"]
    role = request.form["role"]
    signature_data = request.form["signature"]

    signature_image = Image.open(io.BytesIO(base64.b64decode(signature_data.split(",")[1])))
    signature_path = "/tmp/signature.png"
    signature_image.save(signature_path)

    signed_pdfs = []
    for pdf_file in roles_to_pdfs.get(role, []):
        pdf_path = f"pdf_templates/{pdf_file}"
        output = io.BytesIO()
        reader = PdfReader(pdf_path)
        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        writer.add_metadata(reader.metadata)
        writer.write(output)
        signed_pdfs.append((pdf_file, output.getvalue()))

    attachments = [("signed_" + fname, content) for fname, content in signed_pdfs]

    send_email(
        to=email,
        subject="Your Signed Documents",
        body="Attached are your signed documents for the Hilde B Foundation.",
        attachments=attachments
    )

    send_email(
        to=EMAIL_ADDRESS,
        subject=f"New Signing Submitted: {name}",
        body=f"{name} ({email}) signed the following as {role}: {[x[0] for x in attachments]}",
        attachments=attachments
    )

    return "Documents signed and emailed!"

def send_email(to, subject, body, attachments=None):
    msg = MIMEMultipart()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    attachments = attachments or []
    for filename, filecontent in attachments:
        part = MIMEApplication(filecontent, Name=filename)
        part["Content-Disposition"] = f'attachment; filename="{filename}"'
        msg.attach(part)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)

if __name__ == "__main__":
    app.run(debug=True)
