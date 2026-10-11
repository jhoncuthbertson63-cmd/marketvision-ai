"""Curated universes. Groupings are MarketVision editorial classifications (labeled as such in the UI)."""

HEATMAP = {
    "Technology": ["AAPL", "MSFT", "NVDA", "AVGO", "ORCL", "CRM", "AMD", "ADBE", "CSCO", "ACN", "IBM", "QCOM", "TXN",
                   "INTU", "NOW", "AMAT", "MU", "LRCX", "KLAC", "PANW", "ANET", "INTC", "ADI", "CRWD", "PLTR"],
    "Communication": ["GOOGL", "META", "NFLX", "TMUS", "DIS", "VZ", "T", "CMCSA"],
    "Consumer Disc.": ["AMZN", "TSLA", "HD", "MCD", "LOW", "BKNG", "TJX", "NKE", "SBUX", "CMG"],
    "Consumer Staples": ["WMT", "COST", "PG", "KO", "PEP", "PM", "MDLZ", "CL"],
    "Health Care": ["LLY", "UNH", "JNJ", "ABBV", "MRK", "TMO", "ABT", "ISRG", "AMGN", "DHR", "PFE", "VRTX", "GILD", "BSX"],
    "Financials": ["BRK-B", "JPM", "V", "MA", "BAC", "WFC", "GS", "MS", "AXP", "BLK", "SCHW", "C", "SPGI", "PGR"],
    "Industrials": ["GE", "CAT", "RTX", "HON", "UNP", "BA", "LMT", "DE", "ETN", "UBER", "GEV", "ADP"],
    "Energy": ["XOM", "CVX", "COP", "SLB", "EOG"],
    "Utilities": ["NEE", "SO", "DUK", "CEG", "VST"],
    "Real Estate": ["PLD", "AMT", "EQIX", "WELL"],
    "Materials": ["LIN", "SHW", "APD", "FCX", "NEM"],
}

INDEXES = [("^GSPC", "S&P 500"), ("^IXIC", "Nasdaq Composite"), ("^DJI", "Dow Jones Industrial Avg"), ("^RUT", "Russell 2000")]
SECTOR_ETFS = [("XLK", "Technology"), ("XLC", "Communication"), ("XLY", "Consumer Disc."), ("XLP", "Consumer Staples"),
               ("XLV", "Health Care"), ("XLF", "Financials"), ("XLI", "Industrials"), ("XLE", "Energy"),
               ("XLU", "Utilities"), ("XLRE", "Real Estate"), ("XLB", "Materials")]

