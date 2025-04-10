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

app = Flask(__name__, template_folder="templates", static_folder="static")

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
    data = request.get_json()
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
    import io
    from datetime import datetime
    from PyPDF2 import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from PIL import Image
    import base64
    import os
    import tempfile

    name = request.form["name"]
    email = request.form["email"]
    role = request.form["role"]
    signature_data = request.form["signature"]

    # Decode and flatten user's signature
    original = Image.open(io.BytesIO(base64.b64decode(signature_data.split(",")[1])))
    signature_image = Image.new("RGB", original.size, (255, 255, 255))
    signature_image.paste(original, mask=original.split()[3] if original.mode == "RGBA" else None)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_sig_file:
        tmp_sig_path = tmp_sig_file.name
        signature_image.save(tmp_sig_path)

    # Load foundation signature
    from PIL import Image
    foundation_sig_raw = Image.open("static/foundation_signature/signature.png")
    foundation_sig = Image.new("RGB", foundation_sig_raw.size, (255, 255, 255))
    foundation_sig.paste(foundation_sig_raw, mask=foundation_sig_raw.split()[3] if foundation_sig_raw.mode == "RGBA" else None)

    import tempfile
    foundation_sig_path = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
    foundation_sig.save(foundation_sig_path)
    date_str = datetime.now().strftime("%Y-%m-%d")
    signed_pdfs = []

    for filename in roles_to_pdfs.get(role, []):
        pdf_path = os.path.join("static/pdf_templates", filename)
        reader = PdfReader(pdf_path)
        writer = PdfWriter()

        for i, page in enumerate(reader.pages):
            packet = io.BytesIO()
            c = canvas.Canvas(packet, pagesize=letter)

            # Left side: foundation signature
            c.drawString(72, 90, "Signed on behalf of the Hilde B Foundation")
            c.drawImage(foundation_sig_path, 72, 95, width=150, height=50)

            # Right side: user signature
            c.drawString(400, 90, f"Signed by: {name}")
            c.drawString(400, 75, f"Date: {date_str}")
            c.drawImage(tmp_sig_path, 400, 95, width=150, height=50)

            c.save()
            packet.seek(0)
            overlay_pdf = PdfReader(packet)
            page.merge_page(overlay_pdf.pages[0])
            writer.add_page(page)

        output = io.BytesIO()
        writer.write(output)
        output.seek(0)
        signed_pdfs.append((f"signed_{filename}", output.read()))

    send_email(
        to=email,
        subject="Your Signed Documents",
        body="Attached are your signed documents for the Hilde B Foundation.",
        attachments=signed_pdfs
    )
    send_email(
        to=EMAIL_ADDRESS,
        subject=f"New Signing Submitted: {name}",
        body=f"{name} ({email}) signed as {role}.",
        attachments=signed_pdfs
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
