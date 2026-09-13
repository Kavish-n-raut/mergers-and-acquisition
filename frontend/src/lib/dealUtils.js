export const STAGE_LABELS = {
  m1_hunt: "Target Screening",
  m2_approach: "Outreach & NDA",
  m3_handshake: "Valuation",
  m4_deep_dive: "Due Diligence",
  m5_war_room: "Negotiation",
  m6_check: "Financing & Regulatory",
  m7_close: "Closing",
  m8_reality: "Post-Merger Integration",
};

export const STAGE_OPTIONS = Object.entries(STAGE_LABELS).map(([value, label]) => ({ value, label }));

export const STATUS_LABELS = {
  in_progress: "In Progress",
  completed: "Completed",
  blocked: "Blocked",
};

export const DEAL_TYPES = ["Acquisition", "Merger", "Minority Investment", "Carve-Out"];

export const DEMO_ASSUMPTIONS = {
  dcf_assumptions: {
    wacc: 0.1,
    terminal_growth_rate: 0.025,
    free_cash_flows: [1800000, 2200000, 2600000, 3100000, 3600000],
  },
  acquirer_market_cap: 240000000,
  synergy_assumptions: {
    company_a_revenue: 118000000,
    company_b_revenue: 42000000,
    company_b_opex: 14500000,
    cost_reduction_pct: 0.12,
    cross_sell_pct: 0.045,
    market_compatibility_score: 8,
    tech_stack_compatibility: 7,
  },
};

export const DEMO_DEAL = {
  dealName: "Aster Northstar Acquisition",
  buyerName: "Aster Capital Technologies",
  targetName: "Northstar Process Automation",
  dealType: "Acquisition",
  sector: "Industrial Automation Software",
  geography: "North America",
  owner: "Maya Desai",
  transactionCode: "AST-NPA-2026",
  dealValue: 87500000,
  closeProbability: 68,
  stage: "m4_deep_dive",
  status: "in_progress",
  teamMembers: ["Maya Desai", "Jon Bell", "Priya Shah", "Carlos Mendes"],
};

export const DEMO_DOCUMENT_FOLDERS = [
  "Corporate",
  "Financial",
  "Legal",
  "Tax",
  "HR",
  "IP",
  "Customer Contracts",
  "Regulatory",
  "Closing",
  "PMI",
];

export const DEMO_DOCUMENTS = [
  { name: "Certificate of Incorporation", folder: "Corporate", type: "Charter Document", owner: "Legal", uploadDate: "2026-05-12", scanStatus: "Reviewed", riskCount: 0, lastScanned: "2026-05-21", summary: "Corporate authority materials appear complete for initial diligence." },
  { name: "Northstar Credit Agreement", folder: "Legal", type: "Debt Agreement", owner: "Finance", uploadDate: "2026-05-13", scanStatus: "Reviewed", riskCount: 2, lastScanned: "2026-05-21", summary: "Contains lender consent and restricted indebtedness provisions." },
  { name: "FY2025 Quality of Earnings", folder: "Financial", type: "Financial Diligence", owner: "Finance", uploadDate: "2026-05-14", scanStatus: "Reviewed", riskCount: 1, lastScanned: "2026-05-21", summary: "Revenue quality is strong, with one-time implementation services normalized." },
  { name: "Top Customer MSA", folder: "Customer Contracts", type: "Commercial Contract", owner: "Commercial", uploadDate: "2026-05-15", scanStatus: "Reviewed", riskCount: 1, lastScanned: "2026-05-21", summary: "Assignment and change-of-control provisions require customer outreach." },
  { name: "Patent Assignment Schedule", folder: "IP", type: "IP Schedule", owner: "Product Counsel", uploadDate: "2026-05-16", scanStatus: "Queued", riskCount: 0, lastScanned: "Not scanned", summary: "Awaiting scan for title chain and open-source dependency review." },
  { name: "Employee Census", folder: "HR", type: "HR Data", owner: "People", uploadDate: "2026-05-17", scanStatus: "Queued", riskCount: 0, lastScanned: "Not scanned", summary: "Retention and compensation benchmarking pending." },
  { name: "HSR Antitrust Memo", folder: "Regulatory", type: "Regulatory Memo", owner: "Regulatory", uploadDate: "2026-05-18", scanStatus: "Reviewed", riskCount: 1, lastScanned: "2026-05-21", summary: "No obvious filing blocker, but customer concentration needs review." },
];

