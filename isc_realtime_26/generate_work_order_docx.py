import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls

def create_work_order():
    doc = docx.Document()

    # Set page margins (1 inch / 2.54 cm)
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)
        
        # Header / Footer setup
        header = section.header
        hp = header.paragraphs[0]
        hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        hrun = hp.add_run("IFS09 Telemetry Base Station | Work Order: WO-IFS09-TEL-001")
        hrun.font.name = "Arial"
        hrun.font.size = Pt(8.5)
        hrun.font.color.rgb = RGBColor(128, 128, 128)

        footer = section.footer
        fp = footer.paragraphs[0]
        fp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        frun = fp.add_run("Formula Student Team — ISC Telemetry Subsystem")
        frun.font.name = "Arial"
        frun.font.size = Pt(8.5)
        frun.font.color.rgb = RGBColor(128, 128, 128)

    # Style colors
    PRIMARY_COLOR = RGBColor(15, 45, 95)    # Deep Navy
    SECONDARY_COLOR = RGBColor(40, 80, 140) # Slate Blue
    DARK_TEXT = RGBColor(35, 35, 35)       # Charcoal Body Text
    ACCENT_HEX = "183B6B"
    BG_LIGHT_HEX = "F0F4F8"
    BORDER_HEX = "CCCCCC"

    # Helper: Set Cell Shading
    def set_cell_background(cell, fill_hex):
        tcPr = cell._tc.get_or_add_tcPr()
        shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
        tcPr.append(shd)

    # Helper: Set Table Borders
    def set_table_borders(table, border_color=BORDER_HEX):
        tblPr = table._tbl.tblPr
        borders = parse_xml(f'''
            <w:tblBorders {nsdecls("w")}>
                <w:top w:val="single" w:sz="6" w:space="0" w:color="{border_color}"/>
                <w:left w:val="single" w:sz="6" w:space="0" w:color="{border_color}"/>
                <w:bottom w:val="single" w:sz="6" w:space="0" w:color="{border_color}"/>
                <w:right w:val="single" w:sz="6" w:space="0" w:color="{border_color}"/>
                <w:insideH w:val="single" w:sz="4" w:space="0" w:color="{border_color}"/>
                <w:insideV w:val="single" w:sz="4" w:space="0" w:color="{border_color}"/>
            </w:tblBorders>
        ''')
        tblPr.append(borders)

    # Helper: Format Heading 1
    def add_h1(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.name = "Arial"
        run.font.size = Pt(13)
        run.font.bold = True
        run.font.color.rgb = PRIMARY_COLOR
        return p

    # Helper: Format Heading 2
    def add_h2(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.name = "Arial"
        run.font.size = Pt(11)
        run.font.bold = True
        run.font.color.rgb = SECONDARY_COLOR
        return p

    # Helper: Format Body Paragraph
    def add_body(text="", bold_prefix=""):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.line_spacing = 1.15
        if bold_prefix:
            r_pre = p.add_run(bold_prefix)
            r_pre.font.name = "Arial"
            r_pre.font.size = Pt(9.5)
            r_pre.font.bold = True
            r_pre.font.color.rgb = DARK_TEXT
        if text:
            r_txt = p.add_run(text)
            r_txt.font.name = "Arial"
            r_txt.font.size = Pt(9.5)
            r_txt.font.color.rgb = DARK_TEXT
        return p

    # Helper: Format Bullet
    def add_bullet(text, bold_prefix=""):
        p = doc.add_paragraph(style='List Bullet')
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.line_spacing = 1.15
        if bold_prefix:
            r_pre = p.add_run(bold_prefix)
            r_pre.font.name = "Arial"
            r_pre.font.size = Pt(9.5)
            r_pre.font.bold = True
            r_pre.font.color.rgb = DARK_TEXT
        if text:
            r_txt = p.add_run(text)
            r_txt.font.name = "Arial"
            r_txt.font.size = Pt(9.5)
            r_txt.font.color.rgb = DARK_TEXT
        return p

    # --- TITLE ---
    title_p = doc.add_paragraph()
    title_p.paragraph_format.space_before = Pt(0)
    title_p.paragraph_format.space_after = Pt(2)
    t_run = title_p.add_run("WORK ORDER: IFS09 TELEMETRY RECEIVER")
    t_run.font.name = "Arial"
    t_run.font.size = Pt(16)
    t_run.font.bold = True
    t_run.font.color.rgb = PRIMARY_COLOR

    sub_p = doc.add_paragraph()
    sub_p.paragraph_format.space_before = Pt(0)
    sub_p.paragraph_format.space_after = Pt(8)
    s_run = sub_p.add_run("PCB Design Specification, Hardware Interfacing & Quality Assurance Protocol")
    s_run.font.name = "Arial"
    s_run.font.size = Pt(10.5)
    s_run.font.italic = True
    s_run.font.color.rgb = SECONDARY_COLOR

    # --- METADATA TABLE ---
    meta_tbl = doc.add_table(rows=2, cols=4)
    meta_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(meta_tbl, "B0C4DE")

    headers_meta = [
        ("Document ID:", "WO-IFS09-TEL-001"),
        ("Subsystem:", "Telemetry Ground Station"),
        ("Date / Version:", "August 2026 / Rev 1.0"),
        ("Author / Team:", "ISC Electronics & Telemetry Team")
    ]

    for idx, (label, val) in enumerate(headers_meta):
        row = idx // 2
        col = (idx % 2) * 2
        cell_lbl = meta_tbl.cell(row, col)
        cell_val = meta_tbl.cell(row, col + 1)
        
        set_cell_background(cell_lbl, BG_LIGHT_HEX)
        cell_lbl.paragraphs[0].paragraph_format.space_after = Pt(1)
        cell_val.paragraphs[0].paragraph_format.space_after = Pt(1)
        
        rl = cell_lbl.paragraphs[0].add_run(label)
        rl.font.name = "Arial"
        rl.font.size = Pt(8.5)
        rl.font.bold = True
        rl.font.color.rgb = PRIMARY_COLOR

        rv = cell_val.paragraphs[0].add_run(val)
        rv.font.name = "Arial"
        rv.font.size = Pt(8.5)
        rv.font.color.rgb = DARK_TEXT

    doc.add_paragraph().paragraph_format.space_after = Pt(4)

    # --- SECTION 1 ---
    add_h1("1. Executive Summary & Functional Description")
    
    add_h2("1.1 Purpose")
    add_body("This Work Order defines the technical requirements, hardware architecture, component specifications, and verification testing procedures for designing and manufacturing the IFS09 Telemetry Receiver PCB. The board acts as the dedicated ground station receiving interface, capturing telemetry packet frames from the race car and forwarding them over high-speed USB-Serial to the trackside engineering computer.")

    add_h2("1.2 System Overview & Module Integration")
    add_bullet(" An 8-bit ATmega328P microcontroller running at 16 MHz (5V logic). It manages SPI transactions with the wireless transceiver, decodes raw telemetry payloads, verifies frame checksums/integrity, and streams formatted data packets to the PC via its integrated USB-C bridge.", "Processing & USB Bridge (Arduino Nano 3.0):")
    add_bullet(" 2.4 GHz GFSK transceiver with integrated RF front-end (PA + LNA) offering enhanced receiver sensitivity (-95 dBm @ 250 kbps) and long-range capability. It interfaces with the Nano via hardware SPI and requires dedicated clean 3.3V power.", "Wireless Transceiver (nRF24L01+ PA+LNA):")

    # --- SECTION 2 ---
    add_h1("2. System Architecture Diagram")
    add_body("The block diagram below represents the system architecture, power rails, SPI bus, and external I/O interfaces.")
    
    # Diagram box (placeholder box with border)
    diag_tbl = doc.add_table(rows=1, cols=1)
    diag_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    diag_cell = diag_tbl.cell(0, 0)
    diag_cell.width = Inches(6.8)
    set_cell_background(diag_cell, "FAFAFA")
    set_table_borders(diag_tbl, "999999")
    
    dp = diag_cell.paragraphs[0]
    dp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    dp.paragraph_format.space_before = Pt(30)
    dp.paragraph_format.space_after = Pt(30)
    drun = dp.add_run("[ SYSTEM ARCHITECTURE & INTERCONNECTION DIAGRAM ]\n(Reserved Area for Author Diagram)")
    drun.font.name = "Arial"
    drun.font.size = Pt(10)
    drun.font.italic = True
    drun.font.color.rgb = RGBColor(120, 120, 120)

    # --- SECTION 3 ---
    add_h1("3. Hardware & Design Requirements")

    add_h2("3.1 Core Component & Electrical Requirements")
    add_bullet(" Standard socket/footprint to mount an Arduino Nano 3.0 featuring a native USB-C connector for communication and 5V bus power.", "Microcontroller Module:")
    add_bullet(" Standard 2x4 (2.54 mm pitch) socket header to mount the nRF24L01+ PA+LNA transceiver module.", "RF Transceiver Interface:")
    add_bullet(" Edge-mounted / chassis-mounted SMA Female (Jack) connector (50 Ω impedance) matched to a high-gain 2.4 GHz omnidirectional whip antenna.", "External Antenna Connection:")
    add_bullet(" Dedicated on-board low-dropout regulator (5V to 3.3V, e.g., AMS1117-3.3) and decoupling network (10-47 µF bulk + 100 nF ceramic) adjacent to the RF module VCC/GND pins to prevent current brownouts during RF bursts.", "Power Regulation & Filtering:")

    add_h2("3.2 Pin Mapping & Interface Specification")
    pin_tbl = doc.add_table(rows=10, cols=4)
    pin_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(pin_tbl)

    headers_pin = ["Signal Name", "Arduino Nano Pin", "nRF24L01+ Pin", "Functional Description"]
    for c_idx, h_text in enumerate(headers_pin):
        c = pin_tbl.cell(0, c_idx)
        set_cell_background(c, ACCENT_HEX)
        c.paragraphs[0].paragraph_format.space_after = Pt(1)
        r = c.paragraphs[0].add_run(h_text)
        r.font.name = "Arial"
        r.font.size = Pt(8.5)
        r.font.bold = True
        r.font.color.rgb = RGBColor(255, 255, 255)

    pin_data = [
        ("VCC_5V", "5V / VIN", "—", "5.0V Main Bus derived from USB-C"),
        ("VCC_3V3", "3V3 / Reg OUT", "VCC (Pin 2)", "Regulated & Decoupled 3.3V Power Rail"),
        ("GND", "GND", "GND (Pin 1)", "Common Ground Return Plane"),
        ("CE", "D9 (or D8)", "CE (Pin 3)", "Transceiver Chip Enable / RX-TX Mode Control"),
        ("CSN", "D10 (SS)", "CSN (Pin 4)", "SPI Chip Select Not (Active Low)"),
        ("SCK", "D13", "SCK (Pin 5)", "SPI Serial Clock"),
        ("MOSI", "D11", "MOSI (Pin 6)", "SPI Master Out Slave In"),
        ("MISO", "D12", "MISO (Pin 7)", "SPI Master In Slave Out"),
        ("IRQ", "D2 (INT0)", "IRQ (Pin 8)", "Optional External Interrupt / Data Ready Line")
    ]

    for r_idx, row_vals in enumerate(pin_data):
        for c_idx, val in enumerate(row_vals):
            c = pin_tbl.cell(r_idx + 1, c_idx)
            if r_idx % 2 == 1:
                set_cell_background(c, "F7F9FC")
            c.paragraphs[0].paragraph_format.space_after = Pt(1)
            r = c.paragraphs[0].add_run(val)
            r.font.name = "Arial"
            r.font.size = Pt(8.5)
            r.font.color.rgb = DARK_TEXT

    doc.add_paragraph().paragraph_format.space_after = Pt(2)

    add_h2("3.3 Testability & Mechanical Requirements")
    add_bullet(" Dedicated test points with silkscreen labels must be placed on the top copper layer for TP_5V, TP_3V3, TP_GND, TP_SCK, TP_MOSI, TP_MISO, TP_CE, TP_CSN, and UART lines.", "On-Board Test Points:")
    add_bullet(" Four (4) symmetric M3 mounting holes (3.2 mm drill diameter) to secure the board inside a custom 3D-printed enclosure using M3 threaded heat-set inserts or standoffs.", "Mechanical Mounting:")
    add_bullet(" Complete physical clearance for direct USB-C cable mating, SMA antenna extension, and LED visibility.", "Enclosure Clearances:")

    # --- SECTION 4 ---
    add_h1("4. Verification & Testing Protocol")
    add_body("Every manufactured board unit must successfully pass the following verification tests in sequence:")

    add_h2("4.1 Power Supply Rails Verification (TP_5V & TP_3V3)")
    add_bullet(" Before power-up, measure resistance across supply test points to GND (R > 10 kΩ). Connect USB-C power and measure DC voltages using a DMM.", "Procedure:")
    add_bullet(" TP_5V must measure 5.00V ± 0.25V; TP_3V3 must measure 3.30V ± 0.10V with ripple < 30 mVp-p under active RX load.", "Acceptance Criteria:")

    add_h2("4.2 Microcontroller to Transceiver Interface Test")
    add_bullet(" Flash SPI test firmware. Execute radio.begin() and check radio.isChipConnected() over serial monitor.", "Procedure:")
    add_bullet(" Transceiver returns TRUE status, valid register dumps, and clean clock waveforms on TP_SCK.", "Acceptance Criteria:")

    add_h2("4.3 USB-Serial Communication Test with PuTTY")
    add_bullet(" Connect the board to PC via USB-C. Open PuTTY terminal at 115200 baud, 8-N-1, No Flow Control.", "Procedure:")
    add_bullet(" Continuous streaming of raw telemetry frames for 10 minutes with 0% framing errors or data corruption.", "Acceptance Criteria:")

    add_h2("4.4 Vehicle Dynamic RF Range & Link Test")
    add_bullet(" Install telemetry transmitter in the car or dynamic test fixture; place receiver in the pits with external 2.4 GHz antenna.", "Procedure:")
    add_bullet(" Packet Reception Rate (PRR) ≥ 95% at line-of-sight distance ≥ 300 meters under race-condition electrical noise.", "Acceptance Criteria:")

    # --- SECTION 5 ---
    add_h1("5. Quality Assurance Test Execution Sign-Off Sheet")
    
    qa_tbl = doc.add_table(rows=6, cols=6)
    qa_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(qa_tbl)

    headers_qa = ["Test Item", "Target / Acceptance Criteria", "Measured Value", "Pass / Fail", "Inspector", "Date"]
    for c_idx, h_text in enumerate(headers_qa):
        c = qa_tbl.cell(0, c_idx)
        set_cell_background(c, ACCENT_HEX)
        c.paragraphs[0].paragraph_format.space_after = Pt(1)
        r = c.paragraphs[0].add_run(h_text)
        r.font.name = "Arial"
        r.font.size = Pt(8.5)
        r.font.bold = True
        r.font.color.rgb = RGBColor(255, 255, 255)

    qa_data = [
        ("1. 5V Supply Rail", "4.75 V – 5.25 V at TP_5V", "", "", "", ""),
        ("2. 3.3V Supply Rail", "3.20 V – 3.40 V at TP_3V3", "", "", "", ""),
        ("3. SPI & nRF24 Comm", "isChipConnected() == true", "", "", "", ""),
        ("4. PuTTY Serial Stream", "0% error rate / 10 min stream", "", "", "", ""),
        ("5. Vehicle Range Test", "PRR ≥ 95% at ≥ 300 m line-of-sight", "", "", "", "")
    ]

    for r_idx, row_vals in enumerate(qa_data):
        for c_idx, val in enumerate(row_vals):
            c = qa_tbl.cell(r_idx + 1, c_idx)
            if r_idx % 2 == 1:
                set_cell_background(c, "F7F9FC")
            c.paragraphs[0].paragraph_format.space_after = Pt(1)
            r = c.paragraphs[0].add_run(val)
            r.font.name = "Arial"
            r.font.size = Pt(8.5)
            r.font.color.rgb = DARK_TEXT

    doc.add_paragraph().paragraph_format.space_after = Pt(4)

    # --- SECTION 6 ---
    add_h1("6. Post-Design Requirement: Design Report")
    add_body("Upon completion of the PCB layout, hardware fabrication, and bench/track testing, a comprehensive Design Report document must be filled out and submitted for technical review.")
    add_body("The Design Report must document:")
    add_bullet(" Detailed schematic diagrams, layer stack-up, trace routing, and RF ground plane implementation.", "Schematic & Layout Documentation:")
    add_bullet(" Complete list of manufacturer part numbers, exact SMD/through-hole footprints, and supplier sourcing.", "Bill of Materials (BOM):")
    add_bullet(" Enclosure CAD integration, connector port clearances, and M3 insert stress considerations.", "3D Mechanical Integration:")
    add_bullet(" Oscilloscope captures, measured voltage rails, serial logs, and vehicle link budget telemetry graphs.", "Validation Test Results:")
    add_bullet(" Assembly issues encountered, thermal behavior, and proposed revisions for next-generation hardware.", "Design Iterations & Recommendations:")

    # Save document
    output_path = r"c:\Users\andre\Desktop\Universidad\ICAI\4\TFG\Repositorios\IFS08-TE\ISC_REAL_TIME_25\WORK_ORDER_IFS09_TELEMETRY_RECEIVER.docx"
    doc.save(output_path)
    print(f"Successfully generated: {output_path}")

if __name__ == "__main__":
    create_work_order()
