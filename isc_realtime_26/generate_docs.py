import os
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

# ==========================================
# 1. WORD DOCUMENT GENERATION (.docx)
# ==========================================
def set_cell_background(cell, fill_hex):
    tcPr = cell._element.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    tcPr = cell._element.get_or_add_tcPr()
    tcMar = parse_xml(f'<w:tcMar {nsdecls("w")}><w:top w:w="{top}" w:type="dxa"/><w:bottom w:w="{bottom}" w:type="dxa"/><w:left w:w="{left}" w:type="dxa"/><w:right w:w="{right}" w:type="dxa"/></w:tcMar>')
    tcPr.append(tcMar)

def create_word_doc(filename):
    doc = Document()
    
    # Page setup
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    # Styles
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Calibri'
    normal_style.font.size = Pt(10.5)
    normal_style.font.color.rgb = RGBColor(0x22, 0x22, 0x22)

    # Title
    p_title = doc.add_paragraph()
    p_title.paragraph_format.space_before = Pt(0)
    p_title.paragraph_format.space_after = Pt(4)
    run_title = p_title.add_run("ISC Telemetry Operational Guide")
    run_title.font.size = Pt(22)
    run_title.font.bold = True
    run_title.font.color.rgb = RGBColor(0x0E, 0x5C, 0x2F) # Racing Green

    p_sub = doc.add_paragraph()
    p_sub.paragraph_format.space_after = Pt(14)
    run_sub = p_sub.add_run("Hardware Setup, ISCmetrics Suite & Marple Cloud Data Platform")
    run_sub.font.size = Pt(12)
    run_sub.font.italic = True
    run_sub.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

    # Helper function for headings
    def add_h1(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(16)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.size = Pt(14)
        run.font.bold = True
        run.font.color.rgb = RGBColor(0x0E, 0x5C, 0x2F)
        return p

    def add_h2(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.size = Pt(12)
        run.font.bold = True
        run.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)
        return p

    def add_callout(title, text, bg_hex="E8F5E9", border_hex="0E5C2F"):
        tbl = doc.add_table(rows=1, cols=1)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = tbl.cell(0, 0)
        set_cell_background(cell, bg_hex)
        set_cell_margins(cell, top=140, bottom=140, left=200, right=200)
        
        tcPr = cell._element.get_or_add_tcPr()
        borders = parse_xml(f'<w:tcBorders {nsdecls("w")}><w:left w:val="single" w:sz="24" w:space="0" w:color="{border_hex}"/><w:top w:val="none"/><w:right w:val="none"/><w:bottom w:val="none"/></w:tcBorders>')
        tcPr.append(borders)

        cp = cell.paragraphs[0]
        cp.paragraph_format.space_before = Pt(2)
        cp.paragraph_format.space_after = Pt(2)
        r_title = cp.add_run(f"★ {title}\n")
        r_title.bold = True
        r_title.font.color.rgb = RGBColor(0x0E, 0x5C, 0x2F)
        r_text = cp.add_run(text)
        r_text.font.size = Pt(10)
        doc.add_paragraph().paragraph_format.space_after = Pt(4)

    def add_code_block(code_text):
        tbl = doc.add_table(rows=1, cols=1)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = tbl.cell(0, 0)
        set_cell_background(cell, "F3F4F6")
        set_cell_margins(cell, top=100, bottom=100, left=150, right=150)
        cp = cell.paragraphs[0]
        cp.paragraph_format.space_before = Pt(2)
        cp.paragraph_format.space_after = Pt(2)
        r = cp.add_run(code_text)
        r.font.name = 'Consolas'
        r.font.size = Pt(9.5)
        r.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)
        doc.add_paragraph().paragraph_format.space_after = Pt(4)

    # 1. PHYSICAL SETUP
    add_h1("1. Physical Hardware Setup")
    
    add_h2("1.1 Car Side (Transmitter / ECU)")
    p = doc.add_paragraph()
    p.add_run("• Antenna Positioning: ").bold = True
    p.add_run("Mount vertically on the roll hoop or shark fin with an insulating spacer. Maintain at least 3.5 cm (λ/4) clearance from carbon fiber panels to avoid signal absorption.\n")
    p.add_run("• RF Cabling: ").bold = True
    p.add_run("Use low-loss RG-316 or RG-142 coaxial cable with SMA connectors (< 50 cm). Route away from high-voltage (HV) lines and inverter phase cables.\n")
    p.add_run("• Decoupling Capacitor: ").bold = True
    p.add_run("High-power PA modules (e.g. E01-ML01DP5) draw up to 150 mA peak during transmit bursts. Solder a 10–100 µF electrolytic in parallel with a 100 nF ceramic capacitor directly across the module's VCC (3.3V) and GND pins.")

    add_h2("1.2 Pitwall Side (USB Receiver Ground Station)")
    p = doc.add_paragraph()
    p.add_run("• Hardware: ").bold = True
    p.add_run("Arduino Nano / USB dongle connected to nRF24L01+ + PA/LNA module over SPI, communicating via USB-Serial at 115200 baud.\n")
    p.add_run("• Mast Elevation: ").bold = True
    p.add_run("Mount the high-gain antenna (+9 to +14 dBi) on a tripod mast 2.5 m to 3.5 m above ground to ensure line-of-sight and clear the first Fresnel zone above barriers and team personnel.")

    # 2. ISCMETRICS
    add_h1("2. Installing & Running ISCmetrics")
    p = doc.add_paragraph()
    p.add_run("ISCmetrics is the official Formula Student telemetry desktop application developed for real-time monitoring, state machine diagnostics, and CSV logging.\n")
    p.add_run("• GitHub Repository: ").bold = True
    p.add_run("https://github.com/MrAndy5/ISCmetrics\n")
    p.add_run("• Latest Releases (Executable): ").bold = True
    p.add_run("https://github.com/MrAndy5/ISCmetrics/releases/latest")

    add_h2("2.1 Installation from Source")
    add_code_block(
        "git clone https://github.com/MrAndy5/ISCmetrics.git\n"
        "cd ISCmetrics\n"
        "python -m venv venv\n"
        ".\\venv\\Scripts\\Activate.ps1\n"
        "pip install PyQt5 matplotlib pyserial numpy pandas marple requests python-can\n"
        "python ui.py"
    )

    add_h2("2.2 Cloud Upload Authentication")
    add_callout(
        "MARPLE CLOUD UPLOAD PASSWORD",
        "To enable cloud uploads in the Settings dialog, enter the password:\n"
        "Password: ISC_telemetry_2026\n\n"
        "Steps: Settings (Gear Icon) -> Check 'Upload to Marple Data (cloud)' -> Enter password -> Save.",
        bg_hex="FFF8E1",
        border_hex="FFA000"
    )

    add_h2("2.3 Live Session Workflow")
    p = doc.add_paragraph()
    p.add_run("1. Select the Serial COM Port for the receiver dongle in the top bar.\n")
    p.add_run("2. Click CONNECT to begin live streaming (Inverter FSM, DC Bus, AMS module voltages & temps, APPS pedals, Brake pressure, Link health).\n")
    p.add_run("3. Click DISCONNECT when the run completes. The session CSV is saved under logs/ and automatically uploaded to Marple in the background.")

    # 3. MARPLE DATA
    add_h1("3. Marple Data: Cloud Uploads & Analysis")
    p = doc.add_paragraph()
    p.add_run("• Default API Token: ").bold = True
    p.add_run("mdb_Le69BDaNdgn1SJ4DqWX6N6btH-a8Dx8Ou96aBbLA4v8\n")
    p.add_run("• Destination Stream: ").bold = True
    p.add_run("ISC_Telemetry\n")
    p.add_run("• Local Override: ").bold = True
    p.add_run("Place MARPLE_API_TOKEN=your_token in a .env file in the workspace.")

    add_h2("3.1 Post-Race Data Fusion (SD Card Merge)")
    p = doc.add_paragraph()
    p.add_run("1. Open Tools -> Post-Race Analysis in ISCmetrics.\n")
    p.add_run("2. Select the recorded Session CSV.\n")
    p.add_run("3. Select the car's SD-card GPS Log (.nmea) and set the UTC timezone offset.\n")
    p.add_run("4. Select the AMS Temperatures Log (95 cells per-module data).\n")
    p.add_run("5. Click Merge & Push to Marple. The synchronized complete dataset is uploaded instantly.")

    add_h2("3.2 Recommended Marple Derived Channels")
    
    # Table of derived channels
    table = doc.add_table(rows=6, cols=3)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = table.rows[0].cells
    hdr[0].text = "Channel Name"
    hdr[1].text = "Formula / Expression"
    hdr[2].text = "Purpose / Threshold Alert"
    for c in hdr:
        set_cell_background(c, "0E5C2F")
        c.paragraphs[0].runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        c.paragraphs[0].runs[0].font.bold = True

    data = [
        ("ams_max_cell_mv", "MAX(vmax_mod0, vmax_mod1, vmax_mod2, vmax_mod3, vmax_mod4)", "Overvoltage alert (> 4200 mV)"),
        ("v_cell_min_mV", "v_cell_min_mV (Raw mV)", "Undervoltage alert (< 3000 mV)"),
        ("ams_max_temp_c", "MAX(tmax_mod0, tmax_mod1, tmax_mod2, tmax_mod3, tmax_mod4)", "Thermal ceiling alert (> 55°C)"),
        ("current_A", "corriente_accu * 0.1", "Tractive pack current in Amperes"),
        ("seq_jump", "seq - PREV(seq)", "Radio packet loss alarm (seq_jump > 1)"),
    ]

    for i, row in enumerate(data, start=1):
        cells = table.rows[i].cells
        cells[0].text = row[0]
        cells[1].text = row[1]
        cells[2].text = row[2]
        bg = "F9FAFB" if i % 2 == 0 else "FFFFFF"
        for c in cells:
            set_cell_background(c, bg)
            set_cell_margins(c, top=80, bottom=80, left=100, right=100)

    # 4. RF RANGE
    add_h1("4. RF Range & PA/LNA Optimization")
    p = doc.add_paragraph()
    p.add_run("• PA + LNA Front-End: ").bold = True
    p.add_run("Using +20 dBm (100 mW) TX power with a +10 dB LNA receiver provides a +35 dB to +42 dB link budget improvement over base nRF24 modules.\n")
    p.add_run("• RF Channel: ").bold = True
    p.add_run("Set to Channel 76 or higher (2476 MHz+) to avoid trackside 2.4 GHz WiFi interference.\n")
    p.add_run("• 250 kbps Mode: ").bold = True
    p.add_run("Configuring 250 kbps on-air datarate increases receiver sensitivity to -94 dBm (adding +9 dB link margin).")

    # 5. CHEAT SHEET
    add_h1("5. Trackside Quick-Start Checklist")
    add_code_block(
        "1. PLUG IN:      Connect Arduino USB receiver dongle to laptop.\n"
        "2. ELEVATE:      Mount pit antenna on tripod mast (2.5m+ height).\n"
        "3. CLONE/RUN:    Clone https://github.com/MrAndy5/ISCmetrics.git & run 'python ui.py'.\n"
        "4. UNLOCK CLOUD: Settings -> [X] Upload to Marple -> Enter: ISC_telemetry_2026\n"
        "5. CONNECT:      Select COM Port -> Click CONNECT.\n"
        "6. POST-RACE:    Tools -> Post-Race Analysis -> Merge SD GPS/AMS -> Upload to Marple."
    )

    doc.save(filename)
    print(f"[Word Doc] Created successfully at: {filename}")