export const DEMO_RISKS = [
  { severity: "High", category: "Legal", risk_category: "Debt Covenant", sourceDocument: "Northstar Credit Agreement", owner: "Finance", status: "Reviewing", mitigation: "Escrow", ai_explanation: "The credit agreement may require lender consent before new debt or a change in control.", quoted_text: "Borrower shall not incur additional indebtedness or enter into a change of control transaction without prior written lender consent.", recommended_action: "Request covenant waiver before signing and include financing-condition fallback language." },
  { severity: "Medium", category: "Customer", risk_category: "Change of Control", sourceDocument: "Top Customer MSA", owner: "Commercial", status: "Open", mitigation: "Closing Condition", ai_explanation: "A key customer contract may be terminable if ownership changes without customer approval.", quoted_text: "Customer may terminate this agreement upon assignment or transfer by operation of law.", recommended_action: "Prioritize customer consent outreach during confirmatory diligence." },
  { severity: "Medium", category: "Regulatory", risk_category: "Customer Concentration", sourceDocument: "HSR Antitrust Memo", owner: "Regulatory", status: "Open", mitigation: "Covenant", ai_explanation: "The combined company has concentration in discrete process manufacturing customers.", quoted_text: "Combined share in two vertical niches may require additional customer win-loss support.", recommended_action: "Prepare competitive effects memo before regulatory submission." },
  { severity: "Low", category: "Cyber", risk_category: "Data Privacy", sourceDocument: "Data Processing Addendum", owner: "IT Security", status: "Mitigated", mitigation: "Indemnity", ai_explanation: "Privacy obligations appear manageable but should be validated before systems integration.", quoted_text: "Processor shall notify controller of a security incident without undue delay.", recommended_action: "Add post-close privacy controls to the integration plan." },
];

export const DEMO_VALUATION = {
  footballField: [
    { method: "DCF", low: 78, high: 96 },
    { method: "Trading Comps", low: 72, high: 91 },
    { method: "Precedent Transactions", low: 84, high: 105 },
    { method: "LBO Floor", low: 68, high: 82 },
  ],
  trends: [
    { year: "2023", revenue: 34, ebitda: 5.8 },
    { year: "2024", revenue: 38, ebitda: 6.9 },
    { year: "2025", revenue: 42, ebitda: 8.1 },
  ],
  synergyBreakdown: [
    { label: "Software Consolidation", value: 1.4 },
    { label: "G&A Rationalization", value: 1.1 },
    { label: "Cross-Sell Upside", value: 2.7 },
  ],
};

