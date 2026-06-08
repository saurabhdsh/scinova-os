"""Entity and relationship quality filters — reduce noisy graph nodes."""

import re

from app.services.entity_extractor import ExtractedEntity, ExtractedRelationship

MIN_ENTITY_CONFIDENCE = 0.65
MIN_RELATIONSHIP_CONFIDENCE = 0.55
MAX_CO_OCCURRENCE_PAIRS_PER_CHUNK = 6

# Common document / clinical abbreviations misclassified as genes
GENE_BLOCKLIST = {
    "PDF", "DOCX", "CSV", "XLSX", "JSON", "TXT", "THE", "AND", "FOR", "WITH",
    "FROM", "THIS", "THAT", "FIG", "TABLE", "PAGE", "HTTP", "HTTPS", "API",
    "AA", "AB", "AC", "AD", "AE", "AF", "AG", "AI", "AJ", "AK", "AL", "AM", "AN",
    "AR", "AS", "AT", "AU", "AV", "AW", "AX", "AY", "AZ", "BA", "BB", "BC", "BD",
    "BE", "BF", "BG", "BH", "BI", "BJ", "BK", "BL", "BM", "BN", "BO", "BP", "BQ",
    "BR", "BS", "BT", "BU", "BV", "BW", "BX", "BY", "BZ", "CA", "CB", "CC", "CD",
    "CE", "CF", "CG", "CH", "CI", "CJ", "CK", "CL", "CM", "CN", "CO", "CP", "CQ",
    "CR", "CS", "CT", "CU", "CV", "CW", "CX", "CY", "CZ", "DA", "DB", "DC", "DD",
    "DE", "DF", "DG", "DH", "DI", "DJ", "DK", "DL", "DM", "DN", "DO", "DP", "DQ",
    "DR", "DS", "DT", "DU", "DV", "DW", "DX", "DY", "DZ", "EA", "EB", "EC", "ED",
    "EE", "EF", "EG", "EH", "EI", "EJ", "EK", "EL", "EM", "EN", "EO", "EP", "EQ",
    "ER", "ES", "ET", "EU", "EV", "EW", "EX", "EY", "EZ", "FA", "FB", "FC", "FD",
    "FE", "FF", "FG", "FH", "FI", "FJ", "FK", "FL", "FM", "FN", "FO", "FP", "FQ",
    "FR", "FS", "FT", "FU", "FV", "FW", "FX", "FY", "FZ", "GA", "GB", "GC", "GD",
    "GE", "GF", "GG", "GH", "GI", "GJ", "GK", "GL", "GM", "GN", "GO", "GP", "GQ",
    "GR", "GS", "GT", "GU", "GV", "GW", "GX", "GY", "GZ", "HA", "HB", "HC", "HD",
    "HE", "HF", "HG", "HH", "HI", "HJ", "HK", "HL", "HM", "HN", "HO", "HP", "HQ",
    "HR", "HS", "HT", "HU", "HV", "HW", "HX", "HY", "HZ", "IA", "IB", "IC", "ID",
    "IE", "IF", "IG", "IH", "II", "IJ", "IK", "IL", "IM", "IN", "IO", "IP", "IQ",
    "IR", "IS", "IT", "IU", "IV", "IW", "IX", "IY", "IZ", "JA", "JB", "JC", "JD",
    "JE", "JF", "JG", "JH", "JI", "JJ", "JK", "JL", "JM", "JN", "JO", "JP", "JQ",
    "JR", "JS", "JT", "JU", "JV", "JW", "JX", "JY", "JZ", "KA", "KB", "KC", "KD",
    "KE", "KF", "KG", "KH", "KI", "KJ", "KK", "KL", "KM", "KN", "KO", "KP", "KQ",
    "KR", "KS", "KT", "KU", "KV", "KW", "KX", "KY", "KZ", "LA", "LB", "LC", "LD",
    "LE", "LF", "LG", "LH", "LI", "LJ", "LK", "LL", "LM", "LN", "LO", "LP", "LQ",
    "LR", "LS", "LT", "LU", "LV", "LW", "LX", "LY", "LZ", "MA", "MB", "MC", "MD",
    "ME", "MF", "MG", "MH", "MI", "MJ", "MK", "ML", "MM", "MN", "MO", "MP", "MQ",
    "MR", "MS", "MT", "MU", "MV", "MW", "MX", "MY", "MZ", "NA", "NB", "NC", "ND",
    "NE", "NF", "NG", "NH", "NI", "NJ", "NK", "NL", "NM", "NN", "NO", "NP", "NQ",
    "NR", "NS", "NT", "NU", "NV", "NW", "NX", "NY", "NZ", "OA", "OB", "OC", "OD",
    "OE", "OF", "OG", "OH", "OI", "OJ", "OK", "OL", "OM", "ON", "OO", "OP", "OQ",
    "OR", "OS", "OT", "OU", "OV", "OW", "OX", "OY", "OZ", "PA", "PB", "PC", "PD",
    "PE", "PF", "PG", "PH", "PI", "PJ", "PK", "PL", "PM", "PN", "PO", "PP", "PQ",
    "PR", "PS", "PT", "PU", "PV", "PW", "PX", "PY", "PZ", "QA", "QB", "QC", "QD",
    "QE", "QF", "QG", "QH", "QI", "QJ", "QK", "QL", "QM", "QN", "QO", "QP", "QQ",
    "QR", "QS", "QT", "QU", "QV", "QW", "QX", "QY", "QZ", "RA", "RB", "RC", "RD",
    "RE", "RF", "RG", "RH", "RI", "RJ", "RK", "RL", "RM", "RN", "RO", "RP", "RQ",
    "RR", "RS", "RT", "RU", "RV", "RW", "RX", "RY", "RZ", "SA", "SB", "SC", "SD",
    "SE", "SF", "SG", "SH", "SI", "SJ", "SK", "SL", "SM", "SN", "SO", "SP", "SQ",
    "SR", "SS", "ST", "SU", "SV", "SW", "SX", "SY", "SZ", "TA", "TB", "TC", "TD",
    "TE", "TF", "TG", "TH", "TI", "TJ", "TK", "TL", "TM", "TN", "TO", "TP", "TQ",
    "TR", "TS", "TT", "TU", "TV", "TW", "TX", "TY", "TZ", "UA", "UB", "UC", "UD",
    "UE", "UF", "UG", "UH", "UI", "UJ", "UK", "UL", "UM", "UN", "UO", "UP", "UQ",
    "UR", "US", "UT", "UU", "UV", "UW", "UX", "UY", "UZ", "VA", "VB", "VC", "VD",
    "VE", "VF", "VG", "VH", "VI", "VJ", "VK", "VL", "VM", "VN", "VO", "VP", "VQ",
    "VR", "VS", "VT", "VU", "VV", "VW", "VX", "VY", "VZ", "WA", "WB", "WC", "WD",
    "WE", "WF", "WG", "WH", "WI", "WJ", "WK", "WL", "WM", "WN", "WO", "WP", "WQ",
    "WR", "WS", "WT", "WU", "WV", "WW", "WX", "WY", "WZ", "XA", "XB", "XC", "XD",
    "XE", "XF", "XG", "XH", "XI", "XJ", "XK", "XL", "XM", "XN", "XO", "XP", "XQ",
    "XR", "XS", "XT", "XU", "XV", "XW", "XX", "XY", "XZ", "YA", "YB", "YC", "YD",
    "YE", "YF", "YG", "YH", "YI", "YJ", "YK", "YL", "YM", "YN", "YO", "YP", "YQ",
    "YR", "YS", "YT", "YU", "YV", "YW", "YX", "YY", "YZ", "ZA", "ZB", "ZC", "ZD",
    "ZE", "ZF", "ZG", "ZH", "ZI", "ZJ", "ZK", "ZL", "ZM", "ZN", "ZO", "ZP", "ZQ",
    "ZR", "ZS", "ZT", "ZU", "ZV", "ZW", "ZX", "ZY", "ZZ",
    "VS", "CI", "HR", "OR", "RR", "CI", "SD", "SEM", "IQR", "N", "SD", "SE",
    "PPM", "RPM", "DNA", "RNA", "FDA", "EMA", "GCP", "GMP", "SOP", "QC", "QA",
    "IV", "PO", "SC", "IM", "AE", "SAE", "TEAE", "BID", "TID", "QD", "PRN",
    "WBC", "RBC", "HGB", "PLT", "ALT", "AST", "BUN", "GFR", "ECG", "EKG",
    "MRI", "CT", "PET", "DAS", "ACR", "CRP", "ESR", "BMI", "LDH", "HDL", "LDL",
    "TNF", "IL", "IFN", "VEGF", "HER", "ALK", "ROS", "ATP", "ADP", "GTP",
    "PBO", "PLA", "PLB", "NRS", "ITT", "PP", "FAS", "SAP", "CSR", "IB",
}

