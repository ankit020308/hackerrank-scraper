#!/usr/bin/env python3
"""
SRM eLab Scraper — PDF Output
------------------------------
Scrapes all Level 2 & Level 3 solved questions across all registered
courses and exports a clean PDF report.

Usage: python3 elab_scraper.py
"""

import requests
import time
import sys
import json
import jwt as pyjwt          # pip install PyJWT
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT

BASE_URL      = "https://dld.srmist.edu.in/ktretelab2023/elabserver"
API_KEY       = "john"          # extracted from eLab JS bundle
TARGET_LEVELS = {2, 3}

# ── Colors ────────────────────────────────────────────────────────────────────
DARK_BLUE  = colors.HexColor("#0A3D62")
MID_BLUE   = colors.HexColor("#1A5276")
LEVEL2_BG  = colors.HexColor("#FFF3CD")
LEVEL2_FG  = colors.HexColor("#856404")
LEVEL3_BG  = colors.HexColor("#F8D7DA")
LEVEL3_FG  = colors.HexColor("#721C24")
COURSE_BG  = colors.HexColor("#D6EAF8")
ALT_ROW    = colors.HexColor("#F8F9FA")
WHITE      = colors.white
LINK_COLOR = colors.HexColor("#0563C1")


# ── Auth ──────────────────────────────────────────────────────────────────────

def login(session, username, password):
    """Login with the correct eLab API payload and return (token_str, user_dict)."""
    print("Logging in...")
    resp = session.post(
        f"{BASE_URL}/ict/login",
        json={"USER_ID": username, "PASSWORD": password, "KEY": API_KEY},
        headers={"Content-Type": "application/json"},
    )
    if resp.status_code != 200:
        print(f"  HTTP {resp.status_code}: {resp.text[:300]}")
        return None, None

    data = resp.json()
    if data.get("Status") != 1:
        print(f"  Login failed: {json.dumps(data, indent=2)[:400]}")
        return None, None

    # token comes back as  "Bearer :eyJ..."  — use it verbatim as Authorization header
    full_token = data["token"]          # e.g. "Bearer :eyJhbGci..."
    session.headers.update({"Authorization": full_token})

    # Decode JWT to get user object (no verify — we just need the payload fields)
    jwt_part = full_token.split(":")[-1].strip()
    try:
        user = pyjwt.decode(jwt_part, options={"verify_signature": False})
    except Exception:
        # Fallback: build user dict from login response or minimal fields
        user = {"USER_ID": username, "ROLE": "S"}

    print(f"  Logged in as {user.get('FIRST_NAME','')} {user.get('LAST_NAME','')} ({username})")
    return full_token, user


# ── Courses ───────────────────────────────────────────────────────────────────

def get_registered_courses(session, user):
    """POST /ict/student/home/registeredcourses — returns list of course dicts."""
    print("\nFetching registered courses...")
    resp = session.post(
        f"{BASE_URL}/ict/student/home/registeredcourses",
        json={"info": user, "KEY": API_KEY},
    )
    if resp.status_code != 200:
        print(f"  HTTP {resp.status_code}: {resp.text[:200]}")
        return []
    data = resp.json()
    courses = data.get("courses", [])
    print(f"  Found {len(courses)} course(s)")
    return courses


# ── Flare Tree Parser ─────────────────────────────────────────────────────────

def collect_solved_sequence_ids(flare, target_levels):
    """
    Walk the nested flare tree and return list of (sequence_id, level_num)
    for every node with status==2 and level in target_levels.

    Tree shape:
      flare{name, children:[
        topic{children:[
          L1_q{level:"1", name:SEQ_ID, status:N, children:[
            L2_q{level:"2", name:SEQ_ID, status:N, children:[
              L3_q{level:"3", name:SEQ_ID, status:N}   ← leaf
            ]}
          ]}
        ]}
      ]}

    L2 nodes have children (their L3s), so we capture ANY node whose level
    is in target_levels and status == 2 — do NOT restrict to leaves only.
    Then we recurse into children as well (to also catch L3s inside L2s).
    """
    results = []

    def walk(node):
        level  = node.get("level")
        status = node.get("status", 0)
        seq_id = node.get("name")

        if level:
            try:
                level_num = int(str(level))
            except (ValueError, TypeError):
                level_num = None

            if level_num in target_levels and status == 2 and seq_id is not None:
                results.append((int(seq_id), level_num))

        for child in node.get("children", []):
            walk(child)

    walk(flare)
    return results


