import os
import base64
import smtplib
from io import BytesIO
from datetime import datetime
from flask import Flask, render_template, request, send_file
from email.message import EmailMessage
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

app = Flask(__name__)

ROLES = {
    "volunteer": ["volunteer_agreement.pdf", "nda.pdf", "media_release.pdf"],
    "donor": ["donor_agreement.pdf", "media_release.pdf", "privacy_policy.pdf"],
    "board_member": ["board_member_agreement.pdf", "conflict_policy.pdf", "expense_policy.pdf", "nda.pdf"],
    "minor_volunteer": ["volunteer_agreement.pdf", "media_release.pdf"],
    "sponsored_project": ["fiscal_sponsorship_agreement.pdf", "privacy_policy.pdf", "nda.pdf"]
}

PDF_DIR = "static/pdf_templates"

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", roles=ROLES.keys())

@app.route("/sign", methods=["POST"])
def sign_documents():
    role = request.form["role"]
    name = request.form["name"]
    email = request.form["email"]
    signature_data = request.form["signature"]
    date_str = datetime.now().strftime("%Y-%m-%d")

    # Decode the signature image from Base64
    if signature_data.startswith("data:image/png;base64,"):
        signature_data = signature_data.replace("data:image/png;base64,", "")
    signature_bytes = base64.b64decode(signature_data)

    combined_writer = PdfWriter()

    for doc_name in ROLES[role]:
        full_path = os.path.join(PDF_DIR, doc_name)
        reader = PdfReader(full_path)
        writer = PdfWriter()

        # Copy all pages except last one
        for i in range(len(reader.pages) - 1):
            writer.add_page(reader.pages[i])

        # Overlay signature info on last page
        last_page = reader.pages[-1]
        packet = BytesIO()
        c = canvas.Canvas(packet, pagesize=letter)
        c.drawString(72, 700, f"Full Name: {name}")
        c.drawImage(BytesIO(signature_bytes), 180, 665, width=150, height=40, mask='auto')
        c.drawString(72, 640, f"Date: {date_str}")
        c.save()
        packet.seek(0)

        overlay = PdfReader(packet)
        last_page.merge_page(overlay.pages[0])
        writer.add_page(last_page)

        for page in writer.pages:
            combined_writer.add_page(page)

    # Prepare the full output
    final_pdf = BytesIO()
    combined_writer.write(final_pdf)
    final_pdf.seek(0)

    # Email the signed PDF
    send_confirmation_email(name, email, final_pdf)

    final_pdf.seek(0)
    return send_file(final_pdf, as_attachment=True, download_name=f"signed_documents_{role}.pdf", mimetype="application/pdf")

def send_confirmation_email(name, recipient_email, pdf_data):
    msg = EmailMessage()
    msg["Subject"] = f"Signed Documents â Hilde B Foundation"
    msg["From"] = os.environ["EMAIL_ADDRESS"]
    msg["To"] = recipient_email
    msg["Cc"] = "contact@hildebfoundation.org"
    msg.set_content(f"Dear {name},\n\nThank you for signing. Your documents are attached.\n\nâ Hilde B Foundation")

    msg.add_attachment(pdf_data.read(), maintype="application", subtype="pdf", filename="signed_documents.pdf")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(os.environ["EMAIL_ADDRESS"], os.environ["EMAIL_PASSWORD"])
        smtp.send_message(msg)

if __name__ == "__main__":
    app.run(debug=True)