KNOWN_GENE_SYMBOLS = {
    "JAK1", "JAK2", "JAK3", "TYK2", "EGFR", "BRAF", "KRAS", "NRAS", "PIK3CA",
    "TP53", "BRCA1", "BRCA2", "HER2", "ERBB2", "PD1", "PDL1", "CTLA4", "VEGFA",
    "MET", "ALK", "RET", "KIT", "FLT3", "IDH1", "IDH2", "STAT1", "STAT3", "MTOR",
}


def _looks_like_gene(name: str) -> bool:
    upper = name.upper().strip()
    if upper in KNOWN_GENE_SYMBOLS:
        return True
    if upper in GENE_BLOCKLIST:
        return False
    if len(upper) < 3:
        return False
    if len(upper) <= 3 and not any(ch.isdigit() for ch in upper):
        return False
    if re.fullmatch(r"[A-Z]{2,}[0-9][A-Z0-9]*", upper):
        return True
    if re.fullmatch(r"[A-Z]{4,}", upper):
        return True
    return False


def is_noisy_entity(name: str, entity_type: str, confidence: float) -> bool:
    cleaned = (name or "").strip()
    if len(cleaned) < 2:
        return True
    if confidence < MIN_ENTITY_CONFIDENCE:
        return True

    upper = cleaned.upper()
    if entity_type == "Gene":
        if upper in GENE_BLOCKLIST:
            return True
        if not _looks_like_gene(cleaned):
            return True

    if entity_type in ("Gene", "Protein", "Target") and len(cleaned) <= 2:
        return True

    if entity_type == "Gene" and cleaned.isupper() and len(cleaned) == 3 and upper not in KNOWN_GENE_SYMBOLS:
        if not any(ch.isdigit() for ch in cleaned):
            return True

    return False


