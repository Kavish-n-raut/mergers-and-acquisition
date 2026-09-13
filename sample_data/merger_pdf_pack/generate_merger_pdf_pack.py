from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from pypdf import PdfWriter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "pdfs"
COMBINED_PDF = BASE_DIR / "Aster_Northstar_Merger_Document_Pack_All_In_One.pdf"
ZIP_PATH = BASE_DIR / "Aster_Northstar_Merger_Document_Pack.zip"

DEAL = {
    "acquirer": "Aster Capital Technologies Inc.",
    "target": "Northstar Process Automation Pvt. Ltd.",
    "combined": "Aster Northstar Automation Group",
    "announcement_date": "2026-01-15",
    "loi_date": "2026-01-22",
    "signing_date": "2026-02-18",
    "closing_date": "2026-03-31",
    "purchase_price": "USD 86.0 million enterprise value",
    "structure": "100 percent cash acquisition with 12 percent management rollover equity",
    "status": "Closed and integrated under common ownership",
}


styles = getSampleStyleSheet()
styles.add(
    ParagraphStyle(
        name="DocTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#111827"),
        spaceAfter=10,
    )
)
styles.add(
    ParagraphStyle(
        name="DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#4B5563"),
        alignment=TA_CENTER,
        spaceAfter=18,
    )
)
styles.add(
    ParagraphStyle(
        name="Section",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=10,
        spaceAfter=6,
    )
)
styles.add(
    ParagraphStyle(
        name="Body",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#111827"),
        spaceAfter=7,
    )
)
styles.add(
    ParagraphStyle(
        name="Small",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#6B7280"),
    )
)


def safe_paragraph(text: str, style_name: str = "Body") -> Paragraph:
    escaped = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )
    return Paragraph(escaped, styles[style_name])


def draw_footer(canvas, doc):
    canvas.saveState()
    width, _height = A4
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#6B7280"))
    canvas.drawString(
        doc.leftMargin,
        0.38 * inch,
        "FICTIONAL MVP SAMPLE DATA - Not legal, tax, investment, or accounting advice.",
    )
    canvas.drawRightString(width - doc.rightMargin, 0.38 * inch, f"Page {doc.page}")
    canvas.restoreState()


def metadata_table(doc_id: str, owner: str, sensitivity: str, date: str) -> Table:
    rows = [
        ["Document ID", doc_id, "Deal Status", DEAL["status"]],
        ["Acquirer", DEAL["acquirer"], "Target", DEAL["target"]],
        ["Owner", owner, "Sensitivity", sensitivity],
        ["Date", date, "Close Date", DEAL["closing_date"]],
    ]
    table = Table(rows, colWidths=[1.15 * inch, 2.4 * inch, 1.15 * inch, 2.4 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F3F4F6")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#111827")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D1D5DB")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def make_table(headers: list[str], rows: list[list[str]], widths: list[float] | None = None) -> Table:
    data = [[safe_paragraph(h, "Small") for h in headers]]
    data.extend([[safe_paragraph(str(cell), "Small") for cell in row] for row in rows])
    col_widths = widths or [6.9 * inch / len(headers)] * len(headers)
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D1D5DB")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def section(title: str, body: str | None = None, table: Table | None = None):
    flow = [safe_paragraph(title, "Section")]
    if body:
        for para in body.strip().split("\n\n"):
            flow.append(safe_paragraph(para.strip(), "Body"))
    if table is not None:
        flow.append(table)
        flow.append(Spacer(1, 8))
    return flow


def build_pdf(filename: str, title: str, doc_id: str, owner: str, sensitivity: str, date: str, blocks: list):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / filename
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=0.62 * inch,
        rightMargin=0.62 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.7 * inch,
        title=title,
        author="Codex synthetic sample data generator",
    )
    story = [
        safe_paragraph(title, "DocTitle"),
        safe_paragraph(
            f"{DEAL['acquirer']} acquisition of {DEAL['target']} - synthetic completed merger file",
            "DocSubtitle",
        ),
        metadata_table(doc_id, owner, sensitivity, date),
        Spacer(1, 12),
    ]
    for block in blocks:
        if block == "PAGE_BREAK":
            story.append(PageBreak())
        else:
            story.extend(block)
    doc.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)
    return path