INDUSTRIES = [
    {"id": "ai", "name": "Artificial Intelligence & AI Platforms", "etf": "AIQ",
     "companies": ["NVDA", "MSFT", "GOOGL", "META", "AMZN", "ORCL", "PLTR", "NOW"],
     "drivers": ["Enterprise and consumer adoption of generative AI", "Hyperscaler AI capex budgets", "Model inference demand growth"]},
    {"id": "dc", "name": "Data Centers & Cooling", "etf": "DTCR",
     "companies": ["VRT", "EQIX", "DLR", "ANET", "SMCI", "DELL", "MOD", "JCI"],
     "drivers": ["Hyperscale & AI cluster construction", "Liquid cooling for high-density racks", "Colocation demand / vacancy rates"]},
    {"id": "power", "name": "Electricity & Power Infrastructure", "etf": "GRID",
     "companies": ["ETN", "PWR", "GEV", "HUBB", "NVT", "VST", "MYRG", "POWL"],
     "drivers": ["Data-center load growth", "Grid modernization & transmission build-out", "Electrification of transport & industry"]},
    {"id": "semis", "name": "Semiconductors & Advanced Computing", "etf": "SMH",
     "companies": ["NVDA", "AVGO", "AMD", "MU", "QCOM", "AMAT", "LRCX", "KLAC"],
     "drivers": ["Accelerator & HBM memory demand", "Advanced packaging capacity", "Wafer-fab equipment spending cycle"]},
    {"id": "robotics", "name": "Robotics & Automation", "etf": "BOTZ",
     "companies": ["ISRG", "ROK", "TER", "SYM", "CGNX", "ZBRA", "EMR"],
     "drivers": ["Labor scarcity & reshoring", "Warehouse automation", "Surgical robotics adoption"]},
    {"id": "nuclear", "name": "Nuclear Energy & Next-Gen Power", "etf": "NLR",
     "companies": ["CEG", "BWXT", "LEU", "SMR", "OKLO", "VST"],
     "drivers": ["24/7 carbon-free power contracts with tech firms", "Small modular reactor licensing", "Enriched uranium supply security"]},
    {"id": "cyber", "name": "Cybersecurity", "etf": "CIBR",
     "companies": ["CRWD", "PANW", "FTNT", "ZS", "NET", "OKTA", "S"],
     "drivers": ["Rising attack frequency & regulation (SEC cyber disclosure rules)", "Cloud & identity security consolidation", "AI-driven threats"]},
    {"id": "bio", "name": "Healthcare Innovation & Biotechnology", "etf": "XBI",
     "companies": ["LLY", "VRTX", "REGN", "ALNY", "AMGN", "GILD", "INCY", "EXEL"],
     "drivers": ["GLP-1 / metabolic therapies", "Gene & RNA medicines", "FDA approval cadence & M&A"]},
    {"id": "space", "name": "Space Technology", "etf": "UFO",
     "companies": ["RKLB", "ASTS", "IRDM", "LUNR", "PL", "VSAT"],
     "drivers": ["Launch cost declines", "Satellite broadband & direct-to-device", "Government space budgets"]},
    {"id": "defense", "name": "Defense & Aerospace", "etf": "ITA",
     "companies": ["LMT", "RTX", "NOC", "GD", "LHX", "BA", "HWM", "TDG"],
     "drivers": ["Global defense budget increases", "Munitions & missile-defense replenishment", "Commercial aircraft backlog"]},
    {"id": "fintech", "name": "Financial Technology", "etf": "FINX",
     "companies": ["PYPL", "XYZ", "COIN", "HOOD", "SOFI", "AFRM", "TOST", "FISV"],
     "drivers": ["Digital payments penetration", "Retail brokerage & crypto activity", "Embedded lending"]},
    {"id": "industrial", "name": "Industrial Manufacturing & Infrastructure", "etf": "PAVE",
     "companies": ["CAT", "DE", "URI", "VMC", "MLM", "PH", "FAST", "PWR"],
     "drivers": ["Public infrastructure spending", "Reshoring / new factory construction", "Equipment replacement cycles"]},
    {"id": "quantum", "name": "Quantum Computing (emerging)", "etf": "QTUM",
     "companies": ["IONQ", "RGTI", "QBTS", "IBM"],
     "drivers": ["Qubit fidelity milestones", "Government & enterprise pilot contracts"]},
    {"id": "software", "name": "Cloud & AI Software (emerging adjacency)", "etf": "IGV",
     "companies": ["CRM", "NOW", "ADBE", "SNOW", "DDOG", "MDB", "WDAY"],
     "drivers": ["AI agent monetization", "Cloud consumption trends", "Seat-based vs usage pricing shift"]},
]

# Wider thematic ETF list for the "emerging themes radar" (momentum evidence only)
RADAR = [("LIT", "Lithium & Battery Tech"), ("TAN", "Solar"), ("ICLN", "Clean Energy"), ("COPX", "Copper Miners"),
         ("ARKG", "Genomics"), ("IBB", "Large Biotech"), ("SKYY", "Cloud Computing"), ("HACK", "Cyber (alt)"),
         ("DRIV", "Autonomous & EV"), ("BLOK", "Blockchain"), ("XHB", "Homebuilders"), ("KRE", "Regional Banks"),
         ("JETS", "Airlines"), ("URNM", "Uranium Miners"), ("XME", "Metals & Mining"), ("SOXX", "Semis (alt)"),
         ("KWEB", "China Internet"), ("ESPO", "Video Games & Esports"), ("IPAY", "Digital Payments"), ("PHO", "Water"),
         ("WCLD", "Cloud (equal wt)"), ("ARKK", "Disruptive Innovation"), ("SHLD", "Defense Tech"), ("PPH", "Pharma"),
         ("XOP", "Oil & Gas E&P"), ("GDX", "Gold Miners"), ("IYT", "Transportation"), ("XRT", "Retail"),
         ("PAVE", "Infrastructure"), ("UFO", "Space"), ("QTUM", "Quantum"), ("NLR", "Nuclear"), ("GRID", "Smart Grid"),
         ("DTCR", "Data Centers"), ("BOTZ", "Robotics"), ("CIBR", "Cybersecurity"), ("ITA", "Aerospace & Defense"),
         ("SMH", "Semiconductors"), ("XBI", "Biotech"), ("FINX", "Fintech"), ("AIQ", "AI & Tech"), ("IGV", "Software")]


def industry_peers(ticker: str):
    t = ticker.upper()
    out = []
    for ind in INDUSTRIES:
        if t in ind["companies"]:
            out += [c for c in ind["companies"] if c != t]
    for sec, lst in HEATMAP.items():
        if t in lst:
            pass
    seen = []
    for c in out:
        if c not in seen:
            seen.append(c)
    return seen, [ind["name"] for ind in INDUSTRIES if t in ind["companies"]]