# ==========================================
# 2. PDF GENERATION (.pdf)
# ==========================================
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#777777"))
        
        # Header
        self.drawString(54, 750, "ISC Telemetry Operational Guide | Formula Student")
        self.setStrokeColor(colors.HexColor("#D1D5DB"))
        self.setLineWidth(0.5)
        self.line(54, 744, 558, 744)
        
        # Footer
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 36, page_str)
        self.drawString(54, 36, "CONFIDENTIAL — ISC Formula Student Team")
        self.line(54, 46, 558, 46)
        self.restoreState()

def create_pdf_doc(filename):
    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        leftMargin=54,
        rightMargin=54,
        topMargin=64,
        bottomMargin=54
    )
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0E5C2F"),
        spaceAfter=4
    )
    
    sub_style = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#555555"),
        spaceAfter=14
    )
    
    h1_style = ParagraphStyle(
        'Heading1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=colors.HexColor("#0E5C2F"),
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )
    
    h2_style = ParagraphStyle(
        'Heading2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#1F2937"),
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'BodyText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12.5,
        textColor=colors.HexColor("#222222"),
        spaceAfter=5
    )

    code_style = ParagraphStyle(
        'CodeStyle',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor("#1F2937")
    )

    story = []
    
    # Title & Subtitle
    story.append(Paragraph("ISC Telemetry Operational Guide", title_style))
    story.append(Paragraph("Hardware Setup, ISCmetrics Suite & Marple Cloud Data Platform", sub_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0E5C2F"), spaceAfter=10))

    # 1. PHYSICAL SETUP
    story.append(Paragraph("1. Physical Hardware Setup", h1_style))
    story.append(Paragraph("1.1 Car Side (Transmitter / ECU)", h2_style))
    story.append(Paragraph("• <b>Antenna Positioning:</b> Mount vertically on the roll hoop / shark fin with an insulating spacer. Maintain at least 3.5 cm (λ/4) clearance from carbon fiber panels to prevent RF shadowing.", body_style))
    story.append(Paragraph("• <b>RF Cabling:</b> Use low-loss RG-316 or RG-142 coaxial cable with SMA connectors (< 50 cm). Route away from high-voltage (HV) cables and inverter phase lines.", body_style))
    story.append(Paragraph("• <b>Power Decoupling:</b> High-power PA modules draw up to 150 mA in peak bursts. Solder a 10–100 µF electrolytic in parallel with a 100 nF ceramic capacitor directly across the module's VCC (3.3V) and GND pins.", body_style))

    story.append(Paragraph("1.2 Pitwall Side (USB Receiver Ground Station)", h2_style))
    story.append(Paragraph("• <b>Hardware:</b> Arduino Nano / USB dongle connected to nRF24L01+ + PA/LNA module over SPI, communicating via USB-Serial at 115200 baud.", body_style))
    story.append(Paragraph("• <b>Mast Elevation:</b> Mount the high-gain antenna (+9 to +14 dBi) on a tripod mast 2.5 m to 3.5 m above ground to ensure line-of-sight and clear the Fresnel zone.", body_style))

    # 2. ISCMETRICS
    story.append(Paragraph("2. Installing & Running ISCmetrics", h1_style))
    story.append(Paragraph("ISCmetrics is the official Formula Student telemetry desktop application developed for real-time monitoring, state machine diagnostics, and CSV logging.<br/>"
                           "• <b>GitHub Repository:</b> <font color='#0E5C2F'>https://github.com/MrAndy5/ISCmetrics</font><br/>"
                           "• <b>Releases / Pre-built Binary:</b> <font color='#0E5C2F'>https://github.com/MrAndy5/ISCmetrics/releases/latest</font>", body_style))

    story.append(Paragraph("2.1 Installation from Source", h2_style))
    code_text = (
        "git clone https://github.com/MrAndy5/ISCmetrics.git<br/>"
        "cd ISCmetrics<br/>"
        "python -m venv venv<br/>"
        ".\\venv\\Scripts\\Activate.ps1<br/>"
        "pip install PyQt5 matplotlib pyserial numpy pandas marple requests python-can<br/>"
        "python ui.py"
    )
    tbl_code = Table([[Paragraph(code_text, code_style)]], colWidths=[500])
    tbl_code.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F3F4F6")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#D1D5DB")),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(tbl_code)
    story.append(Spacer(1, 6))

    story.append(Paragraph("2.2 Cloud Upload Authentication", h2_style))
    pass_callout = (
        "<b>★ MARPLE CLOUD UPLOAD PASSWORD:</b><br/>"
        "To enable cloud uploads in the Settings dialog, enter the password:<br/>"
        "<b><font size=10 color='#B45309'>Password: ISC_telemetry_2026</font></b><br/>"
        "<i>Workflow: Click Settings (Gear Icon) -> Check 'Upload to Marple Data (cloud)' -> Enter Password -> Save.</i>"
    )
    tbl_pass = Table([[Paragraph(pass_callout, body_style)]], colWidths=[500])
    tbl_pass.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#FEF3C7")),
        ('BOX', (0,0), (-1,-1), 1.5, colors.HexColor("#F59E0B")),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(tbl_pass)
    story.append(Spacer(1, 6))

    story.append(Paragraph("2.3 Live Session Workflow", h2_style))
    story.append(Paragraph("1. Select the Serial COM Port for the receiver dongle in the top bar dropdown.<br/>"
                           "2. Click <b>CONNECT</b> to begin live streaming (Inverter FSM, DC Bus, AMS voltages & temps, APPS pedals, Brake pressure, Link health).<br/>"
                           "3. Click <b>DISCONNECT</b> when the run completes. The session CSV is saved under <code>logs/</code> and automatically pushed to Marple in the background.", body_style))

    # 3. MARPLE DATA
    story.append(Paragraph("3. Marple Data: Cloud Uploads & Analysis", h1_style))
    story.append(Paragraph("• <b>Default API Token:</b> <code>mdb_Le69BDaNdgn1SJ4DqWX6N6btH-a8Dx8Ou96aBbLA4v8</code><br/>"
                           "• <b>Target Stream:</b> <code>ISC_Telemetry</code><br/>"
                           "• <b>Local Override:</b> Add <code>MARPLE_API_TOKEN=your_token</code> to a <code>.env</code> file in the directory.", body_style))

    story.append(Paragraph("3.1 Post-Race Data Fusion (SD Card Merge)", h2_style))
    story.append(Paragraph("1. Open <b>Tools -> Post-Race Analysis</b> in ISCmetrics.<br/>"
                           "2. Select the recorded <b>Session CSV</b>.<br/>"
                           "3. Select the car's SD-card <b>GPS Log</b> (.nmea) and set the UTC timezone offset.<br/>"
                           "4. Select the <b>AMS Temperature Log</b> (95 cells per-module data).<br/>"
                           "5. Click <b>Merge & Push to Marple</b>. The merged dataset is uploaded instantly.", body_style))

    story.append(Paragraph("3.2 Recommended Marple Derived Channels", h2_style))
    table_data = [
        [Paragraph("<b>Channel Name</b>", body_style), Paragraph("<b>Formula / Expression</b>", body_style), Paragraph("<b>Purpose / Alert</b>", body_style)],
        [Paragraph("ams_max_cell_mv", code_style), Paragraph("MAX(vmax_mod0..4)", code_style), Paragraph("Overvoltage alert (> 4200 mV)", body_style)],
        [Paragraph("v_cell_min_mV", code_style), Paragraph("v_cell_min_mV (Raw)", code_style), Paragraph("Undervoltage alert (< 3000 mV)", body_style)],
        [Paragraph("ams_max_temp_c", code_style), Paragraph("MAX(tmax_mod0..4)", code_style), Paragraph("Thermal ceiling alert (> 55°C)", body_style)],
        [Paragraph("current_A", code_style), Paragraph("corriente_accu * 0.1", code_style), Paragraph("Tractive pack current in Amps", body_style)],
        [Paragraph("seq_jump", code_style), Paragraph("seq - PREV(seq)", code_style), Paragraph("Radio packet loss (seq_jump > 1)", body_style)],
    ]
    t_derived = Table(table_data, colWidths=[110, 180, 210])
    t_derived.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0E5C2F")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#D1D5DB")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#F9FAFB"), colors.white]),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(t_derived)
    story.append(Spacer(1, 6))

    # 4. RF RANGE & CHEAT SHEET
    story.append(Paragraph("4. RF Range Optimization & Trackside Cheat Sheet", h1_style))
    story.append(Paragraph("• <b>PA + LNA:</b> +20 dBm (100 mW) TX power + 10 dB LNA gain gives +35 dB to +42 dB total link margin improvement.<br/>"
                           "• <b>RF Channel:</b> Set to Channel 76 or higher (2476 MHz+) to avoid trackside 2.4 GHz WiFi congestion.<br/>"
                           "• <b>250 kbps Mode:</b> Extends receiver sensitivity to -94 dBm for maximum range across large tracks.", body_style))

    cheat_text = (
        "1. PLUG IN:      Connect Arduino USB receiver dongle to laptop.<br/>"
        "2. ELEVATE:      Mount pit antenna on tripod mast (2.5m+ height).<br/>"
        "3. CLONE/RUN:    Clone https://github.com/MrAndy5/ISCmetrics.git & run 'python ui.py'.<br/>"
        "4. UNLOCK CLOUD: Settings -> [X] Upload to Marple -> Enter: <b>ISC_telemetry_2026</b><br/>"
        "5. CONNECT:      Select COM Port -> Click CONNECT.<br/>"
        "6. POST-RACE:    Tools -> Post-Race Analysis -> Merge SD GPS/AMS -> Upload to Marple."
    )
    tbl_cheat = Table([[Paragraph(cheat_text, code_style)]], colWidths=[500])
    tbl_cheat.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F3F4F6")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#0E5C2F")),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(tbl_cheat)

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"[PDF Doc] Created successfully at: {filename}")

if __name__ == "__main__":
    base_dir = r"c:\Users\andre\Desktop\Universidad\ICAI\4\TFG\Repositorios\IFS08-TE\ISC_REAL_TIME_25"
    docx_path = os.path.join(base_dir, "ISC_Telemetry_Guide.docx")
    pdf_path = os.path.join(base_dir, "ISC_Telemetry_Guide.pdf")
    
    create_word_doc(docx_path)
    create_pdf_doc(pdf_path)