def doc_definitions():
    return [
        {
            "filename": "00_Data_Room_Index_and_Deal_Map.pdf",
            "title": "Data Room Index and Deal Map",
            "doc_id": "DR-000",
            "owner": "Corporate Development",
            "sensitivity": "Internal - Synthetic",
            "date": "2026-04-03",
            "blocks": [
                section(
                    "Deal Snapshot",
                    (
                        f"{DEAL['acquirer']} acquired {DEAL['target']} in a closed transaction completed on "
                        f"{DEAL['closing_date']}. The transaction was structured as {DEAL['structure']} with a headline "
                        f"purchase price of {DEAL['purchase_price']}. This data room pack is fictional sample data designed "
                        "for AI diligence, valuation, regulatory, closing, and post-merger integration testing."
                    ),
                ),
                section(
                    "Document Inventory",
                    table=make_table(
                        ["ID", "Document", "Primary Module", "Use In MVP"],
                        [
                            ["DR-001", "Acquirer company profile", "M1/M7", "Strategic rationale and buyer profile"],
                            ["DR-002", "Target company profile", "M1/M7", "Target overview and segmentation"],
                            ["DR-003", "Acquirer three-year financials", "M2/M3", "Baseline financial model"],
                            ["DR-004", "Target three-year financials", "M2/M3", "Normalization and valuation"],
                            ["DR-005", "Normalized EBITDA adjustments", "M2/M3", "Quality of earnings checks"],
                            ["DR-006", "Executed NDA", "M2", "Legal document parsing"],
                            ["DR-007", "Executed LOI", "M3/M5", "Deal terms and exclusivity"],
                            ["DR-008", "Merger agreement", "M4/M7", "Representations and closing conditions"],
                            ["DR-009", "Disclosure schedules", "M4", "Exception finding and risk extraction"],
                            ["DR-010", "Diligence risk matrix", "M4/M5", "Severity scoring and tactics"],
                            ["DR-011", "Customer contract", "M4", "Change-of-control and concentration risk"],
                            ["DR-012", "Supplier agreement", "M4", "Termination and consent risk"],
                            ["DR-013", "Employment and retention agreements", "M4/M8", "Key person and HR risk"],
                            ["DR-014", "IP and technology stack summary", "M4/M8", "IP ownership and system overlap"],
                            ["DR-015", "Litigation and compliance memo", "M4/M7", "Legal and sanctions exposure"],
                            ["DR-016", "Regulatory clearance memo", "M7", "HSR, CCI, and foreign investment checks"],
                            ["DR-017", "Financing commitment and capital stack", "M6", "LBO and financing model"],
                            ["DR-018", "Board approval minutes", "M7", "Approval trail"],
                            ["DR-019", "Closing checklist and funds flow", "M7", "Closing conditions"],
                            ["DR-020", "PMI 100-day plan and synergy tracker", "M8", "Post-close integration tracking"],
                        ],
                        [0.65 * inch, 2.15 * inch, 1.0 * inch, 3.1 * inch],
                    ),
                ),
                section(
                    "MVP Testing Notes",
                    "Use these PDFs to test upload, classification, search, clause extraction, severity scoring, valuation prompts, negotiation tactics, regulatory checklist generation, and PMI tracking. The pack intentionally includes risk clauses such as change-of-control consent, customer concentration, key person retention, data privacy remediation, delayed tax filings, and supplier termination rights.",
                ),
            ],
        },
        {
            "filename": "01_Acquirer_Company_Profile_Aster.pdf",
            "title": "Acquirer Company Profile - Aster Capital Technologies Inc.",
            "doc_id": "DR-001",
            "owner": "Strategy Team",
            "sensitivity": "Internal - Synthetic",
            "date": "2026-01-08",
            "blocks": [
                section(
                    "Business Overview",
                    "Aster Capital Technologies Inc. is a Delaware corporation providing workflow software, analytics dashboards, and AI-assisted compliance tooling for mid-market financial institutions. The company operates from New York, London, Bengaluru, and Singapore. Aster pursued Northstar to expand automation capabilities in loan operations, vendor onboarding, and regulatory workflow orchestration.",
                ),
                section(
                    "Strategic Rationale",
                    table=make_table(
                        ["Rationale", "Details", "Expected Impact"],
                        [
                            ["Product adjacency", "Northstar adds robotic process automation modules for loan onboarding and reconciliation.", "Accelerates roadmap by 18 months"],
                            ["India engineering base", "Target has 142 engineers in Bengaluru and Pune with automation domain knowledge.", "Reduces build cost and increases delivery velocity"],
                            ["Customer cross-sell", "Aster can sell Northstar workflow modules into 94 banking customers.", "USD 9.4M revenue synergy by year 3"],
                            ["Margin expansion", "Consolidated cloud infrastructure and vendor procurement.", "USD 3.1M annual cost synergy by year 2"],
                        ],
                        [1.35 * inch, 3.4 * inch, 2.1 * inch],
                    ),
                ),
                section(
                    "Management Team",
                    table=make_table(
                        ["Name", "Role", "Deal Role", "Notes"],
                        [
                            ["Maya Shah", "Chief Executive Officer", "Executive sponsor", "Board-approved acquisition thesis"],
                            ["Daniel Brooks", "Chief Financial Officer", "Valuation owner", "Approved financing model and IRR hurdle"],
                            ["Priya Menon", "Chief Product Officer", "Integration lead", "Owns product roadmap consolidation"],
                            ["Carlos Vega", "General Counsel", "Legal owner", "Managed regulatory and closing checklist"],
                        ],
                        [1.35 * inch, 1.35 * inch, 1.55 * inch, 2.6 * inch],
                    ),
                ),
                section(
                    "Public-Market Style Metrics",
                    table=make_table(
                        ["Metric", "FY2023", "FY2024", "FY2025"],
                        [
                            ["Revenue", "USD 138.2M", "USD 159.7M", "USD 186.4M"],
                            ["EBITDA", "USD 27.6M", "USD 35.1M", "USD 42.8M"],
                            ["EBITDA Margin", "20.0%", "22.0%", "23.0%"],
                            ["Net Debt", "USD 14.0M", "USD 19.5M", "USD 23.2M"],
                            ["Employees", "612", "701", "784"],
                        ],
                    ),
                ),
            ],
        },
        {
            "filename": "02_Target_Company_Profile_Northstar.pdf",
            "title": "Target Company Profile - Northstar Process Automation Pvt. Ltd.",
            "doc_id": "DR-002",
            "owner": "Target Management",
            "sensitivity": "Confidential - Synthetic",
            "date": "2026-01-10",
            "blocks": [
                section(
                    "Business Overview",
                    "Northstar Process Automation Pvt. Ltd. is a Bengaluru-headquartered automation software company serving banks, non-bank lenders, and insurance administrators. Products include loan file ingestion, KYC exception routing, reconciliations, and automated compliance task queues. The company was founded in 2017 and operated as a founder-led private company before the acquisition.",
                ),
                section(
                    "Revenue Mix",
                    table=make_table(
                        ["Segment", "FY2025 Revenue", "Share", "Growth Notes"],
                        [
                            ["Loan operations automation", "INR 142.0 Cr", "46%", "Strong demand from NBFCs and regional banks"],
                            ["KYC and onboarding workflows", "INR 74.4 Cr", "24%", "High retention, moderate implementation cycle"],
                            ["Reconciliation modules", "INR 49.6 Cr", "16%", "Cross-sell potential into Aster base"],
                            ["Professional services", "INR 43.4 Cr", "14%", "Lower margin implementation work"],
                        ],
                        [2.0 * inch, 1.4 * inch, 0.8 * inch, 2.75 * inch],
                    ),
                ),
                section(
                    "Key Customers",
                    "The top five customers represented 41 percent of FY2025 revenue. One customer, Meridian Cooperative Bank, represented 17 percent of revenue and has a change-of-control consent right under its master services agreement. This risk is repeated in the customer contract sample document.",
                ),
                section(
                    "Operational Footprint",
                    table=make_table(
                        ["Location", "Function", "Headcount", "Integration Note"],
                        [
                            ["Bengaluru", "Engineering, Product, Finance", "184", "Primary integration site"],
                            ["Pune", "Implementation and Support", "71", "Potential overlap with Aster support team"],
                            ["Mumbai", "Sales and Customer Success", "38", "Retain local market coverage"],
                            ["Remote", "Contract engineers", "19", "Review IP assignment completeness"],
                        ],
                    ),
                ),
            ],
        },
        {
            "filename": "03_Acquirer_Three_Year_Financials.pdf",
            "title": "Acquirer Three-Year Financials",
            "doc_id": "DR-003",
            "owner": "Aster Finance",
            "sensitivity": "Confidential - Synthetic",
            "date": "2026-01-12",
            "blocks": [
                section(
                    "Income Statement Summary",
                    table=make_table(
                        ["USD millions", "FY2023", "FY2024", "FY2025"],
                        [
                            ["Revenue", "138.2", "159.7", "186.4"],
                            ["Cost of revenue", "(42.8)", "(48.6)", "(55.9)"],
                            ["Gross profit", "95.4", "111.1", "130.5"],
                            ["SG&A", "(45.2)", "(50.8)", "(59.2)"],
                            ["R&D", "(22.6)", "(25.2)", "(28.5)"],
                            ["EBITDA", "27.6", "35.1", "42.8"],
                            ["D&A", "(6.4)", "(7.1)", "(8.3)"],
                            ["EBIT", "21.2", "28.0", "34.5"],
                            ["Net income", "13.9", "18.5", "22.9"],
                        ],
                    ),
                ),
                section(
                    "Balance Sheet and Cash Flow",
                    table=make_table(
                        ["USD millions", "FY2023", "FY2024", "FY2025"],
                        [
                            ["Cash", "18.3", "23.6", "29.1"],
                            ["Total debt", "32.3", "43.1", "52.3"],
                            ["Net debt", "14.0", "19.5", "23.2"],
                            ["Capital expenditures", "(5.8)", "(7.4)", "(8.9)"],
                            ["Unlevered free cash flow", "19.7", "25.4", "31.2"],
                        ],
                    ),
                ),
                section(
                    "Modeling Notes",
                    "Aster's board required that any acquisition meet at least a 15.0 percent base case levered IRR and maintain pro forma net debt below 3.25x combined EBITDA within 24 months of close.",
                ),
            ],
        },
        {
            "filename": "04_Target_Three_Year_Financials.pdf",
            "title": "Target Three-Year Financials",
            "doc_id": "DR-004",
            "owner": "Northstar Finance",
            "sensitivity": "Confidential - Synthetic",
            "date": "2026-01-12",
            "blocks": [
                section(
                    "Income Statement Summary",
                    table=make_table(
                        ["INR crore", "FY2023", "FY2024", "FY2025"],
                        [
                            ["Revenue", "198.0", "247.5", "310.0"],
                            ["Cost of revenue", "(69.3)", "(84.2)", "(105.4)"],
                            ["Gross profit", "128.7", "163.3", "204.6"],
                            ["SG&A", "(58.4)", "(71.5)", "(87.1)"],
                            ["R&D", "(31.7)", "(39.6)", "(48.1)"],
                            ["Reported EBITDA", "38.6", "52.2", "69.4"],
                            ["D&A", "(6.2)", "(7.1)", "(8.8)"],
                            ["EBIT", "32.4", "45.1", "60.6"],
                            ["Net income", "21.0", "29.1", "39.2"],
                        ],
                    ),
                ),
                section(
                    "Customer Concentration and Working Capital",
                    table=make_table(
                        ["Metric", "FY2023", "FY2024", "FY2025"],
                        [
                            ["Top customer revenue share", "13%", "15%", "17%"],
                            ["Top five customer revenue share", "35%", "38%", "41%"],
                            ["Days sales outstanding", "59", "66", "74"],
                            ["Deferred revenue", "INR 21.5 Cr", "INR 29.0 Cr", "INR 36.2 Cr"],
                            ["Net working capital", "INR 18.1 Cr", "INR 21.8 Cr", "INR 28.4 Cr"],
                        ],
                    ),
                ),
                section(
                    "AI Scanner Flags",
                    "Potential issues for diligence models: DSO increased by 15 days over two years; top customer concentration increased to 17 percent; reported EBITDA includes non-recurring implementation revenue catch-up from one enterprise customer.",
                ),
            ],
        },
        {
            "filename": "05_Normalized_EBITDA_Adjustments.pdf",
            "title": "Normalized EBITDA Adjustments and QoE Summary",
            "doc_id": "DR-005",
            "owner": "Financial Diligence",
            "sensitivity": "Confidential - Synthetic",
            "date": "2026-01-20",
            "blocks": [
                section(
                    "Quality of Earnings Summary",
                    "Financial diligence adjusted Northstar's FY2025 reported EBITDA of INR 69.4 crore to normalized EBITDA of INR 62.1 crore. The main negative adjustment relates to non-recurring revenue recognized from a delayed implementation milestone. The main positive adjustment relates to founder compensation above market benchmark.",
                ),
                section(
                    "Adjustment Schedule",
                    table=make_table(
                        ["Adjustment", "INR Cr", "Direction", "Rationale"],
                        [
                            ["Reported EBITDA", "69.4", "Base", "Per management accounts"],
                            ["Non-recurring milestone catch-up", "(9.8)", "Negative", "Revenue relates to FY2024 implementation delay"],
                            ["Founder compensation add-back", "2.1", "Positive", "Above-market compensation eliminated post-close"],
                            ["One-time legal settlement", "1.7", "Positive", "Historic customer dispute settled before close"],
                            ["Cloud migration cost", "(1.3)", "Negative", "Recurring infrastructure cost incorrectly capitalized"],
                            ["Normalized EBITDA", "62.1", "Output", "Used for valuation and LBO model"],
                        ],
                        [2.2 * inch, 0.8 * inch, 1.0 * inch, 2.95 * inch],
                    ),
                ),
                section(
                    "Diligence Conclusion",
                    "The EBITDA adjustment reduced the valuation basis by 10.5 percent. The valuation committee applied the acquisition multiple to normalized EBITDA only and requested a USD 2.0 million specific indemnity for customer receivable collectability.",
                ),
            ],
        },
        {
            "filename": "06_Executed_NDA.pdf",
            "title": "Executed Mutual Non-Disclosure Agreement",
            "doc_id": "DR-006",
            "owner": "Legal",
            "sensitivity": "Legal - Synthetic",
            "date": "2026-01-14",
            "blocks": [
                section(
                    "Parties and Purpose",
                    "This Mutual Non-Disclosure Agreement is entered into by Aster Capital Technologies Inc. and Northstar Process Automation Pvt. Ltd. for the sole purpose of evaluating a possible acquisition, investment, merger, business combination, or other strategic transaction.",
                ),
                section(
                    "Confidential Information",
                    "Confidential Information includes financial statements, customer lists, source code descriptions, pricing schedules, employee compensation data, contracts, regulatory correspondence, product roadmaps, and information disclosed in the virtual data room.",
                ),
                section(
                    "Standstill and Non-Solicitation",
                    "For 18 months after the effective date, neither party shall solicit senior employees of the other party who are introduced through the transaction process, except through general solicitations not targeted at such employees. Aster shall not make a public acquisition proposal without prior written consent unless required by law.",
                ),
                section(
                    "Return or Destruction",
                    "Upon written request, each recipient shall return or destroy Confidential Information within 10 business days, except one archival copy retained by legal counsel for compliance purposes.",
                ),
                section(
                    "Governing Law",
                    "This agreement is governed by the laws of the State of Delaware, except that employment non-solicitation restrictions for India-based personnel shall be interpreted in accordance with applicable Indian law.",
                ),
            ],
        },
        {
            "filename": "07_Executed_LOI.pdf",
            "title": "Executed Letter of Intent",
            "doc_id": "DR-007",
            "owner": "Corporate Development",
            "sensitivity": "Legal - Synthetic",
            "date": DEAL["loi_date"],
            "blocks": [
                section(
                    "Headline Terms",
                    table=make_table(
                        ["Term", "Agreed Position"],
                        [
                            ["Transaction", f"Aster to acquire 100 percent of {DEAL['target']}"],
                            ["Enterprise value", "USD 86.0 million, subject to net debt and working capital adjustments"],
                            ["Structure", "Cash consideration plus 12 percent management rollover equity"],
                            ["Exclusivity", "45 calendar days from LOI execution"],
                            ["Financing", "Cash on hand plus committed senior secured term loan"],
                            ["Target working capital peg", "INR 28.0 crore"],
                            ["Management retention pool", "USD 4.5 million over 24 months"],
                        ],
                        [2.0 * inch, 4.85 * inch],
                    ),
                ),
                section(
                    "Conditions to Signing",
                    "The parties agreed that definitive agreement execution would require satisfactory financial, legal, tax, employment, regulatory, intellectual property, cybersecurity, and customer contract diligence. Aster reserved the right to reduce purchase price or require escrow if diligence identified material risks.",
                ),
                section(
                    "Non-Binding and Binding Provisions",
                    "The valuation, structure, and transaction description are non-binding. Confidentiality, exclusivity, governing law, expenses, and public announcement provisions are binding.",
                ),
            ],
        },
        {
            "filename": "08_Executed_Merger_Agreement.pdf",
            "title": "Executed Merger Agreement",
            "doc_id": "DR-008",
            "owner": "Legal",
            "sensitivity": "Legal - Synthetic",
            "date": DEAL["signing_date"],
            "blocks": [
                section(
                    "Agreement Summary",
                    f"This Merger Agreement was entered into on {DEAL['signing_date']} among {DEAL['acquirer']}, Aster India Holdings Private Limited, and {DEAL['target']}. The transaction closed on {DEAL['closing_date']} after satisfaction or waiver of closing conditions.",
                ),
                section(
                    "Purchase Price Adjustment",
                    "At closing, estimated equity value was calculated as enterprise value minus closing debt, plus closing cash, minus the amount by which closing working capital was below the INR 28.0 crore target peg. A final true-up statement must be delivered within 75 days after closing.",
                ),
                section(
                    "Representations and Warranties",
                    "Seller representations include organization and authority, capitalization, financial statements, absence of undisclosed liabilities, material contracts, intellectual property ownership, data privacy compliance, tax matters, labor and employment, anti-bribery compliance, sanctions compliance, litigation, environmental matters, and brokers fees.",
                ),
                section(
                    "Indemnity and Escrow",
                    table=make_table(
                        ["Item", "Amount", "Survival", "Notes"],
                        [
                            ["General escrow", "USD 6.0M", "18 months", "Covers general representation breaches"],
                            ["Tax escrow", "USD 1.5M", "36 months", "Covers open GST and transfer pricing matters"],
                            ["Customer consent holdback", "USD 2.0M", "12 months", "Released when Meridian consent is delivered"],
                            ["Cyber remediation holdback", "USD 0.8M", "9 months", "Released after SOC 2 remediation evidence"],
                        ],
                    ),
                ),
                section(
                    "Closing Conditions",
                    "Closing conditions included accuracy of representations, no material adverse effect, delivery of required customer and supplier consents, regulatory clearance or non-applicability confirmations, execution of retention agreements, financing availability, board approvals, and delivery of officer certificates.",
                ),
            ],
        },
        {
            "filename": "09_Disclosure_Schedules.pdf",
            "title": "Disclosure Schedules",
            "doc_id": "DR-009",
            "owner": "Seller Counsel",
            "sensitivity": "Legal - Synthetic",
            "date": DEAL["signing_date"],
            "blocks": [
                section(
                    "Schedule 3.6 - Undisclosed Liabilities",
                    "Northstar disclosed an unpaid service tax assessment of INR 1.9 crore relating to FY2022. Management believes the assessment is contestable, but a tax escrow was agreed because final resolution may extend beyond 24 months.",
                ),
                section(
                    "Schedule 3.11 - Material Contracts",
                    table=make_table(
                        ["Contract", "Counterparty", "Issue", "Required Action"],
                        [
                            ["Master Services Agreement", "Meridian Cooperative Bank", "Change-of-control consent", "Consent required before closing or USD 2.0M holdback"],
                            ["Cloud Hosting Agreement", "Nimbus Cloud Services", "Termination for convenience on 60 days notice", "Renegotiate term post-close"],
                            ["Implementation Partner Agreement", "Saffron Systems LLP", "Most-favored pricing clause", "Legal review after pricing harmonization"],
                            ["Senior Loan Agreement", "Eastern Commercial Bank", "Debt repayment at close", "Payoff letter delivered at closing"],
                        ],
                        [1.6 * inch, 1.55 * inch, 1.75 * inch, 1.95 * inch],
                    ),
                ),
                section(
                    "Schedule 3.14 - Intellectual Property",
                    "Two contractors who contributed to the document parsing module executed invention assignment agreements after development work began. Counsel recommended a confirmatory assignment before closing and a special indemnity for pre-close IP ownership claims.",
                ),
                section(
                    "Schedule 3.17 - Employment",
                    "Three senior engineers have 90-day notice periods and retention bonuses triggered by change of control. One product director has a non-compete covenant that may be unenforceable under applicable local law.",
                ),
            ],
        },
        {
            "filename": "10_Diligence_Risk_Matrix.pdf",
            "title": "Diligence Risk Matrix",
            "doc_id": "DR-010",
            "owner": "Diligence Team",
            "sensitivity": "Confidential - Synthetic",
            "date": "2026-02-02",
            "blocks": [
                section(
                    "Risk Matrix",
                    table=make_table(
                        ["Risk", "Category", "Severity", "Timing", "Recommended Response"],
                        [
                            ["Meridian customer consent required", "Customer / Legal", "High", "At close", "Specific holdback and closing covenant"],
                            ["Open GST service tax assessment", "Tax", "Medium", "Post-close", "Tax escrow and seller indemnity"],
                            ["Contractor IP assignment timing gap", "IP", "High", "At signing", "Confirmatory assignments before close"],
                            ["DSO deterioration", "Financial", "Medium", "Post-close", "Working capital true-up and collection covenant"],
                            ["Cloud provider termination right", "Operations", "Medium", "Post-close year 1", "Negotiate extension and migration backup"],
                            ["SOC 2 remediation incomplete", "Cyber / Compliance", "Medium", "Post-close 9 months", "Cyber holdback and remediation plan"],
                            ["Key engineer retention risk", "HR", "High", "At close", "Retention pool and accelerated onboarding"],
                        ],
                        [1.7 * inch, 1.15 * inch, 0.75 * inch, 1.0 * inch, 2.25 * inch],
                    ),
                ),
                section(
                    "Board-Ready Explainability Card Example",
                    "Finding: Meridian Cooperative Bank accounted for 17 percent of FY2025 revenue and has a consent right triggered by change of control. Impact: Loss of the contract would reduce FY2026 revenue by approximately INR 56 crore and reduce normalized EBITDA by approximately INR 13 crore. Recommendation: Require consent before close or hold back USD 2.0 million for 12 months.",
                ),
            ],
        },
        {
            "filename": "11_Material_Customer_Contract.pdf",
            "title": "Material Customer Contract - Meridian Cooperative Bank",
            "doc_id": "DR-011",
            "owner": "Sales Operations",
            "sensitivity": "Customer Contract - Synthetic",
            "date": "2024-07-01",
            "blocks": [
                section(
                    "Contract Summary",
                    "Meridian Cooperative Bank entered into a three-year master services agreement with Northstar for loan operations automation, KYC workflow queues, implementation support, and ongoing platform maintenance.",
                ),
                section(
                    "Commercial Terms",
                    table=make_table(
                        ["Term", "Value"],
                        [
                            ["Annual recurring subscription", "INR 32.0 crore"],
                            ["Implementation services", "INR 9.5 crore over first 12 months"],
                            ["Renewal", "Automatic one-year renewals unless either party gives 90 days notice"],
                            ["Service credits", "Up to 8 percent of annual subscription fees for SLA failure"],
                        ],
                        [2.2 * inch, 4.65 * inch],
                    ),
                ),
                section(
                    "Change-of-Control Clause",
                    "Customer may terminate this Agreement without penalty upon written notice if Northstar undergoes a change of control and the acquiring party is a direct competitor of Customer or materially changes the data hosting location. Customer consent shall not be unreasonably withheld if the acquiring party maintains equivalent security controls and service levels.",
                ),
                section(
                    "Data Security Clause",
                    "Northstar shall maintain ISO 27001 certification or equivalent controls, conduct annual penetration testing, encrypt customer data at rest and in transit, and notify Customer of any material security incident within 48 hours.",
                ),
            ],
        },
        {
            "filename": "12_Supplier_Agreement_Change_of_Control_Risk.pdf",
            "title": "Supplier Agreement - Nimbus Cloud Services",
            "doc_id": "DR-012",
            "owner": "Procurement",
            "sensitivity": "Supplier Contract - Synthetic",
            "date": "2023-09-18",
            "blocks": [
                section(
                    "Agreement Overview",
                    "Nimbus Cloud Services provides hosting, managed Kubernetes clusters, storage, monitoring, and disaster recovery services to Northstar. The agreement runs through 2027 but includes termination and pricing provisions that require integration planning.",
                ),
                section(
                    "Critical Clauses",
                    table=make_table(
                        ["Clause", "Text Summary", "Risk"],
                        [
                            ["Termination for convenience", "Nimbus may terminate non-production environments on 60 days notice after a control transaction.", "Migration pressure post-close"],
                            ["Most-favored pricing", "If Northstar receives better pricing from another hyperscale provider, Nimbus may match pricing before migration.", "May delay procurement synergy"],
                            ["Data residency", "Production data for India banking customers must remain in India data centers.", "Limits cloud consolidation"],
                            ["Assignment", "Assignment requires notice but not prior consent unless service levels materially change.", "Manageable"],
                        ],
                        [1.4 * inch, 3.4 * inch, 2.05 * inch],
                    ),
                ),
                section(
                    "Recommended Deal Response",
                    "Integration team should complete an architecture assessment within 30 days after close and negotiate a 12-month transition services extension before moving customer workloads to Aster's standard infrastructure.",
                ),
            ],
        },
        {
            "filename": "13_Employment_and_Retention_Agreements.pdf",
            "title": "Employment and Retention Agreements",
            "doc_id": "DR-013",
            "owner": "Human Resources",
            "sensitivity": "HR Confidential - Synthetic",
            "date": "2026-02-10",
            "blocks": [
                section(
                    "Key Employee Register",
                    table=make_table(
                        ["Employee", "Role", "Retention Risk", "Retention Package"],
                        [
                            ["Arjun Rao", "CTO", "High", "USD 650K over 24 months plus rollover equity"],
                            ["Meera Iyer", "VP Engineering", "High", "USD 420K over 24 months"],
                            ["Karan Bhat", "Head of Customer Success", "Medium", "USD 180K over 18 months"],
                            ["Sonal Kapoor", "Finance Controller", "Medium", "USD 110K over 12 months"],
                        ],
                    ),
                ),
                section(
                    "Change-of-Control Benefits",
                    "The CTO and VP Engineering each receive accelerated vesting of 50 percent of unvested phantom equity if employment is terminated without cause within 12 months after close. Retention agreements replace phantom equity with cash retention and rollover equity.",
                ),
                section(
                    "Non-Compete and Non-Solicitation",
                    "Senior management agreements include a 12-month non-solicitation covenant covering customers and employees. Non-compete restrictions are subject to enforceability review and should not be relied upon as the primary retention mechanism.",
                ),
                section(
                    "PMI Note",
                    "The top integration risk is engineering retention. Product roadmap continuity depends on retaining at least 80 percent of the workflow automation engineering team through day 180.",
                ),
            ],
        },
        {
            "filename": "14_IP_and_Technology_Stack_Summary.pdf",
            "title": "IP and Technology Stack Summary",
            "doc_id": "DR-014",
            "owner": "Technology Diligence",
            "sensitivity": "Confidential - Synthetic",
            "date": "2026-02-05",
            "blocks": [
                section(
                    "Owned IP",
                    "Northstar owns source code repositories for workflow orchestration, document ingestion, KYC task routing, reconciliation matching, audit logging, and customer admin dashboards. Code is hosted in private Git repositories with branch protection and pull request review requirements.",
                ),
                section(
                    "IP Assignment Review",
                    table=make_table(
                        ["Contributor Type", "Population", "Assignment Status", "Risk"],
                        [
                            ["Employees", "293", "Standard employment invention assignment executed", "Low"],
                            ["Contract engineers", "19", "17 confirmed, 2 confirmatory assignments delivered before close", "Medium"],
                            ["Implementation partners", "4 firms", "No source code contribution permitted under SOW", "Low"],
                            ["Open-source packages", "214 packages", "3 copyleft packages used in internal tools only", "Medium"],
                        ],
                    ),
                ),
                section(
                    "Technology Stack Compatibility",
                    table=make_table(
                        ["Layer", "Aster", "Northstar", "Integration Implication"],
                        [
                            ["Frontend", "React", "React", "High compatibility"],
                            ["Backend", "Python/FastAPI", "Java/Spring and Python services", "Moderate integration effort"],
                            ["Database", "PostgreSQL", "PostgreSQL and MongoDB", "Schema consolidation needed"],
                            ["Cloud", "AWS", "AWS and local India region workloads", "Data residency constraints"],
                            ["Auth", "Okta", "Keycloak", "SSO migration required"],
                        ],
                        [1.0 * inch, 1.25 * inch, 1.7 * inch, 2.9 * inch],
                    ),
                ),
            ],
        },
        {
            "filename": "15_Litigation_and_Compliance_Memo.pdf",
            "title": "Litigation and Compliance Memo",
            "doc_id": "DR-015",
            "owner": "Legal Diligence",
            "sensitivity": "Legal - Synthetic",
            "date": "2026-02-07",
            "blocks": [
                section(
                    "Litigation Summary",
                    table=make_table(
                        ["Matter", "Status", "Claim Amount", "Deal Treatment"],
                        [
                            ["Former reseller commission dispute", "Settled before close", "INR 0.8 Cr", "No escrow required"],
                            ["Service tax assessment", "Under appeal", "INR 1.9 Cr", "Tax escrow"],
                            ["Employee classification inquiry", "Management response pending", "Not quantified", "Covenant to remediate contractor records"],
                        ],
                    ),
                ),
                section(
                    "Anti-Bribery and Sanctions",
                    "No sanctions matches were identified for the company, directors, or known beneficial owners based on seller-provided screening. Northstar has public-sector customer interactions but no government revenue exceeded 5 percent of FY2025 revenue. Gift and entertainment logs were incomplete for two quarters and must be remediated within 90 days after close.",
                ),
                section(
                    "Data Privacy",
                    "Northstar processes loan applicant data for bank customers. Management represented that it does not sell personal data. Diligence identified inconsistent data retention schedules across two products. Integration plan requires a unified retention policy and customer notice templates by day 60.",
                ),
            ],
        },
        {
            "filename": "16_Regulatory_Clearance_Memo.pdf",
            "title": "Regulatory Clearance Memo",
            "doc_id": "DR-016",
            "owner": "Regulatory Counsel",
            "sensitivity": "Legal - Synthetic",
            "date": "2026-02-15",
            "blocks": [
                section(
                    "Jurisdiction Analysis",
                    table=make_table(
                        ["Jurisdiction", "Filing Analysis", "Risk Tier", "Outcome"],
                        [
                            ["United States HSR", "Target US assets and sales below filing threshold based on management schedules.", "Low", "No filing required"],
                            ["India CCI", "Transaction reviewed under applicable combination thresholds and exemptions.", "Low", "No substantive competition concern identified"],
                            ["United Kingdom CMA", "No UK share of supply overlap above review concern level.", "Low", "No filing expected"],
                            ["EU Merger Regulation", "EU turnover thresholds not met.", "Low", "No filing required"],
                            ["Foreign investment / CFIUS", "No US TID business, critical infrastructure, or sensitive US government personnel data.", "Low", "No mandatory declaration identified"],
                        ],
                        [1.25 * inch, 3.0 * inch, 0.8 * inch, 1.8 * inch],
                    ),
                ),
                section(
                    "Closing Condition",
                    "Regulatory counsel recommended a bring-down certificate at closing confirming that no material customer geography, government contract, or data category changed between signing and closing.",
                ),
                section(
                    "Board Explanation",
                    "The transaction is primarily vertical and complementary. Product overlap is limited, combined market share is below concern levels in each reviewed market, and the parties serve a fragmented customer base.",
                ),
            ],
        },
        {
            "filename": "17_Financing_Commitment_and_Capital_Stack.pdf",
            "title": "Financing Commitment and Capital Stack",
            "doc_id": "DR-017",
            "owner": "Aster Treasury",
            "sensitivity": "Financing Confidential - Synthetic",
            "date": "2026-02-16",
            "blocks": [
                section(
                    "Sources and Uses",
                    table=make_table(
                        ["Sources", "USD M", "Uses", "USD M"],
                        [
                            ["Senior secured term loan", "48.0", "Enterprise value", "86.0"],
                            ["Cash on balance sheet", "28.5", "Estimated net debt", "3.2"],
                            ["Management rollover equity", "10.3", "Transaction fees", "4.1"],
                            ["Seller escrow / holdbacks", "7.5", "Cash to balance sheet", "1.0"],
                            ["Total sources", "94.3", "Total uses", "94.3"],
                        ],
                    ),
                ),
                section(
                    "Debt Terms",
                    table=make_table(
                        ["Term", "Value"],
                        [
                            ["Facility", "Senior secured term loan"],
                            ["Principal", "USD 48.0 million"],
                            ["Spread", "SOFR plus 475 bps"],
                            ["Amortization", "5 percent annually"],
                            ["Maturity", "5 years"],
                            ["Financial covenant", "Net leverage below 3.75x at close, stepping down to 3.25x"],
                        ],
                        [2.15 * inch, 4.7 * inch],
                    ),
                ),
                section(
                    "Return Case",
                    "Base case levered IRR is 18.4 percent using 8.6x entry EBITDA multiple, 9.0x exit EBITDA multiple, normalized EBITDA growth of 13 percent CAGR, and USD 7.8 million annual run-rate synergies by year 3. Bear case IRR is 12.6 percent if revenue synergies are delayed and exit multiple compresses to 8.0x.",
                ),
            ],
        },
        {
            "filename": "18_Board_Approval_Minutes.pdf",
            "title": "Board Approval Minutes",
            "doc_id": "DR-018",
            "owner": "Corporate Secretary",
            "sensitivity": "Board Confidential - Synthetic",
            "date": "2026-02-17",
            "blocks": [
                section(
                    "Meeting Summary",
                    "The Board of Directors of Aster Capital Technologies Inc. met on 2026-02-17 to review and approve the acquisition of Northstar Process Automation Pvt. Ltd. Management presented the strategic rationale, valuation analysis, financing plan, diligence findings, regulatory assessment, and integration plan.",
                ),
                section(
                    "Materials Reviewed",
                    table=make_table(
                        ["Material", "Presenter", "Board Discussion"],
                        [
                            ["Financial model and DCF", "CFO", "Board tested downside case and covenant headroom"],
                            ["Legal diligence summary", "General Counsel", "Board focused on customer consent and IP assignments"],
                            ["Financing commitment", "Treasury", "Board confirmed committed financing availability"],
                            ["Integration plan", "CPO", "Board requested day 30 engineering retention update"],
                        ],
                    ),
                ),
                section(
                    "Resolutions",
                    "The Board approved the execution of definitive agreements, authorized officers to complete closing deliverables, approved a maximum purchase price of USD 86.0 million enterprise value before customary adjustments, and approved retention packages for designated Northstar employees.",
                ),
            ],
        },
        {
            "filename": "19_Closing_Checklist_and_Funds_Flow.pdf",
            "title": "Closing Checklist and Funds Flow",
            "doc_id": "DR-019",
            "owner": "Deal Counsel",
            "sensitivity": "Closing Confidential - Synthetic",
            "date": DEAL["closing_date"],
            "blocks": [
                section(
                    "Closing Checklist",
                    table=make_table(
                        ["Item", "Owner", "Status", "Notes"],
                        [
                            ["Board approvals", "Corporate Secretary", "Complete", "Aster and Northstar approvals delivered"],
                            ["Meridian customer consent", "Seller Counsel", "Waived with holdback", "USD 2.0M holdback established"],
                            ["IP confirmatory assignments", "Seller Counsel", "Complete", "Two assignments delivered"],
                            ["Debt payoff letter", "Target CFO", "Complete", "Eastern Commercial Bank paid at close"],
                            ["Financing draw", "Aster Treasury", "Complete", "USD 48.0M funded"],
                            ["Officer certificates", "Both parties", "Complete", "Delivered at closing"],
                            ["Regulatory bring-down", "Regulatory Counsel", "Complete", "No filing status change"],
                        ],
                    ),
                ),
                section(
                    "Funds Flow",
                    table=make_table(
                        ["Recipient", "Purpose", "USD M"],
                        [
                            ["Selling shareholders", "Cash consideration", "76.5"],
                            ["Escrow agent", "General, tax, customer, cyber holdbacks", "7.5"],
                            ["Eastern Commercial Bank", "Debt repayment", "3.2"],
                            ["Advisors and counsel", "Transaction fees", "4.1"],
                            ["Northstar balance sheet", "Minimum cash", "1.0"],
                        ],
                    ),
                ),
            ],
        },
        {
            "filename": "20_PMI_100_Day_Plan_and_Synergy_Tracker.pdf",
            "title": "PMI 100-Day Plan and Synergy Tracker",
            "doc_id": "DR-020",
            "owner": "Integration Management Office",
            "sensitivity": "Internal - Synthetic",
            "date": "2026-04-05",
            "blocks": [
                section(
                    "PMI DNA Score",
                    table=make_table(
                        ["Workstream", "Friction Score", "Risk", "Day 100 Action"],
                        [
                            ["IT systems", "58 / 100", "Medium", "SSO migration and cloud contract extension"],
                            ["Finance", "71 / 100", "Low", "Chart of accounts mapping and reporting close calendar"],
                            ["HR", "49 / 100", "High", "Retention interviews and benefits harmonization"],
                            ["Sales", "66 / 100", "Medium", "Customer messaging and account mapping"],
                            ["Operations", "62 / 100", "Medium", "Implementation capacity planning"],
                            ["Culture", "53 / 100", "High", "Leadership roadshow and engagement survey"],
                        ],
                    ),
                ),
                section(
                    "Synergy Tracker",
                    table=make_table(
                        ["Synergy Category", "Year 1 Target", "Day 30 Actual", "Status"],
                        [
                            ["Headcount overlap", "USD 1.6M", "USD 0.2M", "On track"],
                            ["Cloud and vendor savings", "USD 1.1M", "USD 0.0M", "Delayed by data residency review"],
                            ["Procurement savings", "USD 0.8M", "USD 0.1M", "On track"],
                            ["Cross-sell revenue", "USD 2.4M", "USD 0.3M pipeline", "Early pipeline"],
                            ["Implementation margin improvement", "USD 0.7M", "USD 0.0M", "Planning"],
                        ],
                    ),
                ),
                section(
                    "Top 100-Day Tasks",
                    "Day 1: announce leadership structure, confirm customer communication plan, launch retention outreach, freeze non-essential system changes. Day 30: complete SSO migration plan, finalize customer consent outreach, update synergy forecast. Day 60: complete data retention policy and finance close calendar. Day 100: deliver board integration report and updated year-one synergy forecast.",
                ),
            ],
        },
    ]


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for old_pdf in OUTPUT_DIR.glob("*.pdf"):
        old_pdf.unlink()

    generated = []
    for definition in doc_definitions():
        generated.append(build_pdf(**definition))

    writer = PdfWriter()
    for path in generated:
        writer.append(str(path))
    with COMBINED_PDF.open("wb") as handle:
        writer.write(handle)

    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with ZipFile(ZIP_PATH, "w", ZIP_DEFLATED) as archive:
        archive.write(COMBINED_PDF, COMBINED_PDF.name)
        for path in generated:
            archive.write(path, f"pdfs/{path.name}")

    print(f"Generated {len(generated)} PDFs")
    print(COMBINED_PDF)
    print(ZIP_PATH)


if __name__ == "__main__":
    main()
