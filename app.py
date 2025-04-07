from flask import Flask, render_template, request, send_file
import io
from PyPDF2 import PdfReader, PdfWriter
from datetime import datetime

app = Flask(__name__)

# Define role-document mapping
ROLE_DOCS = {
    "volunteer": ["volunteer_agreement.pdf", "privacy_policy.pdf", "nda.pdf"],
    "donor": ["donor_agreement.pdf", "privacy_policy.pdf", "media_release.pdf"],
    "board": ["board_member_agreement.pdf", "conflict_policy.pdf", "expense_policy.pdf", "nda.pdf"],
    "minor_volunteer": ["volunteer_agreement.pdf", "media_release.pdf"],
    "sponsored_project": ["fiscal_sponsorship.pdf", "privacy_policy.pdf", "nda.pdf"]
}

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", roles=list(ROLE_DOCS.keys()))

@app.route("/sign", methods=["POST"])
def sign():
    role = request.form["role"]
    name = request.form["name"]
    signature = request.form["signature"]  # Base64 or typed string
    date_str = datetime.today().strftime("%Y-%m-%d")

    packet = PdfWriter()

    for pdf_file in ROLE_DOCS.get(role, []):
        filepath = f"pdf_templates/{pdf_file}"
        reader = PdfReader(filepath)
        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        for page in writer.pages:
            packet.add_page(page)

    output = io.BytesIO()
    packet.write(output)
    output.seek(0)

    return send_file(output, as_attachment=True, download_name=f"signed_{role}_{name}.pdf", mimetype="application/pdf")

if __name__ == "__main__":
    app.run(debug=True)
