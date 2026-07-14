CATEGORIES = {
    "luxury": {
        "label": "Luxury & Premium Fashion",
        "pitch_angle": "Premium virtual try-on that reduces returns on high-value items and elevates the online shopping experience for discerning customers.",
        "subject_patterns": [
            "Elevating [brand]'s digital experience",
            "Virtual try-on for [brand]'s clientele",
            "Reducing returns on premium pieces",
        ],
        "body_focus": "Exclusivity, white-glove experience, ROI on high-value inventory, fitting room bottlenecks for luxury shoppers",
        "match_keywords": ["luxury", "premium", "haute", "couture", "designer", "high-end"],
    },
    "fast_fashion": {
        "label": "Fast Fashion & Mass Retail",
        "pitch_angle": "Same-day VTO onboarding that cuts return rates and gives mass retailers a competitive edge in a crowded market.",
        "subject_patterns": [
            "Cutting returns for [brand]",
            "Quick question about [brand]'s online experience",
            "VTO in 24 hours for [brand]",
        ],
        "body_focus": "Return rate reduction, speed to market, competitive differentiation, no app install for customers",
        "match_keywords": ["fast fashion", "mass market", "high street", "h&m", "zara", "mango", "forever 21", "pantaloons", "max fashion"],
    },
    "department_store": {
        "label": "Department Stores & Multi-brand Retailers",
        "pitch_angle": "White-label VTO that works across all brands in your portfolio — one integration, zero friction for every vendor.",
        "subject_patterns": [
            "VTO across [brand]'s portfolio",
            "Omnichannel try-on for [brand]",
            "One VTO integration for all your brands",
        ],
        "body_focus": "Multi-brand solution, white-label, omnichannel (stores + online), vendor-agnostic, mall/chain rollouts",
        "match_keywords": ["department store", "multi-brand", "lifestyle", "shoppers stop", "westside", "shoppersstop", "lifestyle stores"],
    },
    "d2c": {
        "label": "D2C & Emerging Brands",
        "pitch_angle": "Go live with QR-based VTO today — zero dev work, no app, and an instant edge against bigger competitors.",
        "subject_patterns": [
            "[brand] — try-on live today",
            "Virtual try-on in one day for [brand]",
            "Give [brand]'s customers a try-before-you-buy experience",
        ],
        "body_focus": "Zero code, same-day go-live, QR-based, affordable entry point, compete with bigger brands",
        "match_keywords": ["d2c", "direct-to-consumer", "independent", "emerging", "studio", "boutique", "founder-led"],
    },
    "mall_operator": {
        "label": "Malls & Retail Operators",
        "pitch_angle": "White-label VTO for malls that drives footfall, increases dwell time, and gives tenants a reason to stay — with live analytics per store.",
        "subject_patterns": [
            "VTO for [brand]'s retail spaces",
            "Interactive experiences for [brand]'s visitors",
            "Drive footfall with QR try-on at [brand]",
        ],
        "body_focus": "Tenant solution, footfall analytics, dwell time, white-label for malls, multi-store deployments",
        "match_keywords": ["mall", "retail group", "landmark", "reliance", "majid al futtaim", "operator", "holding"],
    },
    "ecommerce_platform": {
        "label": "Fashion E-commerce Platforms",
        "pitch_angle": "API-first VTO integration that reduces platform-wide return rates by 20%+ and keeps buyers on your site longer.",
        "subject_patterns": [
            "VTO API for [brand]",
            "Reducing returns across [brand]'s catalog",
            "Try-on widget for [brand]'s marketplace",
        ],
        "body_focus": "API/SDK integration, platform-wide return reduction, marketplace enablement, scale, retention",
        "match_keywords": ["marketplace", "platform", "flipkart", "ajio", "tata cliq", "shopify", "myntra", "nykaa"],
    },
}

CATEGORY_SLUGS = list(CATEGORIES.keys())

DOMAIN_PATTERNS = {
    "luxury": [],
    "fast_fashion": ["hm.com", "zara.com", "mango.com", "forever21.com", "tkmaxx.com"],
    "department_store": ["shoppersstop.com", "westside.com", "lifestyle.co.in"],
    "d2c": [],
    "mall_operator": ["majidalfuttaim.com", "landmarkgroup.com", "reliancebrands.com"],
    "ecommerce_platform": ["myntra.com", "nykaa.com", "ajio.com", "tatacliq.com", "flipkart.com", "eyewa.com"],
}

COMPANY_NAME_PATTERNS = {
    "luxury": ["bulgari", "gucci", "prada", "lv ", "louis vuitton", "dior", "chanel", "cartier", "tiffany", "versace", "armani", "ralph lauren", "burberry", "givenchy", "fendi", "hermes"],
    "fast_fashion": ["h&m", "zara", "mango", "uniqlo", "forever 21", "pantaloons", "max fashion", "tommy hilfiger", "calvin klein", "levi"],
    "department_store": ["shoppers stop", "westside", "lifestyle", "bloomingdales", "nordstrom", "macy"],
    "d2c": ["99 colors", "bewakoof", "souled store", "bombay shirt", "blissclub"],
    "mall_operator": ["majid al futtaim", "landmark", "reliance brands", "al shaya", "phenomenal"],
    "ecommerce_platform": ["myntra", "nykaa", "ajio", "tata cliq", "flipkart", "eyewa", "meshoo", "meesho", "shopify"],
}


def classify_lead(*, company: str = "", industry: str = "",
                  title: str = "", company_domain: str = "",
                  about: str = "") -> str:
    text = f"{company} {industry} {title} {about}".lower()
    company_lower = company.lower()

    for slug, domains in DOMAIN_PATTERNS.items():
        for d in domains:
            if d in text or (company_domain and d in company_domain.lower()):
                return slug

    for slug, names in COMPANY_NAME_PATTERNS.items():
        for n in names:
            if n in company_lower:
                return slug

    for slug, cat in CATEGORIES.items():
        for kw in cat.get("match_keywords", []):
            if kw.lower() in text:
                return slug

    if company_domain:
        domain_lower = company_domain.lower()
        if any(tld in domain_lower for tld in [".in", ".co.in", "india"]):
            if any(kw in text for kw in ["fashion", "apparel", "retail", "clothing"]):
                return "d2c"

    if "retail" in text or "fashion" in text or "apparel" in text:
        return "fast_fashion"

    return "fast_fashion"


def get_category_prompt(category: str = "") -> str:
    if not category or category not in CATEGORIES:
        return ""
    cat = CATEGORIES[category]
    return f"""
CATEGORY: {cat['label']}
PITCH ANGLE: {cat['pitch_angle']}
FOCUS: {cat['body_focus']}
"""