export const DEMO_MARKET_INTELLIGENCE = {
  generatedAt: "2026-05-21 09:00 IST",
  dataMode: "Sample local intelligence",
  confidence: "Medium",
  sourceNotes: [
    "Local MVP mode is active. Values are synthetic sample estimates unless marked as a public source.",
    "Google Maps is used only when VITE_GOOGLE_MAPS_API_KEY is configured. Otherwise the map is a static sample operating footprint.",
    "Public-company fields use SEC EDGAR, Stooq, exchange filings, or company investor relations only when a ticker is configured.",
  ],
  entryContext: {
    buyerCountry: "United States",
    targetCountry: "United States",
    marketEntryCountry: "Canada",
    employeeCountries: "United States, Canada, Mexico",
    dataHostingCountries: "United States, Canada",
    sector: "Industrial Automation Software",
    dealType: "Acquisition",
  },
  locations: [
    { name: "Aster Capital Technologies", type: "Buyer HQ", city: "San Francisco, CA", country: "United States", lat: 37.7749, lng: -122.4194, importance: "Corporate development and product leadership hub." },
    { name: "Northstar Process Automation", type: "Target HQ", city: "Chicago, IL", country: "United States", lat: 41.8781, lng: -87.6298, importance: "Target headquarters and customer success center." },
    { name: "ProcessPilot Systems", type: "Competitor", city: "Austin, TX", country: "United States", lat: 30.2672, lng: -97.7431, importance: "Likely pricing response in mid-market manufacturing accounts." },
    { name: "FactoryFlow Analytics", type: "Competitor", city: "Boston, MA", country: "United States", lat: 42.3601, lng: -71.0589, importance: "Product-led competitor with analytics-led positioning." },
    { name: "ControlGrid AI", type: "Competitor", city: "Toronto, ON", country: "Canada", lat: 43.6532, lng: -79.3832, importance: "Canadian go-to-market benchmark." },
    { name: "Automotive Customer Cluster", type: "Customer Market", city: "Detroit, MI", country: "United States", lat: 42.3314, lng: -83.0458, importance: "Dense installed base for plant modernization." },
    { name: "Industrial Energy Cluster", type: "Customer Market", city: "Houston, TX", country: "United States", lat: 29.7604, lng: -95.3698, importance: "Cross-sell opportunity into process-heavy energy accounts." },
    { name: "Northern Mexico Manufacturing Corridor", type: "Operating Region", city: "Monterrey", country: "Mexico", lat: 25.6866, lng: -100.3161, importance: "Nearshore manufacturing expansion region." },
    { name: "Federal Trade Commission", type: "Regulatory Office", city: "Washington, DC", country: "United States", lat: 38.8977, lng: -77.0365, importance: "US competition review reference point." },
    { name: "Competition Bureau Canada", type: "Regulatory Office", city: "Gatineau, QC", country: "Canada", lat: 45.4765, lng: -75.7013, importance: "Canadian merger review reference point." },
  ],
  legalChecklist: [
    { area: "Company Registration", guidance: "Confirm whether a Canadian subsidiary or branch registration is required before commercial launch.", owner: "Corporate Counsel", status: "Open", mitigation: "Local registration workstream" },
    { area: "Foreign Ownership Rules", guidance: "Screen sector and buyer nationality against foreign investment ownership limits.", owner: "Regulatory Counsel", status: "Reviewing", mitigation: "Investment approval memo" },
    { area: "Investment Approval", guidance: "Assess Investment Canada Act thresholds and national security review triggers.", owner: "Regulatory Counsel", status: "Reviewing", mitigation: "Pre-filing consultation" },
    { area: "Merger / Competition Approval", guidance: "Review transaction size and market concentration for merger notification requirements.", owner: "Antitrust Counsel", status: "Open", mitigation: "Competition filing analysis" },
    { area: "Sector Licenses", guidance: "Validate whether automation software touches critical infrastructure, energy, or public-sector procurement rules.", owner: "Sector Counsel", status: "Open", mitigation: "License inventory" },
    { area: "Tax Registration", guidance: "Plan GST/HST, payroll, transfer pricing, and permanent-establishment registrations.", owner: "Tax", status: "Open", mitigation: "Tax setup checklist" },
    { area: "Employment Law", guidance: "Map employee transfer, benefits, termination, and works council style consultation obligations by province.", owner: "HR Legal", status: "Open", mitigation: "Employee transition plan" },
    { area: "Data Privacy", guidance: "Review PIPEDA, provincial privacy laws, customer DPA commitments, and cross-border transfer controls.", owner: "Privacy Counsel", status: "Reviewing", mitigation: "Data transfer impact assessment" },
    { area: "Cybersecurity", guidance: "Confirm incident reporting obligations and critical infrastructure customer security controls.", owner: "Security", status: "Open", mitigation: "Security controls gap review" },
    { area: "Anti-Bribery", guidance: "Run anti-corruption controls review for public-sector and government-linked sales channels.", owner: "Compliance", status: "Open", mitigation: "Third-party diligence" },
    { area: "Sanctions Screening", guidance: "Screen customer, reseller, supplier, and beneficial owner lists against sanctions databases.", owner: "Compliance", status: "Open", mitigation: "Sanctions screening" },
    { area: "Import / Export Rules", guidance: "Check export controls for software, encryption, industrial control systems, and restricted end users.", owner: "Trade Compliance", status: "Open", mitigation: "Export classification" },
    { area: "Environmental Rules", guidance: "Confirm no environmental operating permits are inherited through field-service or hardware activities.", owner: "Operations Counsel", status: "Open", mitigation: "Permit review" },
    { area: "Consumer Protection", guidance: "If SMB customers are served online, review marketing, subscription renewal, and cancellation rules.", owner: "Commercial Counsel", status: "Open", mitigation: "Terms review" },
    { area: "Closing Filings", guidance: "Prepare entity, tax, competition, employment, and customer-consent filing calendar.", owner: "Deal Counsel", status: "Open", mitigation: "Closing checklist" },
    { area: "Post-Close Obligations", guidance: "Track ongoing reporting, privacy, tax, employment, and license renewal obligations after Day 1.", owner: "Integration Lead", status: "Open", mitigation: "PMI compliance tracker" },
  ],
  nicheAnalysis: {
    niche: "AI-assisted workflow automation for mid-market discrete and process manufacturers.",
    customerSegment: "Operations leaders, plant managers, and industrial CIOs at manufacturers with 5 to 40 production sites.",
    marketSizeEstimate: "$1.2B to $1.8B addressable North American mid-market software spend. Sample estimate, not live market data.",
    growthDrivers: ["Labor shortages in plant operations", "Pressure to modernize legacy manufacturing execution workflows", "Nearshoring and supply-chain resilience investments", "Demand for lower-code process automation tools"],
    painPoints: ["Manual plant-floor reporting", "Fragmented OT and ERP data", "Long implementation cycles", "Cyber and compliance exposure in legacy control environments"],
    acquisitionRationale: "Northstar gives Aster an installed base in manufacturing operations and shortens entry into plant-level workflow automation by adding domain-specific product and customer relationships.",
    barriers: {
      regulatory: "Customer security reviews, data residency commitments, and competition filings can delay entry.",
      technology: "Integration with legacy OT, ERP, and historian systems requires specialized connectors and security controls.",
      distribution: "Industrial buyers prefer reference-driven sales and implementation partner networks, which take time to build organically.",
    },
  },
  competitors: [
    { name: "ProcessPilot Systems", headquarters: "Austin, TX", businessModel: "Subscription workflow automation with services-led deployment", marketPosition: "Mid-market challenger", strengths: "Fast implementation and strong plant analytics messaging", weaknesses: "Limited enterprise governance depth", likelyResponse: "Price cuts, sales push, and targeted customer-retention offers", confidence: "Sample / Medium" },
    { name: "FactoryFlow Analytics", headquarters: "Boston, MA", businessModel: "Analytics-first SaaS sold through manufacturing transformation teams", marketPosition: "Analytics specialist", strengths: "Strong dashboards and executive reporting", weaknesses: "Less deep in control-system workflows", likelyResponse: "Faster product launch and partnership with systems integrators", confidence: "Sample / Medium" },
    { name: "ControlGrid AI", headquarters: "Toronto, ON", businessModel: "Industrial AI platform with Canadian market focus", marketPosition: "Regional specialist", strengths: "Local customer references and regulatory familiarity", weaknesses: "Smaller sales capacity outside Canada", likelyResponse: "Geographic expansion and hiring push in US Midwest", confidence: "Sample / Low" },
    { name: "Large ERP Automation Suites", headquarters: "Insufficient public data", businessModel: "Bundled modules inside broader enterprise software suites", marketPosition: "Incumbent alternative", strengths: "Existing procurement relationships", weaknesses: "Slower time-to-value for specialized plant use cases", likelyResponse: "Partnership, account bundling, or regulatory complaint if concentration claims emerge", confidence: "Insufficient public data" },
  ],
  publicCompanyIntelligence: [
    {
      company: "Aster Capital Technologies",
      publicStatus: "Private company sample",
      ticker: "Not applicable",
      exchange: "Not applicable",
      ipoDate: "Not applicable",
      ipoPrice: "Not applicable",
      currentMarketCap: "Private - no public market cap available",
      revenue: "$118.0M sample management case",
      ebitdaOrNetIncome: "$22.4M sample EBITDA",
      sharePriceTrend: "Not applicable - private company",
      secLinks: "No SEC ticker configured",
      annualReport: "Insufficient public data",
      quarterlyReport: "Insufficient public data",
      majorShareholders: "Insufficient public data",
      lockupExpiry: "Not applicable",
      sentiment: "Insufficient public data",
      source: "Local sample data; replace with SEC EDGAR/Stooq/IR data when ticker is available.",
    },
    {
      company: "Northstar Process Automation",
      publicStatus: "Private target sample",
      ticker: "Not applicable",
      exchange: "Not applicable",
      ipoDate: "Not applicable",
      ipoPrice: "Not applicable",
      currentMarketCap: "Private - no public market cap available",
      revenue: "$42.0M sample management case",
      ebitdaOrNetIncome: "$8.1M sample EBITDA",
      sharePriceTrend: "Not applicable - private company",
      secLinks: "No SEC ticker configured",
      annualReport: "Insufficient public data",
      quarterlyReport: "Insufficient public data",
      majorShareholders: "Insufficient public data",
      lockupExpiry: "Not applicable",
      sentiment: "Insufficient public data",
      source: "Local sample data; replace with filings, exchange, or investor-relations sources when public data exists.",
    },
  ],
  reportSections: [
    { title: "Executive Summary", body: "Aster can use the Northstar acquisition to enter industrial automation software with an existing product, customer base, and implementation team. The entry case is attractive but depends on customer consent, lender waiver, and Canada market-entry compliance work." },
    { title: "Market Niche", body: "The target niche is workflow automation for mid-market manufacturers with fragmented plant operations and high modernization pressure." },
    { title: "Location Map", body: "The initial footprint links Aster's West Coast buyer headquarters, Northstar's Midwest operating base, customer clusters in Detroit and Houston, and a potential Canada entry corridor." },
    { title: "Legal & Regulatory Checklist", body: "Priority items are competition review, foreign investment screening, data privacy, employment transfer planning, and sector-specific customer security requirements." },
    { title: "Competitor Landscape", body: "Competitors are likely to respond through pricing, faster launches, partner motions, customer-retention pushes, and selective hiring in industrial hubs." },
    { title: "Public Company / IPO Details", body: "Both entities are treated as private sample companies in local mode. Public market intelligence should be activated only with validated tickers and official public sources." },
    { title: "Risks", body: "Top market-entry risks are regulatory timing, customer consent friction, data residency requirements, and slower-than-modeled distribution buildout." },
    { title: "Recommended Entry Strategy", body: "Use Northstar as the beachhead, prioritize Canadian compliance readiness, protect top-customer retention, and build channel partnerships in industrial regions." },
    { title: "Next Actions", body: "Validate filing thresholds, refresh competitor data from public sources, confirm customer concentration, and prepare a local-counsel review checklist." },
  ],
};