def filter_entities(entities: list[ExtractedEntity]) -> list[ExtractedEntity]:
    return [
        ent for ent in entities
        if not is_noisy_entity(ent.name, ent.entity_type, ent.confidence)
    ]


def is_noisy_relationship(rel: ExtractedRelationship) -> bool:
    if rel.confidence < MIN_RELATIONSHIP_CONFIDENCE:
        return True
    if rel.relationship_type == "ASSOCIATED_WITH":
        if rel.source_type == "Gene" and rel.target_type == "Gene":
            if not _looks_like_gene(rel.source_name) or not _looks_like_gene(rel.target_name):
                return True
        if len(rel.source_name) <= 2 or len(rel.target_name) <= 2:
            return True
    return False


def filter_relationships(relationships: list[ExtractedRelationship]) -> list[ExtractedRelationship]:
    filtered = [r for r in relationships if not is_noisy_relationship(r)]
    deduped: dict[tuple[str, str, str], ExtractedRelationship] = {}
    for rel in filtered:
        key = (rel.source_name.lower(), rel.target_name.lower(), rel.relationship_type)
        existing = deduped.get(key)
        if existing is None or rel.confidence > existing.confidence:
            deduped[key] = rel
    return sorted(deduped.values(), key=lambda r: r.confidence, reverse=True)
