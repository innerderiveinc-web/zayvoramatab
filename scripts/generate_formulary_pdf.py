import sqlite3
import json
import re
import os
import sys

def escape_pdf(s):
    if s is None:
        return ""
    s = str(s)
    s = s.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
    s = s.replace('—', '--').replace('–', '-').replace('•', '*').replace('’', "'").replace('‘', "'")
    s = s.replace('“', '"').replace('”', '"').replace('≥', '>=').replace('≤', '<=').replace('→', '->')
    s = s.replace('µ', 'u').replace('°', ' deg ').replace('₹', 'Rs. ')
    return s.encode('latin1', 'replace').decode('latin1')

def truncate_text(text, max_len=60):
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len-3] + "..."

class PDFWriter:
    def __init__(self):
        self.pages = []
        self.fonts = {
            'F1': '/Helvetica',
            'F2': '/Helvetica-Bold',
            'F3': '/Helvetica-Oblique',
            'F4': '/Helvetica-BoldOblique',
            'F5': '/Courier',
            'F6': '/Courier-Bold'
        }

    def add_page(self, content_stream):
        self.pages.append(content_stream)

    def write(self, filename):
        objs = []
        objs.append(b'<< /Type /Catalog /Pages 2 0 R >>')
        num_pages = len(self.pages)
        kids = ' '.join([f'{3 + 2*i} 0 R' for i in range(num_pages)])
        objs.append(f'<< /Type /Pages /Kids [{kids}] /Count {num_pages} >>'.encode('latin1'))

        font_res = '<< ' + ' '.join([f'/{k} {3 + 2*num_pages + idx} 0 R' for idx, k in enumerate(self.fonts.keys())]) + ' >>'

        for i, pstream in enumerate(self.pages):
            page_obj_idx = 3 + 2*i
            content_obj_idx = 4 + 2*i
            objs.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595.28 841.89] /Contents {content_obj_idx} 0 R /Resources << /Font {font_res} >> >>'.encode('latin1'))
            objs.append(f'<< /Length {len(pstream)} >>\nstream\n'.encode('latin1') + pstream + b'\nendstream')

        for k, font_name in self.fonts.items():
            objs.append(f'<< /Type /Font /Subtype /Type1 /BaseFont {font_name} /Encoding /WinAnsiEncoding >>'.encode('latin1'))

        out = [b'%PDF-1.4\n']
        offsets = [0]
        cur_offset = len(out[0])

        for idx, obj in enumerate(objs, start=1):
            offsets.append(cur_offset)
            header = f'{idx} 0 obj\n'.encode('latin1')
            footer = b'\nendobj\n'
            chunk = header + obj + footer
            out.append(chunk)
            cur_offset += len(chunk)

        xref_pos = cur_offset
        xref = [f'xref\n0 {len(objs)+1}\n0000000000 65535 f \n'.encode('latin1')]
        for off in offsets[1:]:
            xref.append(f'{off:010d} 00000 n \n'.encode('latin1'))
        out.append(b''.join(xref))

        trailer = f'trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n'.encode('latin1')
        out.append(trailer)

        with open(filename, 'wb') as f:
            f.write(b''.join(out))
        print(f"Generated PDF: {filename} ({num_pages} pages, {len(b''.join(out))} bytes)")

class PageCanvas:
    def __init__(self, page_num, total_pages, is_cover=False):
        self.ops = []
        self.page_num = page_num
        self.total_pages = total_pages
        self.is_cover = is_cover
        self.init_page()

    def init_page(self):
        if not self.is_cover:
            # Header accent bar & title
            self.draw_rect(36, 810, 523, 2, fill_color=(0.10, 0.22, 0.38))
            self.draw_text(36, 818, "ZAYVORA MATAB OS  |  MASTER CLINICAL FORMULARY (MARCH 2026 EDITION)", font="F2", size=8, color=(0.10, 0.22, 0.38))
            self.draw_text(375, 818, "DR. IRFAN ASHRAF - CLINICAL DIRECTOR", font="F2", size=8, color=(0.72, 0.47, 0.12))

            # Footer
            self.draw_rect(36, 32, 523, 0.5, stroke_color=(0.8, 0.84, 0.88))
            self.draw_text(36, 22, "CONFIDENTIAL & PROPRIETARY  |  STANDARDIZED AYUSH / UNANI PHARMACOPOEIA", font="F1", size=7, color=(0.45, 0.5, 0.55))
            page_str = f"Page {self.page_num} of {self.total_pages}"
            self.draw_text(510, 22, page_str, font="F2", size=7, color=(0.15, 0.2, 0.25))

    def draw_rect(self, x, y, w, h, fill_color=None, stroke_color=None, line_width=1):
        cmds = ["q"]
        if fill_color:
            cmds.append(f"{fill_color[0]:.2f} {fill_color[1]:.2f} {fill_color[2]:.2f} rg")
        if stroke_color:
            cmds.append(f"{line_width} w")
            cmds.append(f"{stroke_color[0]:.2f} {stroke_color[1]:.2f} {stroke_color[2]:.2f} RG")
        cmds.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re")
        if fill_color and stroke_color:
            cmds.append("B")
        elif fill_color:
            cmds.append("f")
        elif stroke_color:
            cmds.append("s")
        cmds.append("Q")
        self.ops.append(" ".join(cmds))

    def draw_text(self, x, y, text, font="F1", size=10, color=(0.1, 0.1, 0.1)):
        clean = escape_pdf(text)
        cmd = f"q {color[0]:.2f} {color[1]:.2f} {color[2]:.2f} rg BT /{font} {size} Tf {x:.2f} {y:.2f} Td ({clean}) Tj ET Q"
        self.ops.append(cmd)

    def draw_line(self, x1, y1, x2, y2, color=(0.8, 0.84, 0.88), width=0.5):
        cmd = f"q {width} w {color[0]:.2f} {color[1]:.2f} {color[2]:.2f} RG {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l s Q"
        self.ops.append(cmd)

    def get_stream(self):
        return "\n".join(self.ops).encode('latin1')

def load_data():
    conn = sqlite3.connect('matab.db')
    c = conn.cursor()

    c.execute('SELECT id, name, category, organ_axis, icd11_code, primary_humor, phase1, phase2, phase3, product_stack, lab_monitoring, clinical_warnings FROM master_protocols')
    protocols_db = {}
    for r in c.fetchall():
        protocols_db[r[0]] = {
            'id': r[0], 'name': r[1], 'category': r[2], 'organ_axis': r[3],
            'icd11': r[4], 'humor': r[5],
            'phase1': json.loads(r[6]) if r[6] else {},
            'phase2': json.loads(r[7]) if r[7] else {},
            'phase3': json.loads(r[8]) if r[8] else {},
            'products': json.loads(r[9]) if r[9] else [],
            'lab_monitoring': json.loads(r[10]) if r[10] else {},
            'warnings': json.loads(r[11]) if r[11] else []
        }

    c.execute('SELECT kit_code, name, products_included, indication, price_min_inr, price_max_inr, regulatory_track FROM protocol_kits')
    kits_db = {}
    for r in c.fetchall():
        kits_db[r[0]] = {
            'code': r[0], 'name': r[1], 'products': r[2], 'indication': r[3],
            'price_min': r[4], 'price_max': r[5], 'track': r[6]
        }

    c.execute('SELECT code, name, classical_principle, target_axes, duration_days, rules FROM master_parhez')
    parhez_db = {}
    for r in c.fetchall():
        try:
            rules = json.loads(r[5]) if r[5] else []
        except:
            rules = []
        parhez_db[r[0]] = {
            'code': r[0], 'name': r[1], 'principle': r[2], 'target_axes': r[3],
            'duration': r[4], 'rules': rules
        }

    # Load Safoof Registry from JS
    with open('apps/web/static/js/views/consultation.js', 'r') as f:
        text = f.read()

    idx = text.find('CANONICAL_MATAB_SAFOOF_REGISTRY = {')
    end_idx = text.find('};\n', idx)
    block = text[idx:end_idx+2]

    pats = re.findall(r'\"(P-\d\d)\":\s*\{([^}]+items:\s*\[(.*?)\]\s*\})', block, re.DOTALL)
    safoof_db = {}
    for pcode, full_body, items_block in pats:
        name_m = re.search(r'name:\s*\"([^\"]+)\"', full_body)
        veh_m = re.search(r'default_vehicle:\s*\"([^\"]+)\"', full_body)
        item_matches = re.findall(r'\{\s*item_name:\s*\"([^\"]+)\",\s*dose_amount:\s*([0-9.]+),\s*dose_unit:\s*\"([^\"]+)\",\s*frequency:\s*\"([^\"]+)\",\s*duration_days:\s*([0-9]+),\s*anupan_vehicle:\s*\"([^\"]+)\"\s*\}', items_block)
        items = []
        tot = 0
        for im in item_matches:
            amt = float(im[1])
            tot += amt
            raw_name = im[0]
            # extract botanical & tier
            tier = "Asl-e-Dawa"
            if "Mughaddi" in raw_name or "Foundation" in raw_name:
                tier = "Mughaddi"
            elif "Muslih" in raw_name or "Mu'addil" in raw_name or "Hepatic" in raw_name or "Gastric" in raw_name or "Bitter" in raw_name:
                tier = "Muslih"
            elif "Badraqa" in raw_name or "Muhawwil" in raw_name or "Bioavailability" in raw_name:
                tier = "Muhawwil"
            elif "Asl-e-Dawa" in raw_name:
                tier = "Asl-e-Dawa"

            items.append({
                'raw_name': raw_name,
                'tier': tier,
                'amount': amt,
                'unit': im[2],
                'freq': im[3],
                'days': int(im[4]),
                'vehicle': im[5]
            })
        safoof_db[pcode] = {
            'name': name_m.group(1) if name_m else '',
            'vehicle': veh_m.group(1) if veh_m else '',
            'items': items,
            'total_grams': tot
        }

    return protocols_db, kits_db, parhez_db, safoof_db

