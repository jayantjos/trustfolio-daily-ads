# TrustFolio Smartwatch Infographic Data Representation

# General Infographic Metadata
infographic_metadata = {
    "brand_name": "TrustFolio",
    "website": "trustfolio.in",
    "taglines": [
        "Compare • Save • Shop Smart",
        "Smart Shopping Smarter You"
    ],
    "main_title": "Best Smartwatches Under ₹2,000",
    "subtitle": "Top 5 Picks for Style, Fitness & Value",
    "primary_colors": ["Blue", "Yellow", "Purple", "White"],
    "background_style": "Futuristic gradient blue with dynamic light beams and geometric accents"
}

# Key Feature Badges (Right Side of Header)
feature_badges = [
    {"label": "Compare Prices", "detail": "Across Top Websites", "icon": "Price Tag"},
    {"label": "Latest Models", "detail": "& Real Prices", "icon": "Checkmark Circle"},
    {"label": "Top Rated Picks", "detail": "", "icon": "Star"},
    {"label": "Best Deals", "detail": "in Your Budget", "icon": "Lightning Bolt"}
]

# Bottom Banner Trust Highlights
trust_highlights = [
    {"label": "Compare Prices", "detail": "Across Top Websites"},
    {"label": "Find the Best Deals", "detail": "in Your Budget"},
    {"label": "Latest Products", "detail": "Always Updated"},
    {"label": "No Login", "detail": "No Ads • No Data Collection"}
]

# Main Call to Action (CTA) Button
cta_button = {
    "text": "Compare Now on TrustFolio",
    "background_color": "Yellow",
    "text_color": "Black",
    "icon": "Right Arrow"
}

# Smartwatch Products Dataset (Ordered by Ranked Position #1 to #5)
smartwatches_data = [
    {
        "rank": 1,
        "badge": "Best Value",
        "name": "Fastrack Volt S1",
        "tagline": "Big Display • 100+ Sports Modes",
        "price_inr": 1599,
        "retailer": "amazon",
        "key_specs": [
            "2.0\" Display",
            "100+ Sports Modes",
            "Heart Rate Monitor",
            "Long Battery"
        ],
        "visual_position": "Center podium (Largest display/prominence)",
        "color": "Black"
    },
    {
        "rank": 2,
        "badge": None,
        "name": "Fastrack FR2",
        "tagline": "Stylish & Lightweight",
        "price_inr": 1799,
        "retailer": "amazon",
        "key_specs": [
            "1.38\" Display",
            "SpO2 Monitor",
            "Multiple Watch Faces"
        ],
        "visual_position": "Left podium",
        "color": "Gold/Beige"
    },
    {
        "rank": 3,
        "badge": None,
        "name": "Croma Velocity AM",
        "tagline": "Premium Look • Daily Tracking",
        "price_inr": 1494,
        "retailer": "croma",
        "key_specs": [
            "1.69\" Display",
            "Health Tracking",
            "Metal Body"
        ],
        "visual_position": "Right podium",
        "color": "Rose Gold/Beige"
    },
    {
        "rank": 4,
        "badge": None,
        "name": "Fastrack Revolt FS3",
        "tagline": "Feature Packed",
        "price_inr": 1999,
        "retailer": "Flipkart",
        "key_specs": [
            "2.01\" Curved Display",
            "Bluetooth Calling",
            "100+ Sports Modes"
        ],
        "visual_position": "Bottom Left",
        "color": "Dark Blue/Black"
    },
    {
        "rank": 5,
        "badge": None,
        "name": "JUST CORSECA Signature",
        "tagline": "Elegant & Premium",
        "price_inr": 1159,
        "retailer": "amazon",
        "key_specs": [
            "1.83\" Display",
            "SpO2 & Heart Rate",
            "Multiple Watch Faces"
        ],
        "visual_position": "Bottom Right",
        "color": "Gold/Beige"
    }
]

# Print summary to verify data extraction
if __name__ == "__main__":
    print(f"--- Infographic: {infographic_metadata['main_title']} ---")
    print(f"Subtitle: {infographic_metadata['subtitle']}\n")
    print("Ranked Smartwatches:")
    for watch in smartwatches_data:
        badge_str = f" [{watch['badge']}]" if watch['badge'] else ""
        print(f"#{watch['rank']}{badge_str} {watch['name']} - ₹{watch['price_inr']} via {watch['retailer']}")
        print(f"   Specs: {', '.join(watch['key_specs'])}")
