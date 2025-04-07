import os
import random
import smtplib
import ssl
from datetime import datetime, timedelta
from flask import Flask, request, render_template, send_file, jsonify, session
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from io import BytesIO
import base64

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "defaultsecretkey")

EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")

VERIFICATION_CODES = {}

ROLES = {
    "volunteer": ["volunteer_agreement.pdf", "media_release.pdf", "nda.pdf"],
    "donor": ["donor_agreement.pdf", "privacy_policy.pdf", "conflict_policy.pdf"],
    "board_member": ["board_member_agreement.pdf", "conflict_policy.pdf", "nda.pdf", "expense_policy.pdf"]
}

PDF_DIR = "static/pdf_templates"

@app.route("/")
def index():
    return render_template("index.html", roles=ROLES.keys())

@app.route("/send-code", methods=["POST"])
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

@app.route("/verify-code", methods=["POST"])
def verify_code():
    email = request.json.get("email")
    code = request.json.get("code")

    data = VERIFICATION_CODES.get(email)
    if not data:
        return jsonify({"success": False})

    if datetime.utcnow() > data["expires_at"]:
        return jsonify({"success": False})

    if code != data["code"]:
        return jsonify({"success": False})

    session["verified_email"] = email
    return jsonify({"success": True})

@app.route("/sign", methods=["POST"])
def sign_documents():
    role = request.form["role"]
    name = request.form["name"]
    email = request.form["email"]
    signature_data = request.form["signature"]

    if session.get("verified_email") != email:
        return "Email not verified.", 403

    if signature_data.startswith("data:image/png;base64,"):
        signature_data = signature_data.replace("data:image/png;base64,", "")
    signature_bytes = base64.b64decode(signature_data)
    date_str = datetime.now().strftime("%Y-%m-%d")

    output_dir = f"signed_output/{email.replace('@','_')}_{datetime.now().timestamp()}"
    os.makedirs(output_dir, exist_ok=True)

    signed_pdfs = []

    for doc_name in ROLES[role]:
        input_path = os.path.join(PDF_DIR, doc_name)
        output_path = os.path.join(output_dir, f"signed_{doc_name}")
        signed_pdfs.append(output_path)

        reader = PdfReader(input_path)
        writer = PdfWriter()

        for i, page in enumerate(reader.pages):
            packet = BytesIO()
            c = canvas.Canvas(packet, pagesize=letter)
            c.drawString(72, 40, f"Signed by: {name}")
            c.drawString(72, 25, f"Date: {date_str}")
            c.drawImage(BytesIO(signature_bytes), 400, 20, width=150, height=50)
            c.save()
            packet.seek(0)
            overlay = PdfReader(packet)
            page.merge_page(overlay.pages[0])
            writer.add_page(page)

        with open(output_path, "wb") as f:
            writer.write(f)

    send_signed_pdfs(email, name, signed_pdfs)

    return "Documents signed and sent successfully."

def send_signed_pdfs(to_email, name, filepaths):
    msg = MIMEMultipart()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_email
    msg["Cc"] = "contact@hildebfoundation.org"
    msg["Subject"] = "Signed Documents â Hilde B Foundation"
    msg.attach(MIMEText(f"Dear {name},\n\nAttached are your signed documents.\n\nâ Hilde B Foundation", "plain"))

    for filepath in filepaths:
        with open(filepath, "rb") as f:
            part = MIMEText(f.read(), "base64", "utf-8")
            part.add_header("Content-Disposition", "attachment", filename=os.path.basename(filepath))
            part.add_header("Content-Transfer-Encoding", "base64")
            part.set_payload(base64.b64encode(f.read()).decode())
            msg.attach(part)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, [to_email, "contact@hildebfoundation.org"], msg.as_string())
