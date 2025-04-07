from flask import Flask, render_template, request, send_file
import io, os
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from datetime import datetime
import base64
import tempfile

app = Flask(__name__)

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
    signature_data = request.form["signature"]
    date_str = datetime.today().strftime("%Y-%m-%d")

    # Decode the base64 PNG signature
    if signature_data.startswith("data:image/png;base64,"):
        signature_data = signature_data.replace("data:image/png;base64,", "")
    signature_bytes = base64.b64decode(signature_data)

    # Write the signature to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_sig:
        tmp_sig.write(signature_bytes)
        tmp_sig_path = tmp_sig.name

    packet = PdfWriter()

    for pdf_file in ROLE_DOCS.get(role, []):
        filepath = f"pdf_templates/{pdf_file}"
        reader = PdfReader(filepath)

        for page in reader.pages:
            # Create an overlay with the signature
            packet_buf = io.BytesIO()
            c = canvas.Canvas(packet_buf, pagesize=letter)
            c.drawImage(tmp_sig_path, 400, 50, width=150, height=50, mask='auto')
            c.drawString(400, 40, f"Signed by {name} on {date_str}")
            c.save()
            packet_buf.seek(0)

            overlay_reader = PdfReader(packet_buf)
            overlay_page = overlay_reader.pages[0]
            page.merge_page(overlay_page)
            packet.add_page(page)

    # Clean up the temp file
    os.unlink(tmp_sig_path)

    output = io.BytesIO()
    packet.write(output)
    output.seek(0)

    return send_file(output, as_attachment=True, download_name=f"signed_{role}_{name}.pdf", mimetype="application/pdf")

if __name__ == "__main__":
    app.run(debug=True)
