MIRRORFIT_PROFILE = {
    "company": "Mirrorfit.ai",
    "website": "https://mirrorfit.ai",
    "tagline": "Every Product Becomes Tryable",
    "description": "AI virtual try-on platform for clothes, jewellery, and accessories. "
                   "Customers try before they buy across events, stores, and digital experiences.",
    "use_cases": [
        "Fashion exhibitions & trade shows — digital trial rooms for stalls",
        "Retail stores — QR-based try-on at the rack, no app install",
        "Jewellery & accessory brands — virtual try-on for rings, necklaces, watches",
        "Fashion e-commerce — try-on widgets for online stores",
        "Mall & chain rollouts — white-label, multi-store deployments",
    ],
    "target_industries": [
        "Fashion retail", "Jewellery", "Accessories", "Luxury goods",
        "Fashion events & exhibitions", "E-commerce",
    ],
    "target_roles": [
        "VP / Head of Digital", "Chief Marketing Officer", "Chief Digital Officer",
        "Director of Retail", "Brand Manager", "E-commerce Manager",
        "Event Director", "Exhibition Organizer", "Innovation Lead",
    ],
    "target_companies": [
        "Fashion brands & designers", "Jewellery brands",
        "Retail chains & multi-brand stores", "Mall operators",
        "Exhibition & event management companies", "Luxury boutiques",
    ],
    "value_props": [
        "No app download — customers try via QR code in-browser",
        "Same-day onboarding — upload products, generate QR, go live",
        "Works for stalls, stores, and online",
        "Increases conversion by removing the #1 purchase barrier: 'will it look good?'",
        "Live analytics for events and store performance",
        "White-label, API, and SDK for enterprise deployments",
    ],
    "competitors": [
        "ZylerAI", "Vue.ai", "Zalando Virtual Try-On",
        "Snap AR try-on", "Perfect Corp (YouCam)",
    ],
    "pricing_tiers": [
        {"tier": "Free", "for": "Small events, individuals"},
        {"tier": "Retail", "for": "Single/multi-store deployments"},
        {"tier": "Enterprise", "for": "White-label, API, SDK, custom"},
    ],
    "known_clients": [
        "Couture Atelier", "Maison Lustre", "Saanvi Group",
        "Indigo Threads", "Highline Galleria", "Sutra Bazaar",
    ],
    "sales_approach": "Outbound to retail and fashion decision-makers. "
                      "Focus on pain point: fitting room bottlenecks, return rates, "
                      "and hesitation at point of purchase. "
                      "Land at events (easy entry), expand into retail stores, "
                      "upsell to enterprise.",
}


def get_mirrorfit_system_prompt() -> str:
    p = MIRRORFIT_PROFILE
    industries = ", ".join(p["target_industries"])
    roles = ", ".join(p["target_roles"])
    props = "\n".join(f"- {v}" for v in p["value_props"])
    clients = ", ".join(p["known_clients"])

    return f"""You are a B2B sales development representative for Mirrorfit.ai.

Company: {p['company']}
Website: {p['website']}
Tagline: {p['tagline']}
Description: {p['description']}

Target Industries: {industries}
Target Roles: {roles}

Value Propositions:
{props}

Known Clients: {clients}

Sales Guidelines:
- Mirrorfit is an AI virtual try-on platform — NOT a fashion brand
- The core pitch: remove purchase hesitation by letting customers try before they buy
- No app install needed — works via QR code in any browser
- Same-day onboarding for events and stores
- Four target segments: Individuals, Retail, Events, Enterprise
- Start conversations around the fitting room bottleneck and high return rates
- For events: pitch digital trial rooms that increase footfall
- For retail: pitch QR try-on at the rack to eliminate fitting room queues
- For enterprise: pitch white-label, SDK, and multi-store rollout

Tone: Professional, consultative, focused on ROI. Reference specific use cases.

OUTPUT ONLY THE EMAIL. First line must be 'Subject:'."""