export const DEMO_NEGOTIATION_TERMS = [
  { term: "Price", value: "$92.5M current offer", status: "open" },
  { term: "Escrow", value: "8.0% for 18 months", status: "disputed" },
  { term: "Indemnity Cap", value: "12.5% fundamental / 8.0% general", status: "open" },
  { term: "Exclusivity", value: "45 days", status: "agreed" },
  { term: "Closing Conditions", value: "Customer consent and lender waiver", status: "disputed" },
  { term: "Earn-Out", value: "$7.5M tied to ARR retention", status: "open" },
];

export const DEMO_CLOSING_CHECKLIST = [
  { item: "Board Approval", owner: "Aster Corp Dev", dueDate: "2026-06-05", status: "Reviewing", blocker: "Board memo draft in progress" },
  { item: "Regulatory Clearance", owner: "Regulatory Counsel", dueDate: "2026-06-14", status: "Open", blocker: "Customer concentration memo pending" },
  { item: "Financing Commitment", owner: "Treasury", dueDate: "2026-06-10", status: "Open", blocker: "Lender consent required" },
  { item: "Customer Consents", owner: "Commercial Lead", dueDate: "2026-06-18", status: "Open", blocker: "Top customer outreach not yet complete" },
  { item: "Legal Opinions", owner: "Deal Counsel", dueDate: "2026-06-20", status: "Not Started", blocker: "Final structure confirmation needed" },
  { item: "Funds Flow", owner: "Finance", dueDate: "2026-06-22", status: "Not Started", blocker: "Purchase price mechanics not final" },
  { item: "Officer Certificates", owner: "Seller Counsel", dueDate: "2026-06-24", status: "Not Started", blocker: "Final disclosure schedules pending" },
];