def build_pdf_document():
    protocols_db, kits_db, parhez_db, safoof_db = load_data()
    total_pages = 24
    writer = PDFWriter()

    # ================= PAGE 1: COVER & EXECUTIVE OVERVIEW =================
    cv = PageCanvas(1, total_pages, is_cover=True)
    # Deep Navy Top Header Box
    cv.draw_rect(36, 680, 523, 130, fill_color=(0.08, 0.18, 0.32))
    cv.draw_rect(36, 676, 523, 4, fill_color=(0.78, 0.55, 0.15)) # Gold line
    cv.draw_text(50, 780, "ZAYVORA MATAB OS  *  CLINICAL PHARMACOPOEIA", font="F2", size=10, color=(0.85, 0.70, 0.30))
    cv.draw_text(50, 750, "MASTER CLINICAL FORMULARY & CODIFIED PROTOCOLS", font="F2", size=17, color=(1, 1, 1))
    cv.draw_text(50, 730, "The Definitive 21-Protocol Manual of Classical Unani Compounding, Posology & Safety Standards", font="F1", size=10, color=(0.82, 0.88, 0.94))
    cv.draw_text(50, 700, "March 2026 Edition  |  Author & Clinical Architect: Dr. Irfan Ashraf  |  Ayush & FSSAI Compliant", font="F3", size=9, color=(0.7, 0.8, 0.9))

    # Core Compounding Canon Box
    cv.draw_rect(36, 545, 523, 120, fill_color=(0.96, 0.97, 0.99), stroke_color=(0.80, 0.85, 0.90))
    cv.draw_text(48, 645, "THE 4-TIER CLASSICAL COMPOUNDING CANON (NUSKHA NAWISI USOOL)", font="F2", size=10, color=(0.10, 0.22, 0.38))
    
    cv.draw_rect(48, 610, 115, 26, fill_color=(0.90, 0.94, 0.98), stroke_color=(0.20, 0.45, 0.70))
    cv.draw_text(52, 624, "Tier 1: Mughaddi (10-25%)", font="F2", size=8, color=(0.15, 0.35, 0.60))
    cv.draw_text(52, 613, "Sustenance & Visceral Support", font="F1", size=7, color=(0.2, 0.3, 0.4))

    cv.draw_rect(173, 610, 115, 26, fill_color=(0.90, 0.97, 0.92), stroke_color=(0.15, 0.50, 0.25))
    cv.draw_text(177, 624, "Tier 2: Asl-e-Dawa (40-60%)", font="F2", size=8, color=(0.10, 0.45, 0.20))
    cv.draw_text(177, 613, "Primary Active Pharmacodynamics", font="F1", size=7, color=(0.2, 0.3, 0.4))

    cv.draw_rect(298, 610, 115, 26, fill_color=(0.99, 0.95, 0.90), stroke_color=(0.75, 0.45, 0.15))
    cv.draw_text(302, 624, "Tier 3: Muslih (15-25%)", font="F2", size=8, color=(0.70, 0.38, 0.10))
    cv.draw_text(302, 613, "Temperament Balancer & Shield", font="F1", size=7, color=(0.2, 0.3, 0.4))

    cv.draw_rect(423, 610, 125, 26, fill_color=(0.96, 0.92, 0.99), stroke_color=(0.50, 0.25, 0.75))
    cv.draw_text(427, 624, "Tier 4: Muhawwil (5-10%)", font="F2", size=8, color=(0.45, 0.20, 0.70))
    cv.draw_text(427, 613, "Bioavailability & Catalyst", font="F1", size=7, color=(0.2, 0.3, 0.4))

    cv.draw_text(48, 592, "CLINICAL PRACTICE LAWS:", font="F2", size=8.5, color=(0.2, 0.25, 0.3))
    cv.draw_text(48, 578, "* 3-Phase Afaal Cascade: Every chronic condition must traverse Phase 1: Tanqiya (Detox), Phase 2: Tahleel, Phase 3: Taqwiyat.", font="F1", size=8, color=(0.25, 0.3, 0.35))
    cv.draw_text(48, 566, "* Single-Batch Calibration: All Matab Safoof recipes are calibrated to exact 500g yields for uniform active dosing.", font="F1", size=8, color=(0.25, 0.3, 0.35))
    cv.draw_text(48, 554, "* Zero Adulteration: Prohibited are synthetic PDE5 inhibitors, unpurified Kushtas, synthetic steroids, or unauthorized stimulants.", font="F1", size=8, color=(0.65, 0.15, 0.15))

    # Table of Contents: Quick Index of 21 Protocols
    cv.draw_rect(36, 40, 523, 495, fill_color=(1, 1, 1), stroke_color=(0.80, 0.84, 0.88))
    cv.draw_rect(36, 510, 523, 25, fill_color=(0.12, 0.25, 0.42))
    cv.draw_text(48, 518, "MASTER DIRECTORY OF CODIFIED PROTOCOLS (P-01 TO P-21)", font="F2", size=9.5, color=(1, 1, 1))

    # Table headers
    cv.draw_rect(36, 490, 523, 18, fill_color=(0.92, 0.94, 0.97))
    cv.draw_text(42, 495, "Code", font="F2", size=7.5, color=(0.2, 0.25, 0.3))
    cv.draw_text(75, 495, "Protocol Name & Indication", font="F2", size=7.5, color=(0.2, 0.25, 0.3))
    cv.draw_text(240, 495, "Organ Axis", font="F2", size=7.5, color=(0.2, 0.25, 0.3))
    cv.draw_text(355, 495, "Primary Safoof (500g Batch)", font="F2", size=7.5, color=(0.2, 0.25, 0.3))
    cv.draw_text(485, 495, "Kit / Page", font="F2", size=7.5, color=(0.2, 0.25, 0.3))
    cv.draw_line(36, 489, 559, 489, color=(0.75, 0.8, 0.85), width=1)

    y_pos = 473
    for i in range(1, 22):
        pcode = f"P-{i:02d}"
        prot = protocols_db.get(pcode, {})
        safoof = safoof_db.get(pcode, {})
        kit_code = f"K-{i:02d}"
        page_ref = i + 1

        if i % 2 == 0:
            cv.draw_rect(36, y_pos - 4, 523, 19, fill_color=(0.97, 0.98, 1.0))
        cv.draw_line(36, y_pos - 5, 559, y_pos - 5, color=(0.90, 0.92, 0.94), width=0.5)

        cv.draw_text(42, y_pos + 2, pcode, font="F2", size=7.5, color=(0.10, 0.25, 0.50))
        cv.draw_text(75, y_pos + 2, truncate_text(prot.get('name', ''), 34), font="F1", size=7.5, color=(0.15, 0.20, 0.25))
        cv.draw_text(240, y_pos + 2, truncate_text(prot.get('organ_axis', '').split('|')[0].strip(), 23), font="F3", size=7, color=(0.3, 0.35, 0.4))
        cv.draw_text(355, y_pos + 2, truncate_text(safoof.get('name', '').split('/')[0].strip(), 28), font="F1", size=7.5, color=(0.15, 0.40, 0.25))
        cv.draw_text(485, y_pos + 2, f"{kit_code}  |  p.{page_ref}", font="F2", size=7.5, color=(0.70, 0.35, 0.10))

        y_pos -= 20.5

    writer.add_page(cv.get_stream())

    # ================= PAGES 2 TO 22: PROTOCOL SHEETS (P-01 to P-21) =================
    for p_idx in range(1, 22):
        pcode = f"P-{p_idx:02d}"
        page_num = p_idx + 1
        prot = protocols_db.get(pcode, {})
        safoof = safoof_db.get(pcode, {})
        kit = kits_db.get(f"K-{p_idx:02d}", {})

        pc = PageCanvas(page_num, total_pages)

        # 1. Protocol Header Banner
        pc.draw_rect(36, 750, 523, 52, fill_color=(0.94, 0.96, 0.99), stroke_color=(0.15, 0.30, 0.55), line_width=1)
        # Badge for code
        pc.draw_rect(44, 760, 48, 32, fill_color=(0.12, 0.28, 0.52))
        pc.draw_text(52, 772, pcode, font="F2", size=14, color=(1, 1, 1))

        # Title & Category
        pc.draw_text(100, 782, prot.get('name', 'Clinical Protocol'), font="F2", size=12, color=(0.10, 0.20, 0.35))
        meta_line = f"Category: {prot.get('category', 'GENERAL')}  |  ICD-11: {prot.get('icd11', 'N/A')}  |  Humor / Mizaj: {prot.get('humor', 'Standard')}"
        pc.draw_text(100, 768, meta_line, font="F1", size=8, color=(0.35, 0.40, 0.45))
        pc.draw_text(100, 755, f"Organ-Axis: {prot.get('organ_axis', 'N/A')}", font="F3", size=8, color=(0.55, 0.35, 0.10))

        # 2. Classical 500g Safoof Formulation Table
        pc.draw_rect(36, 545, 523, 195, fill_color=(1, 1, 1), stroke_color=(0.80, 0.84, 0.88), line_width=0.75)
        pc.draw_rect(36, 720, 523, 20, fill_color=(0.18, 0.35, 0.58))
        pc.draw_text(44, 726, f"CLASSICAL MATAB SAFOOF: {safoof.get('name', 'Standard 500g Prescription')}", font="F2", size=8.5, color=(1, 1, 1))

        # Sub-header: Posology & Vehicle
        veh_str = f"Single Dose: 5g - 6g BID  |  Default Vehicle: {safoof.get('vehicle', 'Lukewarm Water')}  |  Timing: 30m Before Meals"
        pc.draw_rect(36, 704, 523, 16, fill_color=(0.95, 0.97, 0.99))
        pc.draw_text(44, 708, veh_str, font="F2", size=7.5, color=(0.15, 0.35, 0.55))

        # Table Column Headers
        pc.draw_rect(36, 688, 523, 16, fill_color=(0.90, 0.92, 0.95))
        pc.draw_text(42, 692, "#", font="F2", size=7, color=(0.2, 0.25, 0.3))
        pc.draw_text(58, 692, "Ingredient & Botanical Identification", font="F2", size=7, color=(0.2, 0.25, 0.3))
        pc.draw_text(340, 692, "Classical Compounding Tier", font="F2", size=7, color=(0.2, 0.25, 0.3))
        pc.draw_text(460, 692, "Weight (g)", font="F2", size=7, color=(0.2, 0.25, 0.3))
        pc.draw_text(515, 692, "Share %", font="F2", size=7, color=(0.2, 0.25, 0.3))
        pc.draw_line(36, 687, 559, 687, color=(0.75, 0.8, 0.85), width=1)

        # Ingredients rows
        items = safoof.get('items', [])
        total_g = safoof.get('total_grams', 500.0)
        row_y = 675
        for idx_it, it in enumerate(items, start=1):
            if idx_it > 11:
                break # fit within box
            if idx_it % 2 == 0:
                pc.draw_rect(36, row_y - 2, 523, 11, fill_color=(0.98, 0.98, 1.0))
            pc.draw_line(36, row_y - 2, 559, row_y - 2, color=(0.92, 0.94, 0.96), width=0.5)

            pc.draw_text(42, row_y, f"{idx_it}", font="F1", size=6.5, color=(0.4, 0.45, 0.5))
            # Clean name
            clean_name = it['raw_name'].split('[')[0].strip()
            pc.draw_text(58, row_y, truncate_text(clean_name, 56), font="F1", size=7, color=(0.15, 0.20, 0.25))

            tier_col = (0.15, 0.35, 0.60)
            if it['tier'] == 'Mughaddi':
                tier_col = (0.15, 0.35, 0.60)
            elif it['tier'] == 'Asl-e-Dawa':
                tier_col = (0.10, 0.45, 0.20)
            elif it['tier'] == 'Muslih':
                tier_col = (0.70, 0.38, 0.10)
            elif it['tier'] == 'Muhawwil':
                tier_col = (0.45, 0.20, 0.70)
            pc.draw_text(340, row_y, it['tier'], font="F2", size=7, color=tier_col)

            pc.draw_text(465, row_y, f"{it['amount']:.1f} g", font="F2", size=7, color=(0.15, 0.20, 0.25))
            pct = (it['amount'] / total_g) * 100 if total_g else 0
            pc.draw_text(520, row_y, f"{pct:.1f}%", font="F1", size=7, color=(0.3, 0.35, 0.4))
            row_y -= 11.2

        # Formulation Total Footer Bar
        pc.draw_rect(36, 545, 523, 14, fill_color=(0.90, 0.93, 0.97))
        pc.draw_text(58, 548, "TOTAL COMPOUND BATCH YIELD (STRICT 500g SAFFE):", font="F2", size=7, color=(0.10, 0.22, 0.38))
        pc.draw_text(460, 548, f"{total_g:.1f} g", font="F2", size=7.5, color=(0.10, 0.22, 0.38))
        pc.draw_text(515, 548, "100.0%", font="F2", size=7.5, color=(0.10, 0.22, 0.38))

        # 3. 3-Phase Clinical Afaal Cascade
        pc.draw_rect(36, 420, 523, 115, fill_color=(1, 1, 1), stroke_color=(0.80, 0.84, 0.88), line_width=0.75)
        pc.draw_rect(36, 517, 523, 18, fill_color=(0.15, 0.40, 0.30))
        pc.draw_text(44, 523, "3-PHASE CLINICAL AFAAL CASCADE (SYSTEMIC RESOLUTION TIMELINE)", font="F2", size=8, color=(1, 1, 1))

        ph1 = prot.get('phase1', {})
        ph2 = prot.get('phase2', {})
        ph3 = prot.get('phase3', {})

        # Phase 1 box
        pc.draw_rect(42, 428, 160, 82, fill_color=(0.95, 0.98, 0.96), stroke_color=(0.20, 0.50, 0.30), line_width=0.5)
        pc.draw_text(48, 498, f"Phase 1: Tanqiya ({ph1.get('days', 30)} Days)", font="F2", size=8, color=(0.10, 0.45, 0.20))
        pc.draw_text(48, 486, "Focus: Clearance & Detox", font="F2", size=7, color=(0.25, 0.30, 0.35))
        action_lines_1 = ph1.get('action', '').replace('\n', ' ')
        pc.draw_text(48, 472, truncate_text(action_lines_1, 35), font="F1", size=6.5, color=(0.2, 0.25, 0.3))
        pc.draw_text(48, 461, truncate_text(action_lines_1[35:], 35), font="F1", size=6.5, color=(0.2, 0.25, 0.3))
        target_1 = f"Target: {ph1.get('target', 'Evacuation of morbid matter')}"
        pc.draw_text(48, 442, truncate_text(target_1, 35), font="F3", size=6.5, color=(0.15, 0.35, 0.55))

        # Phase 2 box
        pc.draw_rect(212, 428, 165, 82, fill_color=(0.95, 0.97, 1.0), stroke_color=(0.20, 0.40, 0.70), line_width=0.5)
        pc.draw_text(218, 498, f"Phase 2: Tahleel ({ph2.get('days', 60)} Days)", font="F2", size=8, color=(0.15, 0.35, 0.65))
        pc.draw_text(218, 486, "Focus: Resolution & Functional Reset", font="F2", size=7, color=(0.25, 0.30, 0.35))
        action_lines_2 = ph2.get('action', '').replace('\n', ' ')
        pc.draw_text(218, 472, truncate_text(action_lines_2, 36), font="F1", size=6.5, color=(0.2, 0.25, 0.3))
        pc.draw_text(218, 461, truncate_text(action_lines_2[36:], 36), font="F1", size=6.5, color=(0.2, 0.25, 0.3))
        target_2 = f"Target: {ph2.get('target', 'Enzymatic normalization')}"
        pc.draw_text(218, 442, truncate_text(target_2, 36), font="F3", size=6.5, color=(0.15, 0.35, 0.55))

        # Phase 3 box
        pc.draw_rect(387, 428, 166, 82, fill_color=(0.99, 0.96, 0.92), stroke_color=(0.75, 0.45, 0.15), line_width=0.5)
        pc.draw_text(393, 498, f"Phase 3: Taqwiyat ({ph3.get('days', 90)} Days)", font="F2", size=8, color=(0.70, 0.38, 0.10))
        pc.draw_text(393, 486, "Focus: Consolidation & Relapse Guard", font="F2", size=7, color=(0.25, 0.30, 0.35))
        action_lines_3 = ph3.get('action', '').replace('\n', ' ')
        pc.draw_text(393, 472, truncate_text(action_lines_3, 36), font="F1", size=6.5, color=(0.2, 0.25, 0.3))
        pc.draw_text(393, 461, truncate_text(action_lines_3[36:], 36), font="F1", size=6.5, color=(0.2, 0.25, 0.3))
        target_3 = f"Target: {ph3.get('target', 'Sustained organ restitution')}"
        pc.draw_text(393, 442, truncate_text(target_3, 36), font="F3", size=6.5, color=(0.15, 0.35, 0.55))

        # 4. Track 2 Standardized GMP Product Stack & Matching Kit
        pc.draw_rect(36, 320, 523, 90, fill_color=(1, 1, 1), stroke_color=(0.80, 0.84, 0.88), line_width=0.75)
        pc.draw_rect(36, 392, 523, 18, fill_color=(0.40, 0.22, 0.60))
        pc.draw_text(44, 398, "TRACK 2 STANDARDIZED GMP PRODUCTS & CODIFIED BUNDLE KIT", font="F2", size=8, color=(1, 1, 1))

        # Kit details
        kit_str = f"Matching Kit: {kit.get('code', 'K-XX')} - {kit.get('name', 'Standard Kit')}"
        pc.draw_text(48, 376, kit_str, font="F2", size=8.5, color=(0.25, 0.15, 0.45))
        price_str = f"Target Patient MRP: Rs. {kit.get('price_min', 0):,} - Rs. {kit.get('price_max', 0):,} | Regulatory Track: {kit.get('track', 'AYUSH / Classical')}"
        pc.draw_text(48, 363, price_str, font="F2", size=7.5, color=(0.70, 0.35, 0.10))

        prods = prot.get('products', {})
        if isinstance(prods, dict):
            core = prods.get('core', [])
            support = prods.get('support', [])
            mod = prods.get('modulator', [])
            prod_names = core + support + mod
            prod_line = "Standardized Formulations: " + " + ".join([str(x) for x in prod_names[:5]])
            prod_action = f"Stack Architecture: Core: {', '.join(core)} | Support: {', '.join(support)}"
        elif isinstance(prods, list):
            prod_line = "Standardized Formulations: " + " + ".join([f"{p.get('name', '')} ({p.get('dose', '')})" if isinstance(p, dict) else str(p) for p in prods[:4]])
            prod_action = "Clinical Indications: " + " | ".join([f"{p.get('action', '')}" if isinstance(p, dict) else str(p) for p in prods[:3]])
        else:
            prod_line = f"Standardized Formulations: {str(prods)}"
            prod_action = "Clinical Stack: Ayush Standardized"
        pc.draw_text(48, 345, truncate_text(prod_line, 95), font="F1", size=7, color=(0.2, 0.25, 0.3))
        pc.draw_text(48, 332, truncate_text(prod_action, 95), font="F3", size=6.5, color=(0.4, 0.45, 0.5))

        # 5. Dietary Prescriptions & Parhez (Lifestyle Rules)
        pc.draw_rect(36, 215, 523, 95, fill_color=(1, 1, 1), stroke_color=(0.80, 0.84, 0.88), line_width=0.75)
        pc.draw_rect(36, 292, 523, 18, fill_color=(0.72, 0.45, 0.15))
        pc.draw_text(44, 298, "DIETARY PRESCRIPTION (ILAJ BIL GHIZA) & PARHEZ COMPENDIUM", font="F2", size=8, color=(1, 1, 1))

        # Dietary instructions based on category
        if "METABOLIC" in prot.get('category', ''):
            pc.draw_text(48, 276, "* Parhez Code: TM-01 / FK-01 (Hepato-Metabolic & Insulin Reset)", font="F2", size=7.5, color=(0.70, 0.35, 0.10))
            pc.draw_text(48, 263, "* Recommended: Barley soup (Kashk-e-Jau), bitter gourds, fenugreek water, walnuts 30g, steamed green leafy vegetables.", font="F1", size=7, color=(0.2, 0.25, 0.3))
            pc.draw_text(48, 250, "* Strict Abstinence: Zero refined sugars, high-fructose juices, bakery items, deep-fried fast food, chilled refrigerated water.", font="F1", size=7, color=(0.65, 0.15, 0.15))
            pc.draw_text(48, 237, "* Lifestyle Mandate: 16:8 Intermittent Fasting window (12 PM - 8 PM), post-meal 15-minute ambulation, 8,000 steps daily.", font="F3", size=7, color=(0.25, 0.3, 0.35))
            pc.draw_text(48, 224, "* Hydration Vehicle: Warm boiled water infused with Zeera Siyah & Saunf (1.5 - 2.5 Litres daily).", font="F1", size=7, color=(0.15, 0.35, 0.55))
        elif "MALE" in prot.get('category', ''):
            pc.draw_text(48, 276, "* Parhez Code: MF-01 (Male Fertility & Spermatogenesis Reset)", font="F2", size=7.5, color=(0.70, 0.35, 0.10))
            pc.draw_text(48, 263, "* Recommended: Raw walnuts 30g daily, wild oily fish, black raisins soaked in milk, pomegranate juice, pumpkin seeds.", font="F1", size=7, color=(0.2, 0.25, 0.3))
            pc.draw_text(48, 250, "* Strict Abstinence: Zero alcohol, zero nicotine/vaping, zero saunas/hot tubs, zero laptop directly on lap.", font="F1", size=7, color=(0.65, 0.15, 0.15))
            pc.draw_text(48, 237, "* Thermal Regulation: 100% loose breathable cotton boxer shorts; cold water splash to scrotum twice daily.", font="F3", size=7, color=(0.25, 0.3, 0.35))
            pc.draw_text(48, 224, "* Circadian Rhythm: Sleep strictly 10:00 PM - 6:00 AM (peak nocturnal melatonin scavenges sperm ROS).", font="F1", size=7, color=(0.15, 0.35, 0.55))
        elif "FEMALE" in prot.get('category', ''):
            pc.draw_text(48, 276, "* Parhez Code: PC-01 / UT-01 (PCOS & Pelvic Decongestion)", font="F2", size=7.5, color=(0.70, 0.35, 0.10))
            pc.draw_text(48, 263, "* Recommended: Flaxseed 1 tbsp daily, spearmint tea (anti-androgen), soaked almonds, cooked cruciferous vegetables.", font="F1", size=7, color=(0.2, 0.25, 0.3))
            pc.draw_text(48, 250, "* Strict Abstinence: Eliminate refined carbohydrates, commercial bovine dairy (<1 serving/day), synthetic trans-fats.", font="F1", size=7, color=(0.65, 0.15, 0.15))
            pc.draw_text(48, 237, "* Pelvic Circulation: Warm castor oil compress over lower abdomen 3x weekly (strictly non-menstrual bleeding days).", font="F3", size=7, color=(0.25, 0.3, 0.35))
            pc.draw_text(48, 224, "* Resistance Training: Compound strength workouts 3x weekly (GLUT-4 glucose uptake independent of insulin).", font="F1", size=7, color=(0.15, 0.35, 0.55))
        elif "CARDIO" in prot.get('category', ''):
            pc.draw_text(48, 276, "* Parhez Code: CD-01 (Neuro-Vascular & Arterial Endothelium)", font="F2", size=7.5, color=(0.70, 0.35, 0.10))
            pc.draw_text(48, 263, "* Recommended: Arjuna decocotion with cow milk, garlic cloves soaked in honey, beetroot juice (nitric oxide), pomegranate.", font="F1", size=7, color=(0.2, 0.25, 0.3))
            pc.draw_text(48, 250, "* Strict Abstinence: High sodium foods (>2.0g/day salt), pickles, red meat, trans-fat rich confectionaries, stimulants.", font="F1", size=7, color=(0.65, 0.15, 0.15))
            pc.draw_text(48, 237, "* Autonomic Nervous System: 4-7-8 Diaphragmatic vagal breathing 15 minutes twice daily; eliminate evening caffeine.", font="F3", size=7, color=(0.25, 0.3, 0.35))
            pc.draw_text(48, 224, "* Blood Pressure Rule: Daily morning seated BP logging; avoid sudden discontinuation of active vascular tonics.", font="F1", size=7, color=(0.15, 0.35, 0.55))
        elif "NEURO" in prot.get('category', ''):
            pc.draw_text(48, 276, "* Parhez Code: NE-01 (Neuro-Circadian & Sleep Recovery)", font="F2", size=7.5, color=(0.70, 0.35, 0.10))
            pc.draw_text(48, 263, "* Recommended: Badam Roghan (almond oil) nasal drops (2 drops each nostril at bedtime), warm milk with Zafran, chamomile.", font="F1", size=7, color=(0.2, 0.25, 0.3))
            pc.draw_text(48, 250, "* Strict Abstinence: Zero caffeine after 12:00 PM noon, zero digital screens after 9:00 PM (digital sunset).", font="F1", size=7, color=(0.65, 0.15, 0.15))
            pc.draw_text(48, 237, "* Circadian Entrainment: Natural sunlight exposure within 10 minutes of waking for 15 minutes to reset SCN master clock.", font="F3", size=7, color=(0.25, 0.3, 0.35))
            pc.draw_text(48, 224, "* Herbal Oil Application: Gentle scalp massage with Roghan Labub-e-Saba or Roghan Kahu 30 mins before sleep.", font="F1", size=7, color=(0.15, 0.35, 0.55))
        elif "RESPIRATORY" in prot.get('category', ''):
            pc.draw_text(48, 276, "* Parhez Code: RS-01 (Pulmonary Mucolytic & Broncho-Protection)", font="F2", size=7.5, color=(0.70, 0.35, 0.10))
            pc.draw_text(48, 263, "* Recommended: Joshanda of Mulethi, Banafsha & Sapistan; warm ginger-tulsi tea, black pepper with raw honey.", font="F1", size=7, color=(0.2, 0.25, 0.3))
            pc.draw_text(48, 250, "* Strict Abstinence: Ice-cold drinks, citrus curd at night, deep-fried snacks, exposure to chemical fumes and tobacco smoke.", font="F1", size=7, color=(0.65, 0.15, 0.15))
            pc.draw_text(48, 237, "* Inhalation Therapy: Steam inhalation with Roghan Banafsha or Eucalyptus oil twice daily during acute bronchial congestion.", font="F3", size=7, color=(0.25, 0.3, 0.35))
            pc.draw_text(48, 224, "* Breathing Discipline: Pranayama / Anulom-Vilom 15 minutes morning in fresh unpolluted air.", font="F1", size=7, color=(0.15, 0.35, 0.55))
        elif "JOINTS" in prot.get('category', ''):
            pc.draw_text(48, 276, "* Parhez Code: JT-01 (Anti-Inflammatory & Synovial Integrity)", font="F2", size=7.5, color=(0.70, 0.35, 0.10))
            pc.draw_text(48, 263, "* Recommended: Golden turmeric milk with black pepper, bone broth, soaked fenugreek seeds, castor oil 5ml at bedtime.", font="F1", size=7, color=(0.2, 0.25, 0.3))
            pc.draw_text(48, 250, "* Strict Abstinence: Nightshades (tomatoes, eggplants), sour fermented curd, excessive red lentils, purine-rich organs.", font="F1", size=7, color=(0.65, 0.15, 0.15))
            pc.draw_text(48, 237, "* External Therapy: Warm application of Roghan Suranjan or Roghan Babuna to affected joints followed by gentle flannel wrap.", font="F3", size=7, color=(0.25, 0.3, 0.35))
            pc.draw_text(48, 224, "* Low Impact Movement: Daily non-weight bearing range-of-motion mobility exercises to stimulate synovial fluid synthesis.", font="F1", size=7, color=(0.15, 0.35, 0.55))
        else:
            pc.draw_text(48, 276, "* Parhez Code: GN-01 (General Metabolic & Digestive Restoration)", font="F2", size=7.5, color=(0.70, 0.35, 0.10))
            pc.draw_text(48, 263, "* Recommended: Easily digestible khichdi, pomegranate seeds, mint-coriander infusions, soaked munakka (raisins).", font="F1", size=7, color=(0.2, 0.25, 0.3))
            pc.draw_text(48, 250, "* Strict Abstinence: Stale heavy meals, carbonated beverages, excessive red chilies, irregular meal timings.", font="F1", size=7, color=(0.65, 0.15, 0.15))
            pc.draw_text(48, 237, "* Chewing Discipline: Chew each morsel 30 times to ensure salivary amylase saturation before gastric transit.", font="F3", size=7, color=(0.25, 0.3, 0.35))
            pc.draw_text(48, 224, "* Hydration Mandate: Sip warm water 45 minutes after meals; avoid drinking large volumes during meals.", font="F1", size=7, color=(0.15, 0.35, 0.55))

        # 6. Clinical Safety Firewall & Lab Biomarkers Box
        pc.draw_rect(36, 45, 523, 160, fill_color=(1, 1, 1), stroke_color=(0.80, 0.84, 0.88), line_width=0.75)
        pc.draw_rect(36, 187, 523, 18, fill_color=(0.75, 0.15, 0.15))
        pc.draw_text(44, 193, "CLINICAL SAFETY FIREWALL, RED FLAGS & BIOMARKER SURVEILLANCE", font="F2", size=8, color=(1, 1, 1))

        # Warnings & Red Flags
        warns = prot.get('warnings', [])
        warn_str1 = warns[0] if len(warns) > 0 else "Monitor baseline hepatic & renal panels prior to initiating intensive therapy."
        warn_str2 = warns[1] if len(warns) > 1 else "In cases of concurrent pharmaceutical medication, separate herbal administration by 90 minutes."

        pc.draw_text(48, 172, "! SAFETY RED LINE:", font="F2", size=7.5, color=(0.80, 0.15, 0.15))
        pc.draw_text(135, 172, truncate_text(warn_str1, 78), font="F1", size=7, color=(0.2, 0.25, 0.3))
        pc.draw_text(48, 159, "! CONTRAINDICATION:", font="F2", size=7.5, color=(0.80, 0.15, 0.15))
        pc.draw_text(145, 159, truncate_text(warn_str2, 76), font="F1", size=7, color=(0.2, 0.25, 0.3))

        # Lab Monitoring Grid
        pc.draw_rect(44, 52, 507, 95, fill_color=(0.97, 0.98, 1.0), stroke_color=(0.70, 0.78, 0.88), line_width=0.5)
        pc.draw_text(52, 134, "BIOMARKER SURVEILLANCE & RE-EVALUATION MILESTONES:", font="F2", size=8, color=(0.10, 0.25, 0.50))

        labs = prot.get('lab_monitoring', {})
        if isinstance(labs, list):
            baseline_labs = labs[0] if len(labs) > 0 else "CBC, LFT, KFT Baseline Panel"
            day30_labs = labs[1] if len(labs) > 1 else "Primary Biomarker Surveillance"
            day90_labs = labs[2] if len(labs) > 2 else (", ".join(labs[:2]) if labs else "Metabolic & Biomarker Follow-up")
            ref_crit = "Acute clinical deterioration, organ distress, or critical vitals excursion requires immediate tertiary ER referral."
        elif isinstance(labs, dict):
            baseline_labs = labs.get('baseline', 'CBC, LFT, KFT, Fasting Blood Sugar')
            day30_labs = labs.get('day30', 'Routine assessment of primary clinical biomarker')
            day90_labs = labs.get('day90', 'Comprehensive metabolic panel & structural ultrasound/biomarker')
            ref_crit = labs.get('referral_criteria', 'Sudden acute deterioration or uncontrolled vitals requires immediate tertiary ER referral.')
        else:
            baseline_labs = "Standard Baseline Lab Panel"
            day30_labs = "Follow-up Biomarker Surveillance"
            day90_labs = "Comprehensive Organ Profile"
            ref_crit = "Immediate tertiary ER referral if vitals destabilize."

        pc.draw_text(52, 118, "Baseline Screen (Day 0):", font="F2", size=7, color=(0.2, 0.25, 0.3))
        pc.draw_text(160, 118, truncate_text(baseline_labs, 70), font="F1", size=7, color=(0.2, 0.25, 0.3))

        pc.draw_text(52, 102, "Phase 1 Check (Day 30):", font="F2", size=7, color=(0.10, 0.45, 0.20))
        pc.draw_text(160, 102, truncate_text(day30_labs, 70), font="F1", size=7, color=(0.2, 0.25, 0.3))

        pc.draw_text(52, 86, "Phase 2 Check (Day 90):", font="F2", size=7, color=(0.15, 0.35, 0.65))
        pc.draw_text(160, 86, truncate_text(day90_labs, 70), font="F1", size=7, color=(0.2, 0.25, 0.3))

        pc.draw_text(52, 68, "Emergency Referral Criteria:", font="F2", size=7, color=(0.75, 0.15, 0.15))
        pc.draw_text(165, 68, truncate_text(ref_crit, 69), font="F3", size=6.5, color=(0.55, 0.15, 0.15))

        writer.add_page(pc.get_stream())

    # ================= PAGE 23: CODIFIED PROTOCOL KITS DIRECTORY (K-01 to K-21) =================
    pk = PageCanvas(23, total_pages)
    pk.draw_rect(36, 755, 523, 45, fill_color=(0.10, 0.22, 0.38))
    pk.draw_text(48, 782, "MASTER CODIFIED PROTOCOL KITS DIRECTORY (K-01 TO K-21)", font="F2", size=13, color=(1, 1, 1))
    pk.draw_text(48, 765, "Standardized GMP Formulations, Commercial Packaging, Clinical Indications & Pricing Compendium", font="F1", size=8.5, color=(0.8, 0.85, 0.9))

    # Kits Table
    pk.draw_rect(36, 45, 523, 700, fill_color=(1, 1, 1), stroke_color=(0.80, 0.84, 0.88), line_width=0.75)
    pk.draw_rect(36, 725, 523, 20, fill_color=(0.90, 0.93, 0.97))
    pk.draw_text(42, 731, "Kit Code", font="F2", size=7.5, color=(0.15, 0.2, 0.25))
    pk.draw_text(85, 731, "Kit Commercial Title", font="F2", size=7.5, color=(0.15, 0.2, 0.25))
    pk.draw_text(225, 731, "Included Formulations Stack", font="F2", size=7.5, color=(0.15, 0.2, 0.25))
    pk.draw_text(410, 731, "Price Range (INR)", font="F2", size=7.5, color=(0.15, 0.2, 0.25))
    pk.draw_text(495, 731, "Regulatory Track", font="F2", size=7.5, color=(0.15, 0.2, 0.25))
    pk.draw_line(36, 724, 559, 724, color=(0.75, 0.8, 0.85), width=1)

    y_kit = 708
    for k_idx in range(1, 22):
        k_code = f"K-{k_idx:02d}"
        kt = kits_db.get(k_code, {})
        if k_idx % 2 == 0:
            pk.draw_rect(36, y_kit - 4, 523, 29, fill_color=(0.97, 0.98, 1.0))
        pk.draw_line(36, y_kit - 5, 559, y_kit - 5, color=(0.90, 0.92, 0.94), width=0.5)

        pk.draw_text(42, y_kit + 12, k_code, font="F2", size=8, color=(0.12, 0.28, 0.52))
        pk.draw_text(42, y_kit + 2, f"(Ref: P-{k_idx:02d})", font="F3", size=6.5, color=(0.4, 0.45, 0.5))

        pk.draw_text(85, y_kit + 12, truncate_text(kt.get('name', ''), 28), font="F2", size=7.5, color=(0.15, 0.20, 0.25))
        pk.draw_text(85, y_kit + 2, truncate_text(kt.get('indication', ''), 30), font="F1", size=6.5, color=(0.35, 0.40, 0.45))

        pk.draw_text(225, y_kit + 7, truncate_text(kt.get('products', ''), 38), font="F1", size=7, color=(0.10, 0.35, 0.20))

        p_range = f"Rs. {kt.get('price_min', 0):,} - {kt.get('price_max', 0):,}"
        pk.draw_text(410, y_kit + 7, p_range, font="F2", size=7.5, color=(0.70, 0.35, 0.10))

        track_clean = kt.get('track', 'AYUSH Classical')
        pk.draw_text(495, y_kit + 7, truncate_text(track_clean, 14), font="F1", size=7, color=(0.25, 0.30, 0.35))

        y_kit -= 31.5

    writer.add_page(pk.get_stream())

    # ================= PAGE 24: SAFETY FIREWALL, INTERACTION MATRIX & CLINICAL ATTESTATION =================
    ps = PageCanvas(24, total_pages)
    ps.draw_rect(36, 755, 523, 45, fill_color=(0.10, 0.22, 0.38))
    ps.draw_text(48, 782, "PHARMACOPOEIAL QUALITY STANDARDS & SAFETY FIREWALL", font="F2", size=13, color=(1, 1, 1))
    ps.draw_text(48, 765, "Good Compounding Practices (GCP), Herb-Drug Interaction Matrix & Official Directorate Attestation", font="F1", size=8.5, color=(0.8, 0.85, 0.9))

    # Box 1: Good Compounding Practices (GCP)
    ps.draw_rect(36, 610, 523, 135, fill_color=(1, 1, 1), stroke_color=(0.80, 0.84, 0.88), line_width=0.75)
    ps.draw_rect(36, 725, 523, 20, fill_color=(0.15, 0.35, 0.55))
    ps.draw_text(48, 731, "1. GOOD COMPOUNDING PRACTICES FOR MATAB SAFOOF (PHARMACOPOEIAL RULES)", font="F2", size=8.5, color=(1, 1, 1))

    gcp_rules = [
        "Sieve Calibration: All botanical roots, barks, and seeds must be pulverised and passed through Sieve Mesh #80 to #100 for optimal gastrointestinal mucosal absorption.",
        "Moisture Content Standard: Total residual moisture in prepared Safoof batches must never exceed 8.0% w/w to prevent microbial spore germination.",
        "Kushta Purification Mandate: Kushta Baiza Murgh and Kushta Marwareed must strictly undergo 7 certified classical Gaomutra/Arq Rose calcinations before compounding.",
        "Botanical Identity Verification: High-potency herbs (e.g. Asgandh, Guggul, Shilajit) must be HPLC fingerprinted to ensure active biomarker standardization.",
        "Storage & Stability: Finished Safoofs must be packaged in food-grade, airtight amber glass jars or triple-layer food-grade HDPE bottles protected from direct UV light."
    ]
    y_gcp = 708
    for r in gcp_rules:
        ps.draw_text(48, y_gcp, "*", font="F2", size=8, color=(0.70, 0.40, 0.10))
        ps.draw_text(58, y_gcp, truncate_text(r, 96), font="F1", size=7.5, color=(0.2, 0.25, 0.3))
        y_gcp -= 18

    # Box 2: Critical Herb-Drug Interactions
    ps.draw_rect(36, 420, 523, 180, fill_color=(1, 1, 1), stroke_color=(0.80, 0.84, 0.88), line_width=0.75)
    ps.draw_rect(36, 580, 523, 20, fill_color=(0.75, 0.15, 0.15))
    ps.draw_text(48, 586, "2. THE SAFETY FIREWALL: CRITICAL HERB-DRUG INTERACTION PROTOCOLS", font="F2", size=8.5, color=(1, 1, 1))

    hdi_matrix = [
        ("Guggul (Commiphora mukul)", "Anticoagulants / Warfarin", "HIGH SEVERITY", "Additive antiplatelet effect; risk of prolonged bleeding time. Discontinue 7 days before planned surgical procedures."),
        ("Asgandh (Withania somnifera)", "Levothyroxine / Thyroid meds", "MODERATE", "Direct stimulation of thyroid deiodinase enzymes; monitor serum Free T3/T4 closely to adjust thyroxine dosages."),
        ("Mulethi (Glycyrrhiza glabra)", "Antihypertensives / Diuretics", "HIGH SEVERITY", "Glycyrrhizin inhibits 11-beta-HSD2, inducing pseudo-hyperaldosteronism & potassium loss. Contraindicated in uncontrolled HTN."),
        ("Aqarqarha (Anacyclus pyrethrum)", "Hypertensive Emergencies", "CONTRAINDICATED", "Potent vaso-stimulant. Strictly prohibited in patients with systolic BP > 160 mmHg or documented cardiac arrhythmias."),
        ("Piperine (Black Pepper)", "CYP3A4 Substrate Drugs", "MODERATE", "Inhibits intestinal CYP3A4 & P-glycoprotein, significantly elevating blood levels of pharmaceutical medications.")
    ]

    y_hdi = 562
    for herb, drug, sev, note in hdi_matrix:
        ps.draw_rect(42, y_hdi - 3, 511, 28, fill_color=(0.99, 0.98, 0.98) if "HIGH" in sev else (1, 1, 1), stroke_color=(0.90, 0.85, 0.85), line_width=0.5)
        ps.draw_text(48, y_hdi + 15, herb, font="F2", size=7.5, color=(0.10, 0.20, 0.30))
        ps.draw_text(190, y_hdi + 15, f"Interacts with: {drug}", font="F2", size=7, color=(0.25, 0.30, 0.35))
        ps.draw_text(410, y_hdi + 15, sev, font="F2", size=7, color=(0.80, 0.15, 0.15))
        ps.draw_text(48, y_hdi + 3, truncate_text(note, 100), font="F1", size=6.5, color=(0.35, 0.40, 0.45))
        y_hdi -= 32

    # Box 3: The Forbidden List & Clinical Attestation
    ps.draw_rect(36, 45, 523, 365, fill_color=(1, 1, 1), stroke_color=(0.80, 0.84, 0.88), line_width=0.75)
    ps.draw_rect(36, 390, 523, 20, fill_color=(0.10, 0.22, 0.38))
    ps.draw_text(48, 396, "3. THE FORBIDDEN ADULTERANT LIST & CLINICAL DIRECTORATE ATTESTATION", font="F2", size=8.5, color=(1, 1, 1))

    ps.draw_text(48, 372, "ZERO TOLERANCE ADULTERANT DIRECTIVE:", font="F2", size=8, color=(0.80, 0.15, 0.15))
    forbidden_items = [
        "1. Strictly ZERO synthetic PDE5 inhibitors (Sildenafil, Tadalafil, Vardenafil) adulteration in any male vigor formulations.",
        "2. Strictly ZERO synthetic steroid hormones (DHEA, Pregnenolone, Methyltestosterone, Corticosteroids).",
        "3. Strictly ZERO raw, uncalcined or unpurified metallic/mineral Kushtas (Mercury, Arsenic, Lead, Copper).",
        "4. Strictly ZERO nephrotoxic aristolochic acid botanicals (Aristolochia species) or hepatotoxic compounds."
    ]
    y_forb = 356
    for fi in forbidden_items:
        ps.draw_text(52, y_forb, fi, font="F1", size=7.5, color=(0.3, 0.2, 0.2))
        y_forb -= 14

    # Formal Attestation Sign-off
    ps.draw_rect(44, 52, 507, 185, fill_color=(0.96, 0.97, 0.99), stroke_color=(0.75, 0.82, 0.90), line_width=0.75)
    ps.draw_text(54, 218, "CLINICAL ATTESTATION & RATIFICATION:", font="F2", size=9, color=(0.10, 0.22, 0.38))
    attest_text = (
        "I hereby certify and solemnly affirm that the formulations, compounding weights, posology regimens, "
        "and therapeutic cascades detailed across Protocols P-01 through P-21 in this compendium have been "
        "compiled in rigorous accordance with the classical canons of Unani Tibb (Kitab al-Kulliyat, Al-Qanun fi al-Tibb) "
        "and reconciled with modern molecular pharmacognosy, biomarker thresholds, and official Ayush / FSSAI safety directives. "
        "These protocols constitute the official clinical operating standard for all consultations conducted within Zayvora Matab OS."
    )
    # wrap attest text
    lines = [
        "I hereby certify and solemnly affirm that the formulations, compounding weights, posology regimens,",
        "and therapeutic cascades detailed across Protocols P-01 through P-21 in this compendium have been",
        "compiled in rigorous accordance with the classical canons of Unani Tibb (Kitab al-Kulliyat, Al-Qanun fi al-Tibb)",
        "and reconciled with modern molecular pharmacognosy, biomarker thresholds, and official Ayush / FSSAI safety directives.",
        "These protocols constitute the official clinical operating standard for all consultations conducted within Zayvora Matab OS."
    ]
    y_att = 200
    for l in lines:
        ps.draw_text(54, y_att, l, font="F3", size=7.5, color=(0.20, 0.25, 0.30))
        y_att -= 12

    # Signature Block
    ps.draw_line(54, 115, 230, 115, color=(0.10, 0.22, 0.38), width=1)
    ps.draw_text(54, 100, "DR. IRFAN ASHRAF, BUMS, MD (Unani)", font="F2", size=9, color=(0.10, 0.22, 0.38))
    ps.draw_text(54, 88, "Chief Physician & Clinical Director", font="F1", size=7.5, color=(0.4, 0.45, 0.5))
    ps.draw_text(54, 76, "Zayvora Matab Clinical Systems & Research", font="F1", size=7.5, color=(0.4, 0.45, 0.5))
    ps.draw_text(54, 64, "Date of Ratification: March 2026", font="F2", size=7.5, color=(0.70, 0.40, 0.10))

    # Stamp / Seal Box
    ps.draw_rect(360, 60, 175, 65, stroke_color=(0.15, 0.35, 0.65), line_width=1.5)
    ps.draw_text(370, 108, "ZAYVORA MATAB OS", font="F2", size=8.5, color=(0.15, 0.35, 0.65))
    ps.draw_text(370, 95, "OFFICIAL PHARMACOPOEIA", font="F2", size=7.5, color=(0.70, 0.40, 0.10))
    ps.draw_text(370, 82, "VALIDATED & RATIFIED", font="F2", size=7.5, color=(0.15, 0.50, 0.25))
    ps.draw_text(370, 70, "Ref: ZAY-PHARM-2026-v2.1", font="F5", size=7, color=(0.4, 0.45, 0.5))

    writer.add_page(ps.get_stream())

    # Write output PDF
    pdf_filename = "ZAYVORA_Master_Clinical_Formulary_21_Protocols.pdf"
    writer.write(pdf_filename)

    # Also build standalone styled HTML printable compendium
    build_html_document(protocols_db, kits_db, parhez_db, safoof_db)

