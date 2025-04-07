import os
from flask import Flask, render_template, request, send_file
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import LETTER
import smtplib
from email.message import EmailMessage

app = Flask(__name__)

ROLES = {
    "volunteer": ["volunteer_agreement", "media_release", "nda"],
    "donor": ["donor_agreement", "privacy_policy", "conflict_policy"],
    "board_member": ["board_member_agreement", "nda", "conflict_policy"],
}

PDF_DIR = "pdf_templates"

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", roles=ROLES.keys())

@app.route("/sign", methods=["POST"])
def sign_documents():
    role = request.form["role"]
    name = request.form["name"]
    email = request.form["email"]
    signature = request.form["signature"]

    pdf_output = BytesIO()
    pdf = canvas.Canvas(pdf_output, pagesize=LETTER)

    for doc in ROLES[role]:
        path = os.path.join(PDF_DIR, f"{doc}.pdf")
        if os.path.exists(path):
            pdf.showPage()
            pdf.setFont("Helvetica", 12)
            pdf.drawString(50, 700, f"Signed by: {name}")
            pdf.drawString(50, 685, f"Signature: {signature}")
            pdf.drawString(50, 670, f"Document: {doc.replace('_', ' ').title()}")

    pdf.showPage()
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, 700, f"Confirmation of Signature for Role: {role.title()}")
    pdf.drawString(50, 685, f"Name: {name}")
    pdf.drawString(50, 670, f"Email: {email}")
    pdf.drawString(50, 655, f"Signature: {signature}")
    pdf.save()

    pdf_output.seek(0)
    send_confirmation_email(name, email, pdf_output)

    return "Your documents were signed and emailed successfully!"

def send_confirmation_email(name, recipient_email, pdf_data):
    msg = EmailMessage()
    msg["Subject"] = f"Signed Documents - Hilde B Foundation"
    msg["From"] = os.environ["EMAIL_ADDRESS"]
    msg["To"] = recipient_email
    msg["Cc"] = "contact@hildebfoundation.org"
    msg.set_content(f"Dear {name},\n\nAttached are your signed documents.\n\nSincerely,\nThe Hilde B Foundation")

    msg.add_attachment(pdf_data.read(), maintype="application", subtype="pdf", filename="signed_documents.pdf")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(os.environ["EMAIL_ADDRESS"], os.environ["EMAIL_PASSWORD"])
        smtp.send_message(msg)