export const DEMO_INTEGRATION_TASKS = [
  { milestone: "Day 1", workstream: "IT", task: "Confirm access controls and admin ownership", owner: "IT Integration", status: "Ready" },
  { milestone: "Day 1", workstream: "Finance", task: "Freeze opening balance sheet process", owner: "Controller", status: "Ready" },
  { milestone: "Day 30", workstream: "HR", task: "Launch retention and onboarding plan", owner: "People Ops", status: "In Progress" },
  { milestone: "Day 30", workstream: "Sales", task: "Map cross-sell account overlaps", owner: "Revenue Ops", status: "In Progress" },
  { milestone: "Day 60", workstream: "Operations", task: "Consolidate vendor management process", owner: "Operations", status: "Planned" },
  { milestone: "Day 100", workstream: "Culture", task: "Complete leadership operating model", owner: "Integration Lead", status: "Planned" },
];

export const DEMO_REPORT_HISTORY = [
  { name: "Board Memo", generatedBy: "Maya Desai", date: "2026-05-18", status: "Draft" },
  { name: "Risk Summary", generatedBy: "Priya Shah", date: "2026-05-19", status: "Board-ready" },
  { name: "Management Presentation", generatedBy: "Jon Bell", date: "2026-05-20", status: "Draft" },
];