# ── Question Info ─────────────────────────────────────────────────────────────

def get_question_name(session, user, course, seq_id):
    """POST /ict/student/questionview/getinfo → returns Q_ID (e.g. C_REGULAR_SET1_60)."""
    resp = session.post(
        f"{BASE_URL}/ict/student/questionview/getinfo",
        json={
            "ROLE":        user.get("ROLE", "S"),
            "info":        user,
            "course":      course,
            "SEQUENCE_ID": seq_id,
            "KEY":         API_KEY,
        },
    )
    if resp.status_code == 200:
        d = resp.json()
        if d.get("Status") == 1:
            sd = d.get("studentData", {})
            qd = d.get("questionData", {})
            # Q_ID is the most readable identifier (e.g. "C_REGULAR_SET1_60")
            q_id      = sd.get("Q_ID") or ""
            sess_name = qd.get("SESSION_NAME") or sd.get("SESSION_NAME") or ""
            seq_label = qd.get("SEQ_ID") or seq_id
            if q_id:
                return str(q_id)
            if sess_name:
                return f"{sess_name} #{seq_label}"
    return f"SEQ-{seq_id}"


# ── Scraper ───────────────────────────────────────────────────────────────────

def scrape_solved(session, user, courses):
    print("\nScraping Level 2 & Level 3 solved questions...")
    solved = []

    for c in courses:
        course_id   = c.get("COURSE_ID")
        course_name = c.get("TITLE") or c.get("COURSE_NAME") or str(course_id)

        # Quick skip: if the course has 0 solved L2+L3, skip API call
        l2_count = c.get("LEVEL2", 0) or 0
        l3_count = c.get("LEVEL3", 0) or 0
        if l2_count + l3_count == 0:
            print(f"\n  Course: {course_name} — no L2/L3 solved, skipping")
            continue

        print(f"\n  Course: {course_name} (L2={l2_count}, L3={l3_count})")

        course_obj = {"COURSE_ID": course_id, "COURSE_NAME": c.get("COURSE_NAME", "")}

        resp = session.post(
            f"{BASE_URL}/ict/student/courseview/getcourseinfo",
            json={"info": user, "course": course_obj, "KEY": API_KEY},
        )
        if resp.status_code != 200 or resp.json().get("Status") != 1:
            print(f"    Could not fetch course info (HTTP {resp.status_code})")
            continue

        flare = resp.json().get("flare", {})
        seq_ids = collect_solved_sequence_ids(flare, TARGET_LEVELS)
        print(f"    {len(seq_ids)} solved L2/L3 sequence IDs found in flare")

        for seq_id, level_num in seq_ids:
            q_name = str(get_question_name(session, user, course_obj, seq_id))
            url = (
                f"https://dld.srmist.edu.in/ktretelab2023/#/ktretelab2023/student/"
                f"courseview/{course_id}/questionview/{seq_id}"
            )
            solved.append({
                "course": course_name,
                "level":  f"Level {level_num}",
                "name":   q_name,
                "seq_id": seq_id,
                "url":    url,
            })
            print(f"    + Level {level_num}: {q_name} (SEQ {seq_id})")
            time.sleep(0.2)

    return solved


# ── PDF Builder ───────────────────────────────────────────────────────────────

