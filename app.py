
import os
import smtplib
import random
import string
import io
from flask import Flask, render_template, request, send_file, jsonify
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader, PdfWriter
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from datetime import datetime
from PIL import Image
import base64

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'devkey')

EMAIL_ADDRESS = os.environ.get('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')

VERIFICATION_CODES = {}

ROLE_DOCUMENTS = {
    "volunteer": [
        "volunteer_agreement.pdf",
        "privacy_policy.pdf",
        "conflict_policy.pdf",
        "media_release.pdf"
    ],
    "donor": [
        "donor_agreement.pdf",
        "privacy_policy.pdf"
    ],
    "board_member": [
        "board_member_agreement.pdf",
        "conflict_policy.pdf",
        "privacy_policy.pdf",
        "media_release.pdf"
    ],
    "fiscal_partner": [
        "fiscal_sponsorship.pdf",
        "privacy_policy.pdf"
    ]
}

@app.route("/")
def index():
    return render_template("index.html", roles=ROLE_DOCUMENTS.keys())

@app.route("/send-code", methods=["POST"])
def send_code():
    email = request.form["email"]
    code = "".join(random.choices(string.digits, k=6))
    VERIFICATION_CODES[email] = {"code": code, "timestamp": datetime.now()}
    send_email(email, "Your Verification Code", f"Your code is: {code}")
    return "Code sent"

@app.route("/verify-code", methods=["POST"])
def verify_code():
    email = request.form["email"]
    entered_code = request.form["code"]
    if email in VERIFICATION_CODES:
        correct_code = VERIFICATION_CODES[email]["code"]
        if entered_code == correct_code:
            return "verified"
    return "invalid"

@app.route("/sign", methods=["POST"])
def sign_documents():
    name = request.form["name"]
    email = request.form["email"]
    role = request.form["role"]
    signature_data_url = request.form["signature"]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    signature_data = signature_data_url.split(",")[1]
    signature_bytes = base64.b64decode(signature_data)
    signature_image = Image.open(io.BytesIO(signature_bytes)).convert("RGB")

    signed_pdfs = []

    for filename in ROLE_DOCUMENTS[role]:
        template_path = f"pdf_templates/{filename}"
        if not os.path.exists(template_path):
            continue

        with open(template_path, "rb") as file:
            reader = PdfReader(file)
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            output = io.BytesIO()
            writer.write(output)
            output.seek(0)
            signed_pdfs.append((filename, output.read()))

    attachments = []
    for fname, content in signed_pdfs:
        attachments.append(("signed_" + fname, content))

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
