#!/usr/bin/env python3
"""
TrustFolio master infographic template data.

This file is the visual/content contract for the approved TrustFolio
reference-style promotional infographic.

IMPORTANT:
- metadata/design_elements/key_usps/footer_trust_factors are template-level
  and may be used by the renderer as fixed design copy.
- smartwatches is the approved reference example supplied for the smartwatch
  campaign. For automated daily ads, production product records should come
  from the daily ad manifest; do not silently invent or overwrite product data.
"""

trustfolio_banner_data = {
    "metadata": {
        "platform_name": "TrustFolio",
        "website": "trustfolio.in",
        "tagline": "Smart Shopping for a Smarter You",
        "header_tagline": "Compare • Save • Shop Smart",
        "campaign_title": "Best Smartwatches Under ₹2,000",
        "campaign_subtitle": "Top 5 Picks for Style, Fitness & Value",
    },
    "design_elements": {
        "background_theme": "Modern Premium Tech Showcase",
        "color_palette": {
            "primary": ["Royal Blue", "Electric Blue", "Dark Navy Blue"],
            "highlights": ["Bright Yellow", "Gold"],
            "text": ["White", "Dark Blue", "Black"],
            "accents": ["Purple"],
        },
        "layout_features": {
            "podium_count": 3,
            "podium_color": "3D Blue",
            "has_top_crown_icon": True,
            "has_cta_search_bar": True,
            "cta_text": "Compare Now on TrustFolio",
        },
    },
    "key_usps": [
        {"title": "Compare Prices", "description": "Across Top Websites", "icon_type": "Tag"},
        {"title": "Latest Models", "description": "& Real Prices", "icon_type": "Checkmark"},
        {"title": "Top Rated Picks", "description": "Based on reviews", "icon_type": "Star"},
        {"title": "Best Deals", "description": "in Your Budget", "icon_type": "Lightning"},
    ],
    "smartwatches": [
        {
            "rank": 1,
            "is_best_value": True,
            "visual_position": "Center Top (Main Podium)",
            "model_name": "Fastrack Volt S1",
            "price_inr": 1599,
            "merchant": "Amazon",
            "visual_details": {
                "dial_shape": "Square",
                "strap_color": "Black",
                "strap_material": "Silicon",
                "screen_display_time": "23:24",
            },
            "key_features": [
                "Big Display", "100+ Sports Modes", "2.0\" Display",
                "Heart Rate Monitor", "Long Battery",
            ],
        },
        {
            "rank": 2,
            "is_best_value": False,
            "visual_position": "Left Top (Side Podium)",
            "model_name": "Fastrack FR2",
            "price_inr": 1799,
            "merchant": "Amazon",
            "visual_details": {
                "dial_shape": "Round",
                "strap_color": "Rose Gold",
                "case_color": "Rose Gold",
                "screen_display_text": "fastrack",
            },
            "key_features": [
                "Stylish & Lightweight", "1.38\" Display",
                "SpO2 Monitor", "Multiple Watch Faces",
            ],
        },
        {
            "rank": 3,
            "is_best_value": False,
            "visual_position": "Right Top (Side Podium)",
            "model_name": "Croma Velocity AM",
            "price_inr": 1494,
            "merchant": "Croma",
            "visual_details": {
                "dial_shape": "Square",
                "strap_color": "Beige / Rose Gold",
                "screen_display_time": "20:20",
            },
            "key_features": [
                "Premium Look", "Daily Tracking", "1.69\" Display",
                "Health Tracking", "Metal Body",
            ],
        },
        {
            "rank": 4,
            "is_best_value": False,
            "visual_position": "Left Bottom",
            "model_name": "Fastrack Revolt FS3",
            "price_inr": 1999,
            "merchant": "Flipkart",
            "visual_details": {
                "dial_shape": "Rectangular Curved",
                "strap_color": "Dark Blue / Black",
                "screen_display_time": "09:40",
            },
            "key_features": [
                "Feature Packed", "2.01\" Curved Display",
                "Bluetooth Calling", "100+ Sports Modes",
            ],
        },
        {
            "rank": 5,
            "is_best_value": False,
            "visual_position": "Right Bottom",
            "model_name": "JUST CORSECA Signature",
            "price_inr": 1159,
            "merchant": "Amazon",
            "visual_details": {
                "dial_shape": "Round",
                "strap_color": "Off-White / Cream",
                "display_type": "Analog Classic Dial",
            },
            "key_features": [
                "Elegant & Premium", "1.83\" Display",
                "SpO2 & Heart Rate", "Multiple Watch Faces",
            ],
        },
    ],
    "footer_trust_factors": [
        {"text": "Compare Prices Across Top Websites", "icon_symbol": "₹"},
        {"text": "Find the Best Deals in Your Budget", "icon_symbol": "Shield"},
        {"text": "Latest Products Always Updated", "icon_symbol": "Check"},
        {"text": "No Login • No Ads • No Data Collection", "icon_symbol": "Star"},
    ],
}


if __name__ == "__main__":
    print(f"Campaign: {trustfolio_banner_data['metadata']['campaign_title']}")
    print("-" * 50)
    for watch in trustfolio_banner_data["smartwatches"]:
        print(
            f"Rank {watch['rank']}: {watch['model_name']} | "
            f"Price: ₹{watch['price_inr']} on {watch['merchant']}"
        )