def build_pdf(problems, username, path):
    doc = SimpleDocTemplate(
        path,
        pagesize=A4,
        rightMargin=15*mm, leftMargin=15*mm,
        topMargin=15*mm,   bottomMargin=15*mm,
        title="SRM eLab — Solved Questions",
    )

    styles = getSampleStyleSheet()
    story  = []

    # ── Title block ──────────────────────────────────────────────────────────
    title_style = ParagraphStyle(
        "Title", fontSize=18, textColor=WHITE,
        alignment=TA_CENTER, fontName="Helvetica-Bold", spaceAfter=4,
    )
    sub_style = ParagraphStyle(
        "Sub", fontSize=10, textColor=colors.HexColor("#BDC3C7"),
        alignment=TA_CENTER, fontName="Helvetica",
    )

    title_table = Table(
        [[Paragraph("SRM eLab — Solved Questions", title_style)],
         [Paragraph(f"Student ID: {username}  |  Level 2 &amp; Level 3  |  Easy Excluded", sub_style)]],
        colWidths=[180*mm],
    )
    title_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), DARK_BLUE),
        ("TOPPADDING",    (0,0), (-1,-1), 14),
        ("BOTTOMPADDING", (0,0), (-1,-1), 14),
        ("LEFTPADDING",   (0,0), (-1,-1), 10),
        ("RIGHTPADDING",  (0,0), (-1,-1), 10),
        ("ROUNDEDCORNERS", [6]),
    ]))
    story.append(title_table)
    story.append(Spacer(1, 8*mm))

    # ── Summary block ────────────────────────────────────────────────────────
    courses_unique = sorted(set(p["course"] for p in problems))
    l2 = sum(1 for p in problems if p["level"] == "Level 2")
    l3 = sum(1 for p in problems if p["level"] == "Level 3")

    summary_data = [
        [Paragraph("<b>Total Solved</b>", styles["Normal"]), str(len(problems))],
        [Paragraph("<b>Level 2</b>", styles["Normal"]),      str(l2)],
        [Paragraph("<b>Level 3</b>", styles["Normal"]),      str(l3)],
    ]
    for c in courses_unique:
        cnt = sum(1 for p in problems if p["course"] == c)
        summary_data.append([Paragraph(f"  {c}", styles["Normal"]), str(cnt)])

    summary_table = Table(summary_data, colWidths=[120*mm, 30*mm])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  COURSE_BG),
        ("BACKGROUND",    (0,1), (-1,1),  LEVEL2_BG),
        ("BACKGROUND",    (0,2), (-1,2),  LEVEL3_BG),
        ("FONTSIZE",      (0,0), (-1,-1), 9),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ("GRID",          (0,0), (-1,-1), 0.5, colors.HexColor("#CCCCCC")),
        ("ALIGN",         (1,0), (1,-1),  "CENTER"),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 8*mm))
    story.append(HRFlowable(width="100%", thickness=1, color=DARK_BLUE))
    story.append(Spacer(1, 5*mm))

    # ── Questions by course ──────────────────────────────────────────────────
    header_style = ParagraphStyle(
        "CourseHdr", fontSize=12, textColor=WHITE,
        fontName="Helvetica-Bold", leftIndent=4,
    )
    q_name_style = ParagraphStyle(
        "QName", fontSize=9, fontName="Helvetica", leading=12,
    )
    link_style = ParagraphStyle(
        "Link", fontSize=8, textColor=LINK_COLOR,
        fontName="Helvetica", leading=10,
    )

    problems_sorted = sorted(problems, key=lambda p: (p["course"], p["level"], p["name"]))

    for course in courses_unique:
        course_probs = [p for p in problems_sorted if p["course"] == course]
        if not course_probs:
            continue

        # Course header
        hdr = Table(
            [[Paragraph(f"{course}  ({len(course_probs)} solved)", header_style)]],
            colWidths=[180*mm],
        )
        hdr.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), MID_BLUE),
            ("TOPPADDING",    (0,0), (-1,-1), 7),
            ("BOTTOMPADDING", (0,0), (-1,-1), 7),
            ("LEFTPADDING",   (0,0), (-1,-1), 10),
        ]))
        story.append(hdr)
        story.append(Spacer(1, 2*mm))

        # Table header row
        col_header = Table(
            [["#", "Question Name", "Level", "SEQ ID", "Link"]],
            colWidths=[10*mm, 95*mm, 20*mm, 15*mm, 40*mm],
        )
        col_header.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), DARK_BLUE),
            ("TEXTCOLOR",     (0,0), (-1,-1), WHITE),
            ("FONTNAME",      (0,0), (-1,-1), "Helvetica-Bold"),
            ("FONTSIZE",      (0,0), (-1,-1), 9),
            ("ALIGN",         (0,0), (-1,-1), "CENTER"),
            ("TOPPADDING",    (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ]))
        story.append(col_header)

        # Question rows
        for idx, p in enumerate(course_probs):
            lv_bg = LEVEL2_BG if p["level"] == "Level 2" else LEVEL3_BG
            lv_fg = LEVEL2_FG if p["level"] == "Level 2" else LEVEL3_FG
            row_bg = ALT_ROW if idx % 2 == 0 else WHITE

            lv_style = ParagraphStyle(
                "Lv", fontSize=8, fontName="Helvetica-Bold",
                textColor=lv_fg, alignment=TA_CENTER,
            )

            row = Table(
                [[
                    Paragraph(str(idx + 1), ParagraphStyle("N", fontSize=8, alignment=TA_CENTER)),
                    Paragraph(p["name"], q_name_style),
                    Paragraph(p["level"], lv_style),
                    Paragraph(str(p["seq_id"]), ParagraphStyle("S", fontSize=8, alignment=TA_CENTER)),
                    Paragraph(f'<link href="{p["url"]}"><u>Open →</u></link>', link_style),
                ]],
                colWidths=[10*mm, 95*mm, 20*mm, 15*mm, 40*mm],
            )
            row.setStyle(TableStyle([
                ("BACKGROUND",    (0,0), (-1,-1), row_bg),
                ("BACKGROUND",    (2,0), (2,0),   lv_bg),
                ("TOPPADDING",    (0,0), (-1,-1), 4),
                ("BOTTOMPADDING", (0,0), (-1,-1), 4),
                ("LEFTPADDING",   (0,0), (-1,-1), 5),
                ("RIGHTPADDING",  (0,0), (-1,-1), 5),
                ("LINEBELOW",     (0,0), (-1,-1), 0.3, colors.HexColor("#DDDDDD")),
                ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ]))
            story.append(row)

        story.append(Spacer(1, 6*mm))

    # ── Footer note ───────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(
        "Generated by SRM eLab Scraper  •  Level 2 🟡  Level 3 🔴",
        ParagraphStyle("Footer", fontSize=8, textColor=colors.grey, alignment=TA_CENTER),
    ))

    doc.build(story)
    print(f"Saved: {path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 55)
    print("  SRM eLab Scraper — Level 2 & Level 3  →  PDF")
    print("=" * 55)
    print()

    username = input("eLab Username (your SRM ID e.g. 636531989981): ").strip()
    password = input("Password: ").strip()

    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Accept":       "application/json",
        "Origin":       "https://dld.srmist.edu.in",
        "Referer":      "https://dld.srmist.edu.in/ktretelab2023/",
        "User-Agent":   "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    })

    token, user = login(session, username, password)
    if not token:
        print("\nLogin failed.")
        sys.exit(1)

    courses = get_registered_courses(session, user)
    if not courses:
        print("No courses found.")
        sys.exit(0)

    solved = scrape_solved(session, user, courses)
    if not solved:
        print("\nNo Level 2 or Level 3 solved questions found.")
        sys.exit(0)

    output = "elab_solved.pdf"
    build_pdf(solved, username, output)

    print(f"\n{'='*55}")
    print(f"  Done! {len(solved)} questions exported to {output}")
    print(f"  Level 2: {sum(1 for p in solved if p['level'] == 'Level 2')}")
    print(f"  Level 3: {sum(1 for p in solved if p['level'] == 'Level 3')}")
    print(f"{'='*55}")
    print(f"\nOpen with:  open {output}")


if __name__ == "__main__":
    main()
