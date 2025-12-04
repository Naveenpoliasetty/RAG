from google.cloud import storage
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
import os


# ------------------------------------------------------------
# 1. CREATE RESUME (.docx)
# ------------------------------------------------------------

def create_resume(resume_data: dict) -> str:
    doc = Document()

    style = doc.styles['Normal']
    style.font.name = 'Times New Roman'
    style.font.size = Pt(10)

    def remove_table_borders(table):
        for row in table.rows:
            for cell in row.cells:
                tc = cell._tc
                tcPr = tc.get_or_add_tcPr()
                tcBorders = OxmlElement('w:tcBorders')
                for b in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
                    edge = OxmlElement(f'w:{b}')
                    edge.set(qn('w:val'), 'nil')
                    tcBorders.append(edge)
                tcPr.append(tcBorders)

    def add_bottom_border(paragraph):
        p = paragraph._p
        pPr = p.get_or_add_pPr()
        pBdr = OxmlElement('w:pBdr')
        bottom = OxmlElement('w:bottom')
        bottom.set(qn('w:val'), 'single')
        bottom.set(qn('w:sz'), '4')
        bottom.set(qn('w:space'), '1')
        bottom.set(qn('w:color'), 'auto')
        pBdr.append(bottom)
        pPr.append(pBdr)

    def add_section_header(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(3)
        run = p.add_run(text.upper())
        run.bold = True
        run.font.size = Pt(11)
        add_bottom_border(p)

    def add_bullet_point(text):
        p = doc.add_paragraph(text, style='List Bullet')
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1.0

    def add_experience_block(client, dates, role, bullets, environment=None):
        table = doc.add_table(rows=1, cols=2)
        table.autofit = False
        remove_table_borders(table)

        cell1 = table.rows[0].cells[0]
        cell1.paragraphs[0].add_run(client).bold = True

        cell2 = table.rows[0].cells[1]
        p2 = cell2.paragraphs[0]
        p2.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        p2.add_run(dates).bold = True

        p_role = doc.add_paragraph()
        r_role = p_role.add_run(f"Role: {role}")
        r_role.italic = True

        for bullet in bullets:
            add_bullet_point(bullet)

        if environment:
            p_env = doc.add_paragraph()
            p_env.add_run("Environment: ").bold = True
            p_env.add_run(environment)

    # ---------- HEADER ----------
    header = doc.add_paragraph()
    header.alignment = WD_ALIGN_PARAGRAPH.CENTER
    name = header.add_run(resume_data["name"] + "\n")
    name.bold = True
    name.font.size = Pt(18)

    contact = doc.add_table(rows=1, cols=2)
    remove_table_borders(contact)
    contact.rows[0].cells[0].add_paragraph(f"Email: {resume_data['email']}")
    c2 = contact.rows[0].cells[1]
    p2 = c2.paragraphs[0]
    p2.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p2.add_run(f"Phone: {resume_data['phone_number']}")

    # ---------- SUMMARY ----------
    add_section_header("Professional Summary")
    for point in resume_data["professional_summary"]:
        add_bullet_point(point)

    # ---------- SKILLS ----------
    add_section_header("Technical Skills")
    skills_table = doc.add_table(rows=0, cols=2)
    remove_table_borders(skills_table)

    for category, values in resume_data["technical_skills"].items():
        row = skills_table.add_row()
        cell1 = row.cells[0]
        r = cell1.paragraphs[0].add_run(category + ":")
        r.bold = True

        row.cells[1].paragraphs[0].add_run(", ".join(values))

    # ---------- EXPERIENCE ----------
    add_section_header("Professional Experience")
    for exp in resume_data["experiences"]:
        add_experience_block(
            exp["client_name"],
            exp["duration"],
            exp["job_role"],
            exp["responsibilities"],
            exp.get("environment")
        )

    # ---------- SAVE ----------
    filename = f"{resume_data['name'].replace(' ', '_')}_Resume.docx"
    doc.save(filename)
    print(f"Saved locally as: {filename}")

    return filename



# ------------------------------------------------------------
# 2. UPLOAD FILE TO GOOGLE CLOUD STORAGE
# ------------------------------------------------------------

def upload_to_gcs(bucket_name: str, file_path: str, destination_blob_name: str):
    storage_client = storage.Client.from_service_account_json("/Users/naveenpoliasetty/Downloads/RAG-1/src/resume-477618-0c64e84c6bb0.json")
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(file_path)

    print(f"Uploaded to: gs://{bucket_name}/{destination_blob_name}")
    return f"gs://{bucket_name}/{destination_blob_name}"



# ------------------------------------------------------------
# 3. MASTER FUNCTION (CREATE + UPLOAD)
# ------------------------------------------------------------

def generate_and_upload_resume(resume_data):
    local_file = create_resume(resume_data)

    gcs_path = upload_to_gcs(
        bucket_name="resume-ai-bucket",
        file_path=local_file,
        destination_blob_name=os.path.basename(local_file)
    )

    return {
        "local_file": local_file,
        "gcs_url": gcs_path
    }