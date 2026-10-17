"""ZAYVORA MATAB OS — Classical Asbab-e-Sittah Dietary & Parhez Sheet Generator.
Generates deterministic, classical dietary rules and lifestyle directives based on
Dominant Mizaj, Su-e-Mizaj category, and Affected Organ-Axis.
"""

from typing import Dict, Any, List

MIZAJ_DIET_RULES = {
    "BALGHAMI": {
        "mizaj_label": "Balghami (Cold & Moist / Barid Ratab)",
        "dietary_principle": "Tas-kheen wa Tajfeef (Warming & Drying Diet to counter cold phlegmatic accumulation)",
        "foods_to_avoid": [
            "Dahi, Chaach, Lassi & cold milk (Thandi dairy)",
            "Chawal (Rice) especially cold or refrigerated",
            "Mooli, Kheera, Kakdi, Kaddu (Water-rich cooling vegetables)",
            "Kela (Banana), Amrood, Tarbooz (Cold fruits)",
            "Chilled water, iced drinks, ice creams",
            "Heavy refined flour (Maida), deep-fried oily foods"
        ],
        "foods_to_favor": [
            "Garm masale: Darchini (Cinnamon), Zanjabeel (Dry Ginger), Kali Mirch (Black Pepper), Zeera",
            "Lahsun (Garlic) & Piaz (Onion) lightly cooked",
            "Mutton / Chicken soup seasoned with cloves and black pepper",
            "Moong daal & Kulthi (Horsegram) soup",
            "Lukewarm water boiled with a pinch of saunf (fennel) or ajwain",
            "Dry fruits: Akhrot (Walnuts), Munakka, Khajoor (Dates), Chilghoza",
            "Honey (Shehad) with lukewarm water in the morning"
        ],
        "lifestyle_directives": [
            "Hawa (Air): Stay in warm, well-ventilated, dry quarters; protect chest and joints from cold drafts.",
            "Riyazat (Exercise): Daily brisk walking or moderate physical exertion (Riyazat-e-Mutadilah) for 25-30 minutes before breakfast.",
            "Nawm (Sleep): Avoid sleeping during the daytime (Nawm-un-Nahar produces phlegm); maintain 6-7 hours night sleep.",
            "Istifragh (Excretion): Ensure daily bowel evacuation; avoid suppressing urination or perspiration."
        ]
    },
    "SAFRAWI": {
        "mizaj_label": "Safrawi (Hot & Dry / Haar Yabis)",
        "dietary_principle": "Tabreed wa Tarteeb (Cooling & Moistening Diet to extinguish bilious heat)",
        "foods_to_avoid": [
            "Teekhi Lal Mirch, Garam Masala, Mustard, Hing",
            "Deep-fried snacks (Pakora, Samosa, Puri, Bhaji)",
            "Egg yolk, red meat, beef, organ meats",
            "Pickles (Achar), vinegars, pungent fermented sauces",
            "Excessive strong tea, black coffee, tobacco",
            "Stale, overheated, or salty dry foods"
        ],
        "foods_to_favor": [
            "Sikanjabeen (Lemon-honey or oxymel syrup in cool water)",
            "Tukhm-e-Balanga & Gond Katira soaked in water",
            "Lauki (Bottle Gourd), Torai (Ridge Gourd), Kheera (Cucumber), Palak",
            "Moong daal with a dash of desi ghee",
            "Fruits: Tarbooz (Watermelon), Anaar (Sweet Pomegranate), Angoor (Grapes), Nashpati (Pears)",
            "Maa-ul-Shaeer (Barley water) sweetened with Mishri",
            "Cow's milk boiled with green cardamom and cooled"
        ],
        "lifestyle_directives": [
            "Hawa (Air): Stay in cool, shaded surroundings; avoid prolonged exposure to scorching midday sun.",
            "Riyazat (Exercise): Light morning stroll only; avoid vigorous fatiguing workouts that produce bodily heat.",
            "Nafsani (Emotions): Avoid anger, irritability, and violent arguments (Ghadab excites yellow bile).",
            "Hammam: Cool to lukewarm sponge baths or showers; apply Roghan Gul or Sandal to temples."
        ]
    },
    "DAMWI": {
        "mizaj_label": "Damwi (Hot & Moist / Haar Ratab)",
        "dietary_principle": "Tanqees-e-Ghiza wa Tadeel (Lightening & Equilibrating Diet to reduce sanguineous plethora)",
        "foods_to_avoid": [
            "Red meat, mutton, liver, rich organ preparations",
            "Over-eating, second helpings, heavy late-night dinners",
            "Excessive sweets, creamy pastries, heavy desserts",
            "Spicy oily curries and rich gravies"
        ],
        "foods_to_favor": [
            "Maa-ul-Shaeer (Barley water) with lemon",
            "Anaar (Pomegranate), Seb (Green Apples), Aloo Bukhara (Plums)",
            "Fresh crisp green salads: Chukandar (Beetroot), Salad patta (Lettuce), Gajar",
            "Masoor daal soup with lemon juice",
            "Sprouted moong beans, boiled vegetables",
            "Plenty of fresh pure drinking water throughout the day"
        ],
        "lifestyle_directives": [
            "Hawa (Air): Fresh, cool morning breeze; well-ventilated rooms.",
            "Riyazat (Exercise): Regular active exercise to burn plethoric blood surplus.",
            "Tadbeer: Fasd (Venesection) or Hijama (Wet Cupping) when blood congestion or plethoric pulse is noted.",
            "Istifragh: Intermittent fasting (Sawm) is highly therapeutic for sanguineous temperaments."
        ]
    },
    "SAUDAWI": {
        "mizaj_label": "Saudawi (Cold & Dry / Barid Yabis)",
        "dietary_principle": "Tas-kheen wa Tarteeb (Warming & Humectant Moistening Diet to soften black bile)",
        "foods_to_avoid": [
            "Baingan (Eggplant), Masoor Daal, Gobi (Cabbage/Cauliflower)",
            "Beef (Bada gosht), preserved dried meats, beef curries",
            "Canned, processed, frozen, or stale overnight foods",
            "Excessive dry snacks: Biscuits, crackers, roasted dry chana",
            "Sour citrus, unripe tomatoes, strong black tea"
        ],
        "foods_to_favor": [
            "Badaam (Sweet Almonds) soaked overnight in water, peeled",
            "Injeer (Dry Figs) and Munakka soaked in warm milk",
            "Mutton yakhni (bone broth) cooked with mild spices and a spoon of desi ghee",
            "Kaddu (Pumpkin), Palak (Spinach), Tinda, Chukandar cooked in ghee",
            "Warm fresh cow's milk with a pinch of Zafraan (Saffron)",
            "Shehad (Pure Honey) with warm water",
            "Halwa-e-Gazar or Halwa-e-Baiza Murgh in moderate amount"
        ],
        "lifestyle_directives": [
            "Hawa (Air): Warm, humid, pleasant weather; avoid cold arid winds.",
            "Daluk (Massage): Daily gentle whole-body massage with warm Roghan Badam (Almond oil) or Roghan Zaitoon.",
            "Nafsani (Mental Health): Recreational outings (Tafreeh), pleasant companionship, avoiding solitary isolation and chronic worrying.",
            "Nawm (Sleep): Ensure 7-8 hours deep restful sleep; warm foot-baths before bed."
        ]
    }
}