export const DEMO_ACTIVITY = [
  "Financial diligence package refreshed by Finance.",
  "Legal flagged lender consent requirement for mitigation.",
  "Negotiation team updated earn-out proposal.",
  "Integration lead added Day 1 IT access checklist.",
];

export const DEMO_TIMELINE = [
  { label: "NDA Executed", date: "2026-05-06", status: "Completed" },
  { label: "Management Meeting", date: "2026-05-15", status: "Completed" },
  { label: "Confirmatory Diligence", date: "2026-05-28", status: "In Progress" },
  { label: "Investment Committee", date: "2026-06-04", status: "Upcoming" },
  { label: "Target Signing", date: "2026-06-24", status: "Upcoming" },
];

export const DEMO_REPORT = {
  deal_id: "demo-aster-northstar",
  company_a_financials: {
    latest_revenue: 118000000,
    latest_ebitda: 22400000,
    ratios: [{ Revenue_Growth: 0.14, EBITDA_Margin: 0.19 }],
  },
  company_b_financials: {
    latest_revenue: 42000000,
    latest_ebitda: 8100000,
    ratios: [{ Revenue_Growth: 0.105, EBITDA_Margin: 0.193 }],
  },
  valuation: { enterprise_value: 87500000 },
  synergies: { financial_synergies: { total_annual_synergy: 5200000 } },
  legal_risks: { risks: DEMO_RISKS },
  deal_structure: { recommended_structure: "Cash + Earn-out", estimated_dilution_pct: 0 },
  negotiation_strategy: {
    seller_leverage: "Medium",
    opening_bid_price: 92500000,
    walk_away_price: 113500000,
    tactical_moves: [
      "Use lender-consent requirement to negotiate a targeted escrow holdback.",
      "Tie earn-out consideration to retention of the top customer contract.",
      "Keep price movement linked to clean customer consent and covenant waiver delivery.",
    ],
  },
};

