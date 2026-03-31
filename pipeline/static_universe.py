"""
Static list of major US stock tickers.
Coverage: S&P 500 full components + NASDAQ 100 + major mid-cap growth stocks.
Target: ~650 unique liquid tickers.
Used as fallback when FMP API is unavailable.
"""

STATIC_TICKERS = [
    # ── Index ETFs (market reference + screening) ─────────────────────────
    "SPY", "QQQ", "IWM",

    # ── S&P 500 — Technology ──────────────────────────────────────────────
    "AAPL", "MSFT", "NVDA", "AVGO", "ORCL", "CRM", "ACN", "CSCO", "IBM",
    "ADBE", "NOW", "INTU", "TXN", "QCOM", "AMD", "AMAT", "LRCX", "KLAC",
    "MU", "ADI", "MCHP", "NXPI", "ON", "TEL", "ANSS", "CDNS", "SNPS",
    "FTNT", "EPAM", "CTSH", "IT", "GLW", "STX", "WDC", "NTAP", "HPE",
    "HPQ", "DELL", "PSTG", "KEYS", "TDY", "JNPR", "ZBRA", "VRSN", "AKAM",
    "CDW", "LDOS", "SAIC", "DXC", "FFIV", "ANET", "SMCI",

    # ── S&P 500 — Communication Services ─────────────────────────────────
    "GOOGL", "GOOG", "META", "NFLX", "DIS", "CMCSA", "T", "VZ", "TMUS",
    "CHTR", "WBD", "PARA", "FOX", "FOXA", "OMC", "IPG", "EA", "TTWO",
    "LYV", "MTCH", "ZM", "SNAP",

    # ── S&P 500 — Consumer Discretionary ─────────────────────────────────
    "AMZN", "TSLA", "HD", "MCD", "NKE", "LOW", "SBUX", "CMG", "TJX",
    "BKNG", "MAR", "HLT", "YUM", "DPZ", "ROST", "EBAY", "EXPE", "ABNB",
    "F", "GM", "APTV", "LKQ", "ORLY", "AZO", "AAP", "GPC", "POOL",
    "WSM", "BBY", "ULTA", "LULU", "NVR", "PHM", "LEN", "DHI", "TOL",
    "MDC", "MTH", "KBH", "CZR", "MGM", "LVS", "WYNN", "RCL", "CCL",
    "NCLH", "HAS", "MAT", "DECK", "ONON", "SKX", "VFC", "PVH", "RL",
    "HBI", "UAA", "ANF", "AEO", "URBN", "GPS", "TGT", "DLTR", "DG",
    "KSS", "M", "JWN",

    # ── S&P 500 — Consumer Staples ────────────────────────────────────────
    "WMT", "COST", "PG", "KO", "PEP", "PM", "MO", "MDLZ", "CL", "KMB",
    "EL", "GIS", "K", "CPB", "HRL", "SJM", "MKC", "CAG", "HSY", "MNST",
    "STZ", "BF.B", "TAP", "ADM", "BG", "TSN", "CAH", "MCK", "ABC",
    "WBA", "CVS", "KR", "SYY", "USFD",

    # ── S&P 500 — Energy ──────────────────────────────────────────────────
    "XOM", "CVX", "COP", "EOG", "SLB", "MPC", "PSX", "VLO", "PXD",
    "OXY", "HAL", "BKR", "DVN", "FANG", "HES", "APA", "MRO", "RRC",
    "EQT", "CNX", "AR", "CTRA", "OKE", "KMI", "WMB", "EPD", "ET",
    "TRGP", "MPLX", "BSM", "DT", "NRG", "CEG", "VST", "TLN",

    # ── S&P 500 — Financials ──────────────────────────────────────────────
    "JPM", "BAC", "WFC", "GS", "MS", "C", "BX", "BLK", "SCHW", "AXP",
    "V", "MA", "COF", "DFS", "SYF", "USB", "PNC", "TFC", "FITB", "KEY",
    "HBAN", "RF", "CFG", "MTB", "ZION", "NTRS", "STT", "BK", "IVZ",
    "TROW", "BEN", "AMG", "AMP", "RJF", "LPLA", "MKTX", "ICE", "CME",
    "CBOE", "NDAQ", "SPGI", "MCO", "MMC", "AON", "AJG", "WTW", "MKL",
    "CB", "AIG", "MET", "PRU", "AFL", "ALL", "PGR", "TRV", "HIG",
    "CNA", "CINF", "GL", "UNM", "LNC", "EIG", "ERIE", "RLI", "WRB",
    "RE", "RNR", "ACGL", "RYAN", "VOYA", "FNF", "FAF",

    # ── S&P 500 — Health Care ─────────────────────────────────────────────
    "LLY", "UNH", "JNJ", "ABBV", "MRK", "TMO", "ABT", "DHR", "BMY",
    "AMGN", "GILD", "VRTX", "REGN", "ISRG", "SYK", "MDT", "BSX", "EW",
    "ZBH", "STE", "HOLX", "DXCM", "PODD", "INSP", "SWAV", "NVCR",
    "ALGN", "RMD", "IDXX", "BIO", "A", "IQV", "CRL", "LH", "DGX",
    "PKI", "NVST", "HSIC", "XRAY", "PRCT", "TMDX", "MMSI", "INVA",
    "HCA", "THC", "UHS", "CNC", "HUM", "CI", "ELV", "MOH", "OSCR",
    "CVS", "MCK", "ABC", "WBSN",

    # ── S&P 500 — Industrials ─────────────────────────────────────────────
    "GE", "HON", "CAT", "DE", "ETN", "EMR", "ITW", "PH", "ROP", "CARR",
    "OTIS", "IR", "XYL", "GNRC", "TT", "MMM", "RTX", "LMT", "NOC",
    "GD", "LHX", "HII", "LDOS", "SAIC", "BAH", "CSGP", "TRMB", "VRSK",
    "EXPD", "CHRW", "XPO", "GXO", "FDX", "UPS", "JBHT", "ODFL", "SAIA",
    "AIT", "GWW", "MSC", "FAST", "WSO", "AOS", "MAS", "PNR", "AME",
    "FTV", "HUBB", "FBIN", "JCI", "ACUITY", "CNI", "CP", "NSC", "CSX",
    "UNP", "WAB", "TDG", "AXON", "LDOS", "BAH", "CACI",

    # ── S&P 500 — Materials ───────────────────────────────────────────────
    "LIN", "APD", "SHW", "ECL", "PPG", "RPM", "NEM", "GOLD", "FCX",
    "NUE", "STLD", "RS", "ATI", "CLF", "X", "VMC", "MLM", "CRH",
    "EXP", "USCR", "CF", "MOS", "NTR", "ALB", "ALBEMARLE", "LTHM",
    "FMC", "DD", "DOW", "LYB", "HUN", "WLK", "OLN", "CE", "EMN",
    "PKG", "IP", "SEE", "SON", "SLGN",

    # ── S&P 500 — Real Estate ─────────────────────────────────────────────
    "PLD", "AMT", "EQIX", "CCI", "SPG", "PSA", "O", "VICI", "WPC",
    "EXR", "AVB", "ESS", "MAA", "UDR", "CPT", "EQR", "IRM", "DLR",
    "SBAC", "SUI", "ELS", "UDR", "NSA", "CUBE", "LSI", "REXR", "TRNO",
    "COLD", "KIM", "REG", "BRX", "AKR", "RPT", "WRI", "SKT", "ROIC",
    "IIPR", "MPW", "DOC", "HR", "VTR", "PEAK", "WELL", "OHI", "LTC",
    "NNN", "EPRT", "ADC", "AGREE",

    # ── S&P 500 — Utilities ───────────────────────────────────────────────
    "NEE", "SO", "DUK", "AEP", "D", "EXC", "SRE", "PEG", "XEL", "WEC",
    "ES", "AWK", "ATO", "LNT", "EVRG", "PNW", "OGE", "NI", "CMS",
    "CNP", "AES", "NRG", "PPL", "FE", "ETR", "EIX", "PCG", "AVA",
    "IDACORP", "POR", "IDA", "MGEE",

    # ── NASDAQ 100 additions ──────────────────────────────────────────────
    "MELI", "PDD", "BIDU", "JD", "NTES", "BABA", "SE", "GRAB",
    "SHOP", "WDAY", "VEEV", "TEAM", "HUBS", "DDOG", "ZS", "CRWD",
    "PANW", "NET", "OKTA", "ZM", "BILL", "GTLB", "MDB", "SNOW",
    "PLTR", "SMAR", "BOX", "DOCN", "ESTC", "ELASTIC",

    # ── Mid-cap growth / NASDAQ breakouts ─────────────────────────────────
    "ENPH", "FSLR", "SEDG", "ARRY", "RUN", "NOVA", "SPWR",
    "AEHR", "ONTO", "AMBA", "FORM", "MPWR", "SITM", "ALGM",
    "MRVL", "SWKS", "QRVO", "MTSI", "ADI", "NXPI",
    "AXNX", "CRUS", "DIOD", "SLAB", "SMTC", "POWI",
    "AI", "SOUN", "BBAI", "IONQ", "RGTI", "QUBT",
    "COIN", "HOOD", "SOFI", "AFRM", "UPST", "SQ", "PYPL",
    "RBLX", "U", "TTWO", "EA", "TAKE", "ZNGA",
    "DKNG", "PENN", "RSI",
    "SMCI", "NTAP", "PSTG", "PURE", "BOX",
    "TOST", "PAX", "FOUR", "PAYA", "FLYW",
    "CELH", "VITL", "ELF", "SKIN", "HIMS",
    "CAVA", "BROS", "TXRH", "WING", "SHAK", "DPZ",
    "AXON", "TASER", "MSA", "SAIA", "ODFL", "TFII",
    "APP", "APPLOVIN", "MGNI", "PUBM", "TTD", "TRADE",
    "EXLM", "CIEN", "LITE", "IIVI", "II",
    "WOLF", "OLED", "MKSI", "UCTT", "ACLS",

    # ── Nuclear / Defense / Aerospace ─────────────────────────────────────
    "CCJ", "SMR", "NNE", "OKLO", "BWXT", "LEU", "UUUU", "DNN",
    "UEC", "URG", "LTBR", "GEV", "ETR",
    "LMT", "NOC", "GD", "RTX", "BA", "HII", "L3H",
    "RKLB", "RDW", "MNTS", "ASTS",

    # ── Biotech / Pharma ──────────────────────────────────────────────────
    "VKTX", "VCEL", "RARE", "ALNY", "BLUE", "FATE", "KYMR",
    "PTGX", "AKRO", "IMVT", "BMRN", "INCY", "JAZZ", "SGEN",
    "ILMN", "BIIB", "NTLA", "BEAM", "EDIT", "CRSP",
    "MRNA", "BNTX", "NVAX", "OCGN",
    "HZNP", "PCVX", "PMVP", "ARVN", "KROS",

    # ── Airlines / Travel ─────────────────────────────────────────────────
    "DAL", "UAL", "AAL", "LUV", "ALK", "JBLU", "HA",
    "MAR", "HLT", "H", "WH", "IHG", "EXPE", "BKNG", "ABNB",

    # ── Auto / EV ─────────────────────────────────────────────────────────
    "TSLA", "F", "GM", "RIVN", "LCID", "NIO", "LI", "XPEV",
    "APTV", "BWA", "LEA", "MGA", "MODG",

    # ── Agriculture / Commodities ─────────────────────────────────────────
    "ADM", "BG", "TSN", "HRL", "CF", "MOS", "NTR", "FMC", "CTVA",
]

# Deduplicate while preserving order, remove tickers with dots
seen = set()
UNIQUE_TICKERS = []
for t in STATIC_TICKERS:
    if t not in seen and "." not in t:
        seen.add(t)
        UNIQUE_TICKERS.append(t)