ORGAN_AXIS_DIET_MODIFIERS = {
    "meda-amaa": {
        "axis_label": "Gastro-Intestinal (Meda wa Am'a)",
        "special_advice": "Eat small, frequent, warm meals. Chew food thoroughly (32 times). Avoid drinking cold water during or immediately after meals (impairs Hazm-e-Midi). Avoid gas-forming legumes (Rajma, Chana) and raw onions."
    },
    "jigar-banas": {
        "axis_label": "Hepato-Metabolic (Jigar wa Banqras)",
        "special_advice": "Avoid all deep-fried fats, trans-fats, hydrogenated oils, alcohol, and synthetic food colors. Favor fresh radish (Mooli) juice, Kasni decoction, and boiled green leafy vegetables to support Quwwat-e-Kabid."
    },
    "dimagh-asab": {
        "axis_label": "Brain & Nervous (Dimagh wa Asab)",
        "special_advice": "Incorporate soaked almonds (Badaam), Walnuts (Akhrot), and Khashkhash (Poppy seeds). Avoid mental fatigue after meals. Take Arq-e-Gaozaban or Chamomile infusion before sleep."
    },
    "qalb-uroq": {
        "axis_label": "Cardio-Vascular (Qalb wa Urooq)",
        "special_advice": "Strictly restrict sodium (table salt). Avoid saturated animal fats. Favor Garlic (Lahsun) 1-2 cloves crushed with honey, Arjuna tea, and Anaar (Pomegranate) juice."
    },
    "mafasil-dam": {
        "axis_label": "Musculo-Skeletal (Mafasil wa Dam)",
        "special_advice": "Avoid uric-acid elevating red meats, organ meats, yeast, and cold sour yogurt. Favor warm turmeric milk (Haldi doodh), Suranjan soup, and ginger-cinnamon infusions."
    }
}

def generate_diet_parhez_sheet(
    dominant_mizaj: str,
    primary_axis_id: str = "meda-amaa",
    su_e_mizaj_type: str = "MADDI"
) -> Dict[str, Any]:
    """Generate deterministic Unani dietary guidelines and lifestyle prescription."""
    clean_mizaj = (dominant_mizaj or "BALGHAMI").upper()
    if clean_mizaj not in MIZAJ_DIET_RULES:
        clean_mizaj = "BALGHAMI"
        
    rule = MIZAJ_DIET_RULES[clean_mizaj]
    axis_key = (primary_axis_id or "meda-amaa").lower().replace(" ", "-")
    axis_modifier = ORGAN_AXIS_DIET_MODIFIERS.get(axis_key, {
        "axis_label": "Systemic Equilibrium",
        "special_advice": "Maintain balanced natural nourishment aligned with bodily digestive capacity."
    })
    
    return {
        "mizaj": clean_mizaj,
        "mizaj_label": rule["mizaj_label"],
        "dietary_principle": rule["dietary_principle"],
        "su_e_mizaj_type": su_e_mizaj_type,
        "foods_to_avoid": rule["foods_to_avoid"],
        "foods_to_favor": rule["foods_to_favor"],
        "lifestyle_directives": rule["lifestyle_directives"],
        "organ_axis_advice": axis_modifier
    }