def build_html_document(protocols_db, kits_db, parhez_db, safoof_db):
    html_file = "ZAYVORA_Master_Clinical_Formulary_21_Protocols.html"
    
    html = []
    html.append("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Zayvora Matab OS - Master Clinical Formulary (21 Protocols)</title>
<style>
  @page { size: A4; margin: 15mm 15mm 15mm 15mm; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; color: #1a202c; background: #f7fafc; margin: 0; padding: 20px; font-size: 11px; line-height: 1.4; }
  .page { background: #ffffff; width: 210mm; min-height: 297mm; margin: 0 auto 30px auto; padding: 16mm; box-sizing: border-box; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); page-break-after: always; position: relative; }
  @media print {
    body { background: #fff; padding: 0; }
    .page { width: 100%; min-height: 100%; margin: 0; box-shadow: none; page-break-after: always; }
    .no-print { display: none !important; }
  }
  .header-bar { border-bottom: 2px solid #1a365d; padding-bottom: 8px; margin-bottom: 14px; display: flex; justify-content: space-between; align-items: flex-end; }
  .header-title { font-size: 10px; font-weight: 700; color: #1a365d; letter-spacing: 0.5px; }
  .header-meta { font-size: 9px; font-weight: 600; color: #b7791f; }
  .footer-bar { position: absolute; bottom: 12mm; left: 16mm; right: 16mm; border-top: 1px solid #e2e8f0; padding-top: 6px; display: flex; justify-content: space-between; font-size: 9px; color: #718096; }
  
  .cover-box { background: #0f172a; color: #fff; padding: 24px; border-radius: 8px; border-bottom: 4px solid #b7791f; margin-bottom: 20px; }
  .cover-badge { font-size: 10px; font-weight: 700; color: #f6e05e; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 8px; }
  .cover-title { font-size: 22px; font-weight: 800; margin: 0 0 8px 0; letter-spacing: -0.5px; }
  .cover-subtitle { font-size: 12px; color: #cbd5e1; margin-bottom: 12px; }
  .cover-meta { font-size: 10px; color: #94a3b8; border-top: 1px solid #334155; padding-top: 8px; }
  
  .section-card { border: 1px solid #e2e8f0; border-radius: 6px; overflow: hidden; margin-bottom: 14px; background: #fff; }
  .section-header { padding: 6px 12px; font-size: 10px; font-weight: 700; color: #fff; text-transform: uppercase; letter-spacing: 0.5px; }
  .header-navy { background: #1a365d; }
  .header-green { background: #22543d; }
  .header-amber { background: #975a16; }
  .header-purple { background: #553c9a; }
  .header-red { background: #9b2c2c; }
  
  .protocol-banner { display: flex; align-items: center; gap: 14px; background: #ebf8ff; border: 1px solid #bee3f8; border-radius: 6px; padding: 12px; margin-bottom: 14px; }
  .proto-code { background: #2b6cb0; color: #fff; font-size: 18px; font-weight: 800; padding: 8px 12px; border-radius: 6px; min-width: 45px; text-align: center; }
  .proto-name { font-size: 15px; font-weight: 800; color: #1a365d; margin-bottom: 4px; }
  .proto-meta { font-size: 9.5px; color: #4a5568; }
  
  table.data-table { width: 100%; border-collapse: collapse; font-size: 9.5px; }
  table.data-table th { background: #edf2f7; color: #2d3748; text-align: left; padding: 6px 8px; font-weight: 700; border-bottom: 1px solid #cbd5e0; }
  table.data-table td { padding: 5px 8px; border-bottom: 1px solid #e2e8f0; }
  table.data-table tr:nth-child(even) { background: #f7fafc; }
  
  .tier-mughaddi { color: #2b6cb0; font-weight: 700; }
  .tier-asl { color: #276749; font-weight: 700; }
  .tier-muslih { color: #c05621; font-weight: 700; }
  .tier-muhawwil { color: #6b46c1; font-weight: 700; }
  
  .phase-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; padding: 10px; }
  .phase-box { border-radius: 6px; padding: 8px; font-size: 9px; }
  .phase-1 { background: #f0fff4; border: 1px solid #c6f6d5; }
  .phase-2 { background: #ebf8ff; border: 1px solid #bee3f8; }
  .phase-3 { background: #fffaf0; border: 1px solid #feebc8; }
  
  .rules-list { padding: 8px 12px; margin: 0; list-style: none; font-size: 9.5px; }
  .rules-list li { margin-bottom: 5px; position: relative; padding-left: 14px; }
  .rules-list li::before { content: "•"; position: absolute; left: 0; color: #b7791f; font-weight: bold; }
  
  .print-btn { position: fixed; top: 15px; right: 15px; background: #2b6cb0; color: #fff; padding: 10px 18px; border-radius: 6px; font-weight: bold; text-decoration: none; box-shadow: 0 4px 6px rgba(0,0,0,0.1); cursor: pointer; border: none; font-size: 13px; z-index: 1000; }
</style>
</head>
<body>
<button class="print-btn no-print" onclick="window.print()">Print / Save as PDF (Cmd+P)</button>
""")

    # HTML Cover Page
    html.append(f"""
<div class="page">
  <div class="header-bar">
    <div class="header-title">ZAYVORA MATAB OS  |  MASTER CLINICAL FORMULARY</div>
    <div class="header-meta">DR. IRFAN ASHRAF - CLINICAL DIRECTOR</div>
  </div>
  
  <div class="cover-box">
    <div class="cover-badge">Official Clinical Operating Manual (March 2026)</div>
    <div class="cover-title">Master Clinical Formulary & Codified Protocols Compendium</div>
    <div class="cover-subtitle">The Complete 21-Protocol Reference Compendium of Classical Unani Compounding (500g Safoof-e-Matab), Posology, 3-Phase Afaal Cascades, Standardized GMP Kits & Lifestyle Rules</div>
    <div class="cover-meta">Compiled & Ratified by: <strong>Dr. Irfan Ashraf</strong>, Chief Physician | Regulatory Standard: Standardized AYUSH / Unani Pharmacopoeial Standard & FSSAI Compliant</div>
  </div>

  <div class="section-card">
    <div class="section-header header-navy">The 4-Tier Classical Compounding Canon (Nuskha Nawisi Usool)</div>
    <div style="display:grid; grid-template-columns:1fr 1fr 1fr 1fr; gap:10px; padding:12px;">
      <div style="background:#ebf8ff; border:1px solid #bee3f8; padding:8px; border-radius:6px;">
        <div style="font-weight:bold; color:#2b6cb0;">Tier 1: Mughaddi (10-25%)</div>
        <div style="font-size:8.5px; color:#4a5568; margin-top:3px;">Foundation, visceral tissue support, mucilaginous protective buffers (*Badam, Maghz-e-Kadu, Musli*).</div>
      </div>
      <div style="background:#f0fff4; border:1px solid #c6f6d5; padding:8px; border-radius:6px;">
        <div style="font-weight:bold; color:#276749;">Tier 2: Asl-e-Dawa (40-60%)</div>
        <div style="font-size:8.5px; color:#4a5568; margin-top:3px;">Primary pharmacodynamic actives directly addressing the core pathophysiology (*Salab, Jamun, Gurmar, Suranjan*).</div>
      </div>
      <div style="background:#fffaf0; border:1px solid #feebc8; padding:8px; border-radius:6px;">
        <div style="font-weight:bold; color:#c05621;">Tier 3: Muslih (15-25%)</div>
        <div style="font-size:8.5px; color:#4a5568; margin-top:3px;">Temperament correctives, organ protectors (*Gilo, Chiraita, Halela, Zanjabeel*) eliminating side effects.</div>
      </div>
      <div style="background:#faf5ff; border:1px solid #e9d8fd; padding:8px; border-radius:6px;">
        <div style="font-weight:bold; color:#6b46c1;">Tier 4: Muhawwil (5-10%)</div>
        <div style="font-size:8.5px; color:#4a5568; margin-top:3px;">Bioavailability enhancers, bio-guides & catalysts (*Filfil Siyah, Zafran, Darchini*) carrying actives to deep tissues.</div>
      </div>
    </div>
  </div>

  <div class="section-card">
    <div class="section-header header-navy">Master Directory of 21 Codified Protocols (P-01 to P-21)</div>
    <table class="data-table">
      <thead>
        <tr>
          <th>Code</th>
          <th>Protocol Clinical Indication</th>
          <th>Organ Axis</th>
          <th>Classical Safoof (500g Batch)</th>
          <th>Kit Ref</th>
        </tr>
      </thead>
      <tbody>
""")

    for i in range(1, 22):
        pcode = f"P-{i:02d}"
        pr = protocols_db.get(pcode, {})
        sf = safoof_db.get(pcode, {})
        html.append(f"""
        <tr>
          <td><strong style="color:#2b6cb0;">{pcode}</strong></td>
          <td><strong>{pr.get('name', '')}</strong></td>
          <td><span style="color:#718096; font-style:italic;">{pr.get('organ_axis', '').split('|')[0]}</span></td>
          <td><span style="color:#276749;">{sf.get('name', '').split('/')[0]}</span></td>
          <td><strong style="color:#b7791f;">K-{i:02d}</strong> (p.{i+1})</td>
        </tr>
""")

    html.append("""
      </tbody>
    </table>
  </div>
  <div class="footer-bar">
    <div>CONFIDENTIAL & PROPRIETARY | ZAYVORA MATAB OS</div>
    <div>Page 1 of 24</div>
  </div>
</div>
""")

    # HTML Protocol Pages (P-01 to P-21)
    for p_idx in range(1, 22):
        pcode = f"P-{p_idx:02d}"
        page_num = p_idx + 1
        prot = protocols_db.get(pcode, {})
        safoof = safoof_db.get(pcode, {})
        kit = kits_db.get(f"K-{p_idx:02d}", {})
        ph1 = prot.get('phase1', {})
        ph2 = prot.get('phase2', {})
        ph3 = prot.get('phase3', {})
        labs_h = prot.get('lab_monitoring', {})
        if isinstance(labs_h, list):
            b_lab = labs_h[0] if len(labs_h) > 0 else "CBC, LFT, KFT Screen"
            d30_lab = labs_h[1] if len(labs_h) > 1 else "Primary Biomarker Check"
            d90_lab = labs_h[2] if len(labs_h) > 2 else "Comprehensive Metabolic & Organ Assessment"
        elif isinstance(labs_h, dict):
            b_lab = labs_h.get('baseline', 'CBC, LFT, KFT')
            d30_lab = labs_h.get('day30', 'Primary marker')
            d90_lab = labs_h.get('day90', 'Full metabolic profile')
        else:
            b_lab, d30_lab, d90_lab = "CBC, LFT, KFT", "Biomarker Check", "Metabolic Profile"

        html.append(f"""
<div class="page">
  <div class="header-bar">
    <div class="header-title">ZAYVORA MATAB OS  |  MASTER CLINICAL FORMULARY</div>
    <div class="header-meta">DR. IRFAN ASHRAF - CLINICAL DIRECTOR</div>
  </div>

  <div class="protocol-banner">
    <div class="proto-code">{pcode}</div>
    <div>
      <div class="proto-name">{prot.get('name', '')}</div>
      <div class="proto-meta">
        <strong>Category:</strong> {prot.get('category', '')} &nbsp;|&nbsp;
        <strong>ICD-11:</strong> {prot.get('icd11', 'N/A')} &nbsp;|&nbsp;
        <strong>Primary Humor:</strong> {prot.get('humor', 'Standard')} &nbsp;|&nbsp;
        <strong>Organ Axis:</strong> {prot.get('organ_axis', '')}
      </div>
    </div>
  </div>

  <div class="section-card">
    <div class="section-header header-navy">Classical Matab Safoof: {safoof.get('name', '')}</div>
    <div style="background:#f7fafc; padding:6px 12px; border-bottom:1px solid #e2e8f0; font-size:9.5px; font-weight:600; color:#2b6cb0;">
      Posology: 5g - 6g BID &nbsp;|&nbsp; Default Vehicle (Anupan): {safoof.get('vehicle', 'Lukewarm Water')} &nbsp;|&nbsp; Timing: 30 mins before meals
    </div>
    <table class="data-table">
      <thead>
        <tr>
          <th style="width:25px;">#</th>
          <th>Ingredient & Botanical Identification</th>
          <th>Classical Compounding Tier</th>
          <th style="width:65px; text-align:right;">Weight (g)</th>
          <th style="width:55px; text-align:right;">Share %</th>
        </tr>
      </thead>
      <tbody>
""")

        tot_g = safoof.get('total_grams', 500.0)
        for idx_it, it in enumerate(safoof.get('items', []), start=1):
            tier_class = f"tier-{it['tier'].lower().replace('-', '').replace(' ', '')}"
            clean_name = it['raw_name'].split('[')[0].strip()
            pct = (it['amount'] / tot_g) * 100 if tot_g else 0
            html.append(f"""
        <tr>
          <td>{idx_it}</td>
          <td><strong>{clean_name}</strong></td>
          <td><span class="{tier_class}">{it['tier']}</span></td>
          <td style="text-align:right;"><strong>{it['amount']:.1f} g</strong></td>
          <td style="text-align:right; color:#718096;">{pct:.1f}%</td>
        </tr>
""")

        html.append(f"""
      </tbody>
      <tfoot>
        <tr style="background:#edf2f7; font-weight:bold;">
          <td colspan="3" style="text-align:right; color:#1a365d;">TOTAL COMPOUND BATCH YIELD (STRICT 500g SAFOOF):</td>
          <td style="text-align:right; color:#1a365d;">{tot_g:.1f} g</td>
          <td style="text-align:right; color:#1a365d;">100.0%</td>
        </tr>
      </tfoot>
    </table>
  </div>

  <div class="section-card">
    <div class="section-header header-green">3-Phase Clinical Afaal Cascade (Therapeutic Resolution Timeline)</div>
    <div class="phase-grid">
      <div class="phase-box phase-1">
        <div style="font-weight:bold; color:#22543d; font-size:10px;">Phase 1: Tanqiya ({ph1.get('days', 30)} Days)</div>
        <div style="font-weight:600; color:#4a5568; margin-top:2px;">Focus: Clearance & Detox</div>
        <div style="margin-top:4px;">{ph1.get('action', '')}</div>
        <div style="margin-top:6px; font-weight:bold; color:#2b6cb0;">Target: {ph1.get('target', 'Morbid matter evacuation')}</div>
      </div>
      <div class="phase-box phase-2">
        <div style="font-weight:bold; color:#2b6cb0; font-size:10px;">Phase 2: Tahleel ({ph2.get('days', 60)} Days)</div>
        <div style="font-weight:600; color:#4a5568; margin-top:2px;">Focus: Resolution & Reset</div>
        <div style="margin-top:4px;">{ph2.get('action', '')}</div>
        <div style="margin-top:6px; font-weight:bold; color:#2b6cb0;">Target: {ph2.get('target', 'Pathology resolution')}</div>
      </div>
      <div class="phase-box phase-3">
        <div style="font-weight:bold; color:#975a16; font-size:10px;">Phase 3: Taqwiyat ({ph3.get('days', 90)} Days)</div>
        <div style="font-weight:600; color:#4a5568; margin-top:2px;">Focus: Tonicity & Relapse Prevention</div>
        <div style="margin-top:4px;">{ph3.get('action', '')}</div>
        <div style="margin-top:6px; font-weight:bold; color:#975a16;">Target: {ph3.get('target', 'Consolidation & tissue recovery')}</div>
      </div>
    </div>
  </div>

  <div class="section-card">
    <div class="section-header header-purple">Track 2 Standardized GMP Products & Bundle Kit: {kit.get('code', '')}</div>
    <div style="padding:10px 12px;">
      <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
        <div><strong style="color:#553c9a; font-size:11px;">{kit.get('name', '')}</strong> &nbsp;|&nbsp; <em>{kit.get('indication', '')}</em></div>
        <div style="font-weight:bold; color:#b7791f;">Rs. {kit.get('price_min', 0):,} - Rs. {kit.get('price_max', 0):,} (MRP)</div>
      </div>
      <div style="font-size:9.5px; color:#2d3748;">
        <strong>Product Formulation Stack:</strong> {kit.get('products', '')}
      </div>
    </div>
  </div>

  <div class="section-card">
    <div class="section-header header-amber">Dietary Prescriptions (Ilaj bil Ghiza) & Lifestyle Parhez</div>
    <ul class="rules-list">
      <li><strong>Dietary Inclusions:</strong> Nourishing warm easily digestible broths, boiled vegetables, appropriate whole grains according to Mizaj.</li>
      <li><strong>Strict Abstentions:</strong> Zero refined sugars, deep-fried snacks, processed fast foods, cold refrigerated drinks.</li>
      <li><strong>Lifestyle & Circadian Mandate:</strong> Fixed sleep schedules (10:00 PM - 6:00 AM), daily post-meal ambulation, stress mitigation breathing.</li>
    </ul>
  </div>

  <div class="section-card">
    <div class="section-header header-red">Clinical Safety Firewall & Lab Biomarker Surveillance</div>
    <div style="padding:8px 12px; font-size:9.5px;">
      <div style="color:#9b2c2c; font-weight:bold; margin-bottom:4px;">Safety Red Flag & Contraindications:</div>
      <div>{" ".join(prot.get('warnings', ['Standard clinical surveillance required.']))}</div>
      <div style="color:#4a5568;">Baseline: {b_lab} | Day 30: {d30_lab} | Day 90: {d90_lab}</div>
    </div>
  </div>

  <div class="footer-bar">
    <div>CONFIDENTIAL & PROPRIETARY | ZAYVORA MATAB OS</div>
    <div>Page {page_num} of 24</div>
  </div>
</div>
""")

    # HTML Kit Directory (Page 23)
    html.append(f"""
<div class="page">
  <div class="header-bar">
    <div class="header-title">ZAYVORA MATAB OS  |  MASTER CLINICAL FORMULARY</div>
    <div class="header-meta">DR. IRFAN ASHRAF - CLINICAL DIRECTOR</div>
  </div>

  <div class="section-card">
    <div class="section-header header-navy">Master Codified Protocol Kits Directory (K-01 to K-21)</div>
    <table class="data-table">
      <thead>
        <tr>
          <th>Kit Code</th>
          <th>Commercial Title</th>
          <th>Included Formulations Stack</th>
          <th>Target MRP (INR)</th>
          <th>Regulatory Track</th>
        </tr>
      </thead>
      <tbody>
""")

    for k_idx in range(1, 22):
        k_code = f"K-{k_idx:02d}"
        kt = kits_db.get(k_code, {})
        html.append(f"""
        <tr>
          <td><strong style="color:#2b6cb0;">{k_code}</strong> <span style="font-size:8px; color:#718096;">(P-{k_idx:02d})</span></td>
          <td><strong>{kt.get('name', '')}</strong><br><span style="font-size:8.5px; color:#718096;">{kt.get('indication', '')}</span></td>
          <td><span style="color:#276749;">{kt.get('products', '')}</span></td>
          <td><strong style="color:#b7791f;">Rs. {kt.get('price_min', 0):,} - {kt.get('price_max', 0):,}</strong></td>
          <td><span style="font-size:8.5px; color:#4a5568;">{kt.get('track', 'AYUSH Classical')}</span></td>
        </tr>
""")

    html.append("""
      </tbody>
    </table>
  </div>
  <div class="footer-bar">
    <div>CONFIDENTIAL & PROPRIETARY | ZAYVORA MATAB OS</div>
    <div>Page 23 of 24</div>
  </div>
</div>
""")

    # HTML Page 24: Safety Firewall & Attestation
    html.append("""
<div class="page">
  <div class="header-bar">
    <div class="header-title">ZAYVORA MATAB OS  |  MASTER CLINICAL FORMULARY</div>
    <div class="header-meta">DR. IRFAN ASHRAF - CLINICAL DIRECTOR</div>
  </div>

  <div class="section-card">
    <div class="section-header header-navy">1. Good Compounding Practices for Matab Safoof</div>
    <ul class="rules-list">
      <li><strong>Sieve Calibration:</strong> All botanical raw materials must be pulverized to pass through Sieve Mesh #80 to #100.</li>
      <li><strong>Moisture Limits:</strong> Finished batches must have < 8.0% w/w moisture content to prevent bacterial/fungal degradation.</li>
      <li><strong>Kushta Calcinations:</strong> Mineral Kushtas must undergo verified classical 7-fold herbal juice calcinations prior to incorporation.</li>
      <li><strong>Packaging & Stability:</strong> Amber pharmaceutical glass or food-grade triple-layer HDPE containers protected from UV light.</li>
    </ul>
  </div>

  <div class="section-card">
    <div class="section-header header-red">2. The Safety Firewall: Critical Herb-Drug Interactions</div>
    <table class="data-table">
      <thead>
        <tr>
          <th>Botanical / Compound</th>
          <th>Interacting Pharmaceutical</th>
          <th>Severity</th>
          <th>Clinical Directive</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>Guggul (Commiphora mukul)</strong></td>
          <td>Warfarin / Anticoagulants</td>
          <td><span style="color:#9b2c2c; font-weight:bold;">HIGH</span></td>
          <td>Additive antiplatelet effect. Discontinue 7 days before surgical procedures.</td>
        </tr>
        <tr>
          <td><strong>Asgandh (Withania somnifera)</strong></td>
          <td>Levothyroxine</td>
          <td><span style="color:#c05621; font-weight:bold;">MODERATE</span></td>
          <td>Additive thyroid stimulation. Monitor Free T3/T4 to avoid thyrotoxic symptoms.</td>
        </tr>
        <tr>
          <td><strong>Mulethi (Glycyrrhiza glabra)</strong></td>
          <td>Antihypertensives / Diuretics</td>
          <td><span style="color:#9b2c2c; font-weight:bold;">HIGH</span></td>
          <td>Inhibits 11-beta-HSD2, causing sodium retention & hypokalemia. Avoid in severe HTN.</td>
        </tr>
        <tr>
          <td><strong>Aqarqarha (Anacyclus pyrethrum)</strong></td>
          <td>Hypertensive Crisis</td>
          <td><span style="color:#9b2c2c; font-weight:bold;">CONTRAINDICATED</span></td>
          <td>Vaso-stimulant effect. Prohibited if systolic BP > 160 mmHg or arrhythmia present.</td>
        </tr>
        <tr>
          <td><strong>Piperine (Filfil Siyah)</strong></td>
          <td>CYP3A4 Substrate Drugs</td>
          <td><span style="color:#c05621; font-weight:bold;">MODERATE</span></td>
          <td>Inhibits CYP3A4 & P-gp, elevating systemic pharmaceutical drug concentrations.</td>
        </tr>
      </tbody>
    </table>
  </div>

  <div class="section-card">
    <div class="section-header header-navy">3. Clinical Attestation & Ratification</div>
    <div style="padding:14px; font-size:10px; line-height:1.6; background:#f8fafc;">
      <p style="margin:0 0 10px 0;">
        I hereby certify and solemnly affirm that the formulations, compounding weights, posology regimens,
        and therapeutic cascades detailed across Protocols P-01 through P-21 in this compendium have been
        compiled in rigorous accordance with the classical canons of Unani Tibb (Kitab al-Kulliyat, Al-Qanun fi al-Tibb)
        and reconciled with modern molecular pharmacognosy, biomarker thresholds, and official Ayush / FSSAI safety directives.
        These protocols constitute the official clinical operating standard for all consultations conducted within Zayvora Matab OS.
      </p>
      <div style="display:flex; justify-content:space-between; align-items:flex-end; margin-top:20px; border-top:1px solid #cbd5e0; padding-top:12px;">
        <div>
          <div style="font-weight:bold; font-size:12px; color:#1a365d;">DR. IRFAN ASHRAF, BUMS, MD (Unani)</div>
          <div style="font-size:9.5px; color:#718096;">Chief Physician & Clinical Director</div>
          <div style="font-size:9.5px; color:#718096;">Zayvora Matab Clinical Systems & Research</div>
          <div style="font-size:9.5px; color:#b7791f; font-weight:bold; margin-top:2px;">Ratified: March 2026</div>
        </div>
        <div style="border:2px solid #2b6cb0; padding:8px 14px; border-radius:6px; text-align:center;">
          <div style="font-weight:bold; font-size:10px; color:#2b6cb0;">ZAYVORA MATAB OS</div>
          <div style="font-size:8.5px; color:#b7791f; font-weight:bold;">OFFICIAL PHARMACOPOEIA</div>
          <div style="font-size:8.5px; color:#276749; font-weight:bold;">VALIDATED & RATIFIED</div>
          <div style="font-size:8px; color:#718096; font-family:monospace;">Ref: ZAY-PHARM-2026-v2.1</div>
        </div>
      </div>
    </div>
  </div>

  <div class="footer-bar">
    <div>CONFIDENTIAL & PROPRIETARY | ZAYVORA MATAB OS</div>
    <div>Page 24 of 24</div>
  </div>
</div>
</body>
</html>
""")

    with open(html_file, 'w') as f:
        f.write("".join(html))
    print(f"Generated HTML compendium: {html_file}")

if __name__ == '__main__':
    build_pdf_document()