export function stageLabel(stage) {
  return STAGE_LABELS[stage] || "Target Screening";
}

export function statusLabel(status) {
  return STATUS_LABELS[status] || "In Progress";
}

export function displayDealName(name) {
  if (!name || name === "Unnamed Deal") return "Analysis Run";
  return name;
}

export function formatCurrency(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "Not available";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(number);
}

export function formatPercent(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "Not available";
  const normalized = Math.abs(number) <= 1 ? number * 100 : number;
  return `${normalized.toFixed(1)}%`;
}

export function getActiveReport() {
  try {
    return JSON.parse(localStorage.getItem("activeDealReport")) || DEMO_REPORT;
  } catch {
    return DEMO_REPORT;
  }
}

export function saveActiveReport(report) {
  localStorage.setItem("activeDealReport", JSON.stringify(report));
}

export function getActiveDealMeta() {
  try {
    return JSON.parse(localStorage.getItem("activeDealMeta")) || DEMO_DEAL;
  } catch {
    return DEMO_DEAL;
  }
}

export function saveActiveDealMeta(meta) {
  localStorage.setItem("activeDealMeta", JSON.stringify(meta));
  const map = getDealMetadataMap();
  if (meta.id) {
    map[meta.id] = meta;
    localStorage.setItem("dealMetadataMap", JSON.stringify(map));
  }
}

export function getDealMetadataMap() {
  try {
    return JSON.parse(localStorage.getItem("dealMetadataMap")) || {};
  } catch {
    return {};
  }
}

export function saveDealMetadata(id, meta) {
  const map = getDealMetadataMap();
  map[id] = { ...meta, id };
  localStorage.setItem("dealMetadataMap", JSON.stringify(map));
}

export function loadDemoWorkspace() {
  saveActiveDealMeta(DEMO_DEAL);
  saveActiveReport(DEMO_REPORT);
  localStorage.setItem("activeDocuments", JSON.stringify(DEMO_DOCUMENTS));
}

export function getActiveDocuments() {
  try {
    return JSON.parse(localStorage.getItem("activeDocuments")) || DEMO_DOCUMENTS;
  } catch {
    return DEMO_DOCUMENTS;
  }
}

export function getMetrics(report = getActiveReport()) {
  const acquirer = report?.company_a_financials || {};
  const target = report?.company_b_financials || {};
  const targetRatios = target.ratios?.[target.ratios.length - 1] || {};
  return {
    enterpriseValue: report?.valuation?.enterprise_value,
    ebitda: target.latest_ebitda,
    dcfValue: report?.valuation?.enterprise_value,
    synergyValue: report?.synergies?.financial_synergies?.total_annual_synergy,
    openingBid: report?.negotiation_strategy?.opening_bid_price,
    walkAway: report?.negotiation_strategy?.walk_away_price,
    ebitdaMargin: targetRatios.EBITDA_Margin ?? (target.latest_ebitda && target.latest_revenue ? target.latest_ebitda / target.latest_revenue : null),
    revenueGrowth: targetRatios.Revenue_Growth,
    acquirerRevenue: acquirer.latest_revenue,
    targetRevenue: target.latest_revenue,
  };
}

export function riskItems(report = getActiveReport()) {
  return report?.legal_risks?.risks?.length ? report.legal_risks.risks : DEMO_RISKS;
}

export function nextRecommendedAction(report = getActiveReport()) {
  const highRisk = riskItems(report).some((risk) => risk.severity === "High");
  if (highRisk) return "Resolve high-severity diligence items before final bid submission.";
  if (report?.negotiation_strategy?.opening_bid_price) return "Prepare the negotiation package for investment committee review.";
  return "Complete valuation and diligence inputs to generate transaction recommendations.";
}

export function getMarketIntelligence() {
  try {
    return JSON.parse(localStorage.getItem("marketIntelligence")) || DEMO_MARKET_INTELLIGENCE;
  } catch {
    return DEMO_MARKET_INTELLIGENCE;
  }
}
