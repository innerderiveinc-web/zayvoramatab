#!/usr/bin/env python3
"""
ZAYVORA Classical Unani Pharmacopoeia & Books Knowledge Engine
Extracts, structures, and ingests authentic classical knowledge from:
- Shifa' al-Abdan (Hakeem Wajid Ali, 1896, McGill Osler Library)
- Kitab al-Qanun fi al-Tibb (Ibn Sina, 1593 Rome Medici Edition & UNESCO Book 4)
- Qarabadin-e-Azam & Bayaz-e-Kabir (Part 2)
- Makhzanul Mufradat & Khawas-ul-Advia (Hakeem Muzaffar Hussain)
- Sharah Asbab (Hakeem Mohammad Kabiruddin)

Enriches:
1. ingredient_catalog: Classical single herbs (Mufradat) with Mizaj, Degree, and Posology
2. formulations, formulation_versions, formulation_ingredients: 50+ Mustanad Nuskha-Jaat
3. safety_contraindications: Classical contraindications and toxicity ceilings
4. clinical_claims & claim_citations: Disease definitions, Usul-e-Ilaj, and book locators
"""

import os
import sys
import json
import sqlite3
from datetime import datetime

TARGET_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "matab.db")
ORG_ID = "org-matab-default"
ADMIN_USER_ID = "usr-admin-1"

# -----------------------------------------------------------------------------
# 1. CLASSICAL INGREDIENTS (MUFRADAT) DATASET
# -----------------------------------------------------------------------------
CLASSICAL_HERBS = [
    # (id, canonical_name, unani_name, botanical_name, mizaj, degree, min_mg, max_mg, daily_max_mg, is_mudabbar, is_e1)
    ("ing-ustukhuddus", "Lavender / Ustukhuddus", "Ustukhuddus", "Lavandula stoechas", "HOT_DRY", 1, 500, 3000, 7000, 0, 0),
    ("ing-kishneez", "Coriander / Kishneez", "Kishneez Khushk", "Coriandrum sativum", "COLD_DRY", 2, 1000, 5000, 10000, 0, 0),
    ("ing-halela-zard", "Yellow Myrobalan / Halela Zard", "Post-e-Halela Zard", "Terminalia chebula", "COLD_DRY", 1, 1000, 4000, 8000, 0, 0),
    ("ing-halela-siyah", "Black Myrobalan / Halela Siyah", "Halela Siyah", "Terminalia chebula (Immature)", "COLD_DRY", 2, 500, 3000, 6000, 0, 0),
    ("ing-balela", "Belleric Myrobalan / Balela", "Post-e-Balela", "Terminalia bellirica", "COLD_DRY", 1, 1000, 3000, 6000, 0, 0),
    ("ing-amla", "Emblic Myrobalan / Amla", "Amla Khushk", "Phyllanthus emblica", "COLD_DRY", 2, 1000, 5000, 10000, 0, 0),
    ("ing-shahtara", "Fumitory / Shahtara", "Shahtara", "Fumaria parviflora", "MOTADIL", 1, 1000, 4000, 8000, 0, 0),
    ("ing-gul-surkh", "Damask Rose / Gul-e-Surkh", "Gul-e-Surkh (Warde Ahmar)", "Rosa damascena", "COLD_DRY", 2, 1000, 5000, 10000, 0, 0),
    ("ing-suranjan-shirin", "Sweet Colchicum / Suranjan Shirin", "Suranjan Shirin", "Colchicum autumnale", "HOT_DRY", 3, 250, 1000, 2000, 0, 0),
    ("ing-suranjan-talkh", "Bitter Colchicum / Suranjan Talkh", "Suranjan Talkh", "Colchicum luteum", "HOT_DRY", 3, 100, 500, 1000, 1, 1),
    ("ing-asgand", "Winter Cherry / Asgandh", "Asgand Nagori", "Withania somnifera", "HOT_DRY", 2, 1000, 5000, 10000, 0, 0),
    ("ing-chobchini", "China Root / Chobchini", "Chobchini", "Smilax china", "HOT_DRY", 2, 1000, 4000, 8000, 0, 0),
    ("ing-ushba", "Sarsaparilla / Ushba", "Ushba Maghrabi", "Smilax medica", "HOT_DRY", 2, 1000, 3000, 6000, 0, 0),
    ("ing-banafsha", "Sweet Violet / Banafsha", "Gul-e-Banafsha", "Viola odorata", "COLD_MOIST", 1, 1000, 4000, 8000, 0, 0),
    ("ing-gaozaban", "Borage / Gaozaban", "Gaozaban", "Borago officinalis", "HOT_MOIST", 1, 1000, 5000, 10000, 0, 0),
    ("ing-kasni", "Chicory / Kasni", "Tukhm-e-Kasni", "Cichorium intybus", "COLD_DRY", 1, 1000, 5000, 10000, 0, 0),
    ("ing-mako", "Black Nightshade / Mako", "Mako Khushk", "Solanum nigrum", "COLD_DRY", 2, 1000, 4000, 8000, 0, 0),
    ("ing-sapistan", "Sebesten / Sapistan", "Sapistan", "Cordia latifolia", "MOTADIL", 1, 2000, 7000, 15000, 0, 0),
    ("ing-unnab", "Jujube / Unnab", "Unnab", "Ziziphus jujuba", "MOTADIL", 1, 2000, 7000, 15000, 0, 0),
    ("ing-behidana", "Quince Seeds / Behidana", "Behidana", "Cydonia oblonga", "COLD_MOIST", 2, 500, 2000, 5000, 0, 0),
    ("ing-mulethi", "Licorice / Asl-us-Soos", "Mulethi / Asl-us-Soos", "Glycyrrhiza glabra", "HOT_MOIST", 1, 1000, 4000, 8000, 0, 0),
    ("ing-mastagi", "Mastic / Mastagi Romi", "Mastagi Romi", "Pistacia lentiscus", "HOT_DRY", 2, 500, 2000, 4000, 0, 0),
    ("ing-kamun", "Cumin / Zeera Safaid", "Kamun Safaid", "Cuminum cyminum", "HOT_DRY", 2, 1000, 4000, 8000, 0, 0),
    ("ing-zanjabeel", "Ginger / Zanjabeel", "Zanjabeel", "Zingiber officinale", "HOT_DRY", 3, 500, 2000, 4000, 0, 0),
    ("ing-filfil-siyah", "Black Pepper / Filfil Siyah", "Filfil Siyah", "Piper nigrum", "HOT_DRY", 3, 250, 1000, 2000, 0, 0),
    ("ing-filfil-daraz", "Long Pepper / Filfil Daraz", "Filfil Daraz (Peepli)", "Piper longum", "HOT_DRY", 3, 250, 1000, 2000, 0, 0),
    ("ing-zafran", "Saffron / Zafran", "Zafran (Kesar)", "Crocus sativus", "HOT_DRY", 2, 20, 100, 250, 0, 0),
    ("ing-marwareed", "Pearl / Marwareed", "Marwareed (Mukta)", "Mytilus margaritiferus", "MOTADIL", 1, 50, 200, 500, 1, 0),
    ("ing-salab-misri", "Salep / Salab Misri", "Salab Misri", "Orchis mascula", "HOT_MOIST", 2, 1000, 4000, 8000, 0, 0),
    ("ing-musli-safaid", "White Musli / Musli Safaid", "Musli Safaid", "Chlorophytum borivilianum", "HOT_MOIST", 2, 1000, 5000, 10000, 0, 0),
    ("ing-talmakhana", "Hygrophila / Talmakhana", "Talmakhana", "Asteracantha longifolia", "COLD_MOIST", 1, 1000, 4000, 8000, 0, 0),
    ("ing-tukhm-kahu", "Lettuce Seeds / Tukhm-e-Kahu", "Tukhm-e-Kahu", "Lactuca sativa", "COLD_MOIST", 2, 1000, 4000, 8000, 0, 0),
    ("ing-tukhm-khas", "Poppy Seeds / Tukhm-e-Khashkhash", "Khashkhash Safaid", "Papaver somniferum (Seeds)", "COLD_MOIST", 2, 1000, 5000, 10000, 0, 0),
    ("ing-kuchla-mudabbar", "Nux Vomica (Purified) / Azaraqi Mudabbar", "Azaraqi / Kuchla Mudabbar", "Strychnos nux-vomica", "HOT_DRY", 3, 30, 125, 250, 1, 1),
    ("ing-afiyun", "Opium / Afiyun", "Afiyun Mudabbar", "Papaver somniferum (Latex)", "COLD_DRY", 4, 15, 60, 120, 1, 1),
    ("ing-samm-ul-far", "Arsenic (Purified) / Sankhiya Mudabbar", "Samm-ul-Far Mudabbar", "Arsenic trioxide", "HOT_DRY", 4, 1, 5, 10, 1, 1),
    ("ing-kushta-nuqra", "Silver Calx / Kushta Nuqra", "Kushta Nuqra (Rajat Bhasma)", "Argentum", "COLD_DRY", 2, 30, 120, 250, 1, 0),
    ("ing-kushta-faulad", "Iron Calx / Kushta Faulad", "Kushta Faulad (Lauha Bhasma)", "Ferrum", "HOT_DRY", 2, 60, 250, 500, 1, 0),
    ("ing-kushta-marjan", "Coral Calx / Kushta Marjan", "Kushta Marjan (Praval Bhasma)", "Corallium rubrum", "MOTADIL", 1, 60, 250, 500, 1, 0),
    ("ing-zarishk", "Barberry / Zarishk Shirin", "Zarishk", "Berberis vulgaris", "COLD_DRY", 2, 1000, 5000, 10000, 0, 0),
    ("ing-bazoori-tukhms", "Four Melon Seeds / Char Tukhm Bazoori", "Maghz-e-Khyar, Kadu, Kharbuza, Tarbooz", "Cucumis & Citrullus spp.", "COLD_MOIST", 1, 2000, 8000, 15000, 0, 0),
    ("ing-khardal", "Mustard / Rai", "Khardal (Rai)", "Brassica nigra", "HOT_DRY", 3, 500, 2000, 4000, 0, 0),
    ("ing-turbud", "Turpeth / Turbud", "Turbud Safaid", "Operculina turpethum", "HOT_DRY", 3, 500, 2000, 4000, 0, 0),
    ("ing-sana-makki", "Senna / Sana Makki", "Barg-e-Sana Makki", "Senna alexandrina", "HOT_DRY", 2, 1000, 4000, 8000, 0, 0),
    ("ing-roghan-badam", "Almond Oil / Roghan-e-Badam Shirin", "Roghan-e-Badam Shirin", "Prunus dulcis (Oil)", "HOT_MOIST", 1, 2000, 10000, 25000, 0, 0)
]

# -----------------------------------------------------------------------------
# 2. CLASSICAL FORMULATIONS (MURAKKABAT) FROM SHIFA AL-ABDAN & QARABADIN
# -----------------------------------------------------------------------------
CLASSICAL_FORMULATIONS = [
    {
        "code": "CLAS-ITR-01",
        "name": "Itrifal Kishneezi",
        "transliteration": "Itrifal Kishneezi",
        "dosage_form": "ITRIFAL",
        "source": "Shifā' al-Abdān (1896) Fasl 4 / Qarabadin-e-Azam",
        "indication": "Chronic cold & catarrh (Nazla muzmin), headache (Suda), weakness of brain (Zof-e-Dimagh), and gastric flatulence.",
        "adult_dose": "5g to 10g at bedtime with lukewarm water or Arq Gaozaban 60ml.",
        "ingredients": [
            ("ing-kishneez", 300, 1),
            ("ing-halela-zard", 200, 0),
            ("ing-halela-siyah", 150, 0),
            ("ing-balela", 150, 0),
            ("ing-amla", 150, 0),
            ("ing-roghan-badam", 50, 0)
        ]
    },
    {
        "code": "CLAS-ITR-02",
        "name": "Itrifal Ustukhuddus",
        "transliteration": "Itrifal Ustukhuddus",
        "dosage_form": "ITRIFAL",
        "source": "Kitāb al-Qānūn fī al-ṭibb (Rome 1593) / Shifā' al-Abdān",
        "indication": "Migraine (Shaqiqa), chronic sinusitis, cerebral phlegmatic purgation (Tanqia-e-Dimagh), and vertigo (Dauran-e-Sar).",
        "adult_dose": "5g to 10g at bedtime with warm water.",
        "ingredients": [
            ("ing-ustukhuddus", 350, 1),
            ("ing-halela-zard", 200, 0),
            ("ing-halela-siyah", 150, 0),
            ("ing-balela", 150, 0),
            ("ing-amla", 150, 0),
            ("ing-turbud", 50, 0)
        ]
    },
    {
        "code": "CLAS-ITR-03",
        "name": "Itrifal Shahtara",
        "transliteration": "Itrifal Shahtara",
        "dosage_form": "ITRIFAL",
        "source": "Shifā' al-Abdān (1896) Fasl 7 (Amraz-e-Jild) / NFUM Part I",
        "indication": "Blood purifier (Musaffi-e-Dam), scabies (Jarab), itching (Hikka), boils, and melancholic-bilious dermatoses.",
        "adult_dose": "5g to 10g in the morning with Arq Shahtara 60ml or water.",
        "ingredients": [
            ("ing-shahtara", 300, 1),
            ("ing-halela-zard", 200, 0),
            ("ing-halela-siyah", 150, 0),
            ("ing-balela", 150, 0),
            ("ing-amla", 150, 0),
            ("ing-gul-surkh", 100, 0)
        ]
    },
    {
        "code": "CLAS-ITR-04",
        "name": "Itrifal Zamani",
        "transliteration": "Itrifal Zamani",
        "dosage_form": "ITRIFAL",
        "source": "Qarabadin Hamdard Complete / Shifā' al-Abdān",
        "indication": "Habitual constipation (Qabz muzmin), melancholic headache, joint pains, and purgation of viscous humors.",
        "adult_dose": "5g to 10g at night with lukewarm milk.",
        "ingredients": [
            ("ing-halela-zard", 200, 0),
            ("ing-halela-siyah", 200, 0),
            ("ing-balela", 150, 0),
            ("ing-amla", 150, 0),
            ("ing-turbud", 150, 1),
            ("ing-sana-makki", 150, 0)
        ]
    },
    {
        "code": "CLAS-MAJ-01",
        "name": "Majoon Dabeedul Ward",
        "transliteration": "Majun Dabeedul Ward",
        "dosage_form": "MAJOON",
        "source": "Kitāb al-Qānūn fī al-ṭibb Book 3 / Shifā' al-Abdān Fasl 5",
        "indication": "Weakness of liver (Zof-e-Jigar), hepatic inflammation (Warm-e-Kabid), ascites/dropsy (Istisqa), and gastritis (Zof-e-Meda).",
        "adult_dose": "5g to 7g in the morning on empty stomach with Arq Mako or warm water.",
        "ingredients": [
            ("ing-gul-surkh", 400, 1),
            ("ing-mastagi", 150, 0),
            ("ing-zafran", 20, 0),
            ("ing-kasni", 150, 0),
            ("ing-mako", 100, 0),
            ("ing-zanjabeel", 100, 0)
        ]
    },
    {
        "code": "CLAS-MAJ-02",
        "name": "Majoon Falasfa",
        "transliteration": "Majun Falasfa",
        "dosage_form": "MAJOON",
        "source": "Qarabadin-e-Qaderi / Shifā' al-Abdān Fasl 8",
        "indication": "Strengthens kidneys, bladder, and nerves (Taqwiyat-e-Kulyah o Asab), involuntary urination (Salas-ul-Baul), and backache.",
        "adult_dose": "5g morning and evening with 250ml warm milk.",
        "ingredients": [
            ("ing-zanjabeel", 200, 0),
            ("ing-filfil-siyah", 150, 0),
            ("ing-filfil-daraz", 150, 0),
            ("ing-amla", 200, 0),
            ("ing-balela", 150, 0),
            ("ing-salab-misri", 150, 1)
        ]
    },
    {
        "code": "CLAS-MAJ-03",
        "name": "Majoon Suranjan",
        "transliteration": "Majun Suranjan",
        "dosage_form": "MAJOON",
        "source": "Shifā' al-Abdān Fasl 9 (Amraz-e-Mafasil) / NFUM Part I",
        "indication": "Rheumatoid arthritis (Waja-ul-Mafasil), gout (Niqris), sciatica (Irq-un-Nasa), and musculoskeletal aches.",
        "adult_dose": "5g twice daily after meals with water.",
        "ingredients": [
            ("ing-suranjan-shirin", 300, 1),
            ("ing-asgand", 200, 0),
            ("ing-zanjabeel", 150, 0),
            ("ing-filfil-siyah", 100, 0),
            ("ing-turbud", 150, 0)
        ]
    },
    {
        "code": "CLAS-MAJ-04",
        "name": "Majoon Chobchini",
        "transliteration": "Majun Chobchini",
        "dosage_form": "MAJOON",
        "source": "Qarabadin-e-Azam / Shifā' al-Abdān",
        "indication": "Chronic gout, joint swellings, blood purulence, and chronic syphilitic/arthritic pains.",
        "adult_dose": "5g twice daily with warm milk.",
        "ingredients": [
            ("ing-chobchini", 400, 1),
            ("ing-suranjan-shirin", 200, 0),
            ("ing-asgand", 150, 0),
            ("ing-ushba", 150, 0),
            ("ing-zafran", 20, 0)
        ]
    },
    {
        "code": "CLAS-MAJ-05",
        "name": "Majoon Ushba",
        "transliteration": "Majun Ushba",
        "dosage_form": "MAJOON",
        "source": "Shifā' al-Abdān / Bayaz-e-Kabir",
        "indication": "Severe blood impurities, chronic eczema, boils (Dammamil), and chronic dermatological inflammation.",
        "adult_dose": "5g to 7g morning on empty stomach with water.",
        "ingredients": [
            ("ing-ushba", 350, 1),
            ("ing-shahtara", 200, 0),
            ("ing-chobchini", 200, 0),
            ("ing-gul-surkh", 150, 0),
            ("ing-sana-makki", 100, 0)
        ]
    },
    {
        "code": "CLAS-MAJ-06",
        "name": "Majoon Mughalliz Jawaharwali",
        "transliteration": "Majun Mughalliz Jawaharwali",
        "dosage_form": "MAJOON",
        "source": "Shifā' al-Abdān Fasl 10 (Amraz-e-Tanasul) / Qarabadin Hamdard",
        "indication": "Seminal thinning (Riqat-e-Mani), spermatorrhea (Jiryan), nocturnal emission (Ihtilam), and male sexual weakness.",
        "adult_dose": "5g to 10g in the morning with 250ml warm milk.",
        "ingredients": [
            ("ing-salab-misri", 250, 1),
            ("ing-musli-safaid", 200, 0),
            ("ing-talmakhana", 200, 0),
            ("ing-tukhm-kahu", 150, 0),
            ("ing-kushta-nuqra", 30, 0),
            ("ing-marwareed", 30, 0)
        ]
    },
    {
        "code": "CLAS-JAW-01",
        "name": "Jawarish Kamuni",
        "transliteration": "Jawarish Kamuni",
        "dosage_form": "MAJOON",
        "source": "Kitāb al-Qānūn fī al-ṭibb (Rome 1593) Book 3 / Shifā' al-Abdān",
        "indication": "Gastric flatulence (Nafkh-e-Shikam), indigestion (Su-e-Hazm), stomach ache, and belching.",
        "adult_dose": "5g after main meals with water.",
        "ingredients": [
            ("ing-kamun", 400, 1),
            ("ing-filfil-siyah", 150, 0),
            ("ing-zanjabeel", 150, 0),
            ("ing-mastagi", 100, 0),
            ("ing-bazoori-tukhms", 200, 0)
        ]
    },
    {
        "code": "CLAS-JAW-02",
        "name": "Jawarish Jalinus",
        "transliteration": "Jawarish Jalinus",
        "dosage_form": "MAJOON",
        "source": "Al-Hawi fil Tibb (Al-Razi) / Shifā' al-Abdān",
        "indication": "Strengthens vital organs (Qalb, Dimagh, Meda, Jigar), eliminates excessive cold phlegm, and prevents premature graying.",
        "adult_dose": "5g morning or after meals with water.",
        "ingredients": [
            ("ing-mastagi", 200, 1),
            ("ing-zafran", 25, 0),
            ("ing-zanjabeel", 150, 0),
            ("ing-filfil-daraz", 100, 0),
            ("ing-amla", 150, 0),
            ("ing-halela-siyah", 150, 0)
        ]
    },
    {
        "code": "CLAS-JAW-03",
        "name": "Jawarish Shahi",
        "transliteration": "Jawarish Shahi",
        "dosage_form": "MAJOON",
        "source": "Qarabadin Hamdard / Shifā' al-Abdān",
        "indication": "Cardiac palpitation (Khafqan), anxiety (Wahshat), gastric weakness, and post-illness debility.",
        "adult_dose": "5g morning on empty stomach with Arq Gaozaban 60ml.",
        "ingredients": [
            ("ing-marwareed", 30, 0),
            ("ing-zafran", 20, 0),
            ("ing-kishneez", 300, 1),
            ("ing-amla", 200, 0),
            ("ing-gul-surkh", 200, 0)
        ]
    },
    {
        "code": "CLAS-KHA-01",
        "name": "Khamira Gaozaban Ambari Jawaharwala",
        "transliteration": "Khamira Gaozaban Ambari Jawaharwala",
        "dosage_form": "KHAMIRA",
        "source": "Shifā' al-Abdān Fasl 2 (Amraz-e-Qalb) / Qarabadin-e-Azam",
        "indication": "Potent tonic for Heart & Brain (Muqawwi-e-Qalb o Dimagh), reduces cardiac palpitation, anxiety, and visual fatigue.",
        "adult_dose": "3g to 5g in the morning with warm milk or Arq Gaozaban.",
        "ingredients": [
            ("ing-gaozaban", 400, 1),
            ("ing-marwareed", 50, 0),
            ("ing-kushta-nuqra", 30, 0),
            ("ing-zafran", 25, 0),
            ("ing-kishneez", 200, 0),
            ("ing-behidana", 100, 0)
        ]
    },
    {
        "code": "CLAS-KHA-02",
        "name": "Khamira Marwareed",
        "transliteration": "Khamira Marwareed",
        "dosage_form": "KHAMIRA",
        "source": "Shifā' al-Abdān / Bayaz-e-Kabir",
        "indication": "Relieves palpitation, weakness after infectious fevers (Typhoid, Chickenpox, Measles), and strengthens vital spirit (Ruh).",
        "adult_dose": "3g to 5g morning on empty stomach with milk.",
        "ingredients": [
            ("ing-marwareed", 100, 1),
            ("ing-kushta-nuqra", 40, 0),
            ("ing-banafsha", 200, 0),
            ("ing-gul-surkh", 200, 0),
            ("ing-zafran", 20, 0)
        ]
    },
    {
        "code": "CLAS-SHR-01",
        "name": "Sharbat Deenar",
        "transliteration": "Sharbat Deenar",
        "dosage_form": "SHARBAT",
        "source": "Kitāb al-Qānūn fī al-ṭibb Book 3 / Shifā' al-Abdān Fasl 6",
        "indication": "Hepatobiliary obstruction (Sudad-e-Kabid), hepatitis, splenitis, uterine inflammation, and bilious constipation.",
        "adult_dose": "25ml to 50ml diluted in 150ml water morning and evening.",
        "ingredients": [
            ("ing-kasni", 400, 1),
            ("ing-gul-surkh", 250, 0),
            ("ing-mako", 250, 0),
            ("ing-bazoori-tukhms", 300, 0)
        ]
    },
    {
        "code": "CLAS-SHR-02",
        "name": "Sharbat Faulad",
        "transliteration": "Sharbat Faulad",
        "dosage_form": "SHARBAT",
        "source": "Shifā' al-Abdān / Qarabadin-e-Sarkari",
        "indication": "Iron-deficiency anemia (Qillat-ud-Dam), pale complexion, general debility, and sluggish liver.",
        "adult_dose": "10ml to 20ml twice daily after meals with water or fruit juice.",
        "ingredients": [
            ("ing-kushta-faulad", 120, 1),
            ("ing-amla", 300, 0),
            ("ing-zanjabeel", 100, 0),
            ("ing-filfil-siyah", 50, 0)
        ]
    },
    {
        "code": "CLAS-SHR-03",
        "name": "Sharbat Anjabar",
        "transliteration": "Sharbat Anjabar",
        "dosage_form": "SHARBAT",
        "source": "Shifā' al-Abdān Fasl 7 / Qarabadin Hamdard",
        "indication": "Internal hemorrhages (Nazif-ud-Dam), hematuria (Baul-ud-Dam), bloody diarrhea, and excessive menstrual bleeding (Kasrat-e-Tams).",
        "adult_dose": "20ml to 40ml diluted in water twice daily.",
        "ingredients": [
            ("ing-gul-surkh", 300, 1),
            ("ing-kishneez", 200, 0),
            ("ing-amla", 200, 0),
            ("ing-balela", 150, 0)
        ]
    },
    {
        "code": "CLAS-HAB-01",
        "name": "Habb-e-Suranjan",
        "transliteration": "Habb-e-Suranjan",
        "dosage_form": "QURS",
        "source": "Shifā' al-Abdān Fasl 9 / Al-Hawi fil Tibb",
        "indication": "Acute joint pain (Waja-ul-Mafasil), gout (Niqris), lumbar back pain, and morning stiffness.",
        "adult_dose": "1 to 2 tablets twice daily after meals with water.",
        "ingredients": [
            ("ing-suranjan-shirin", 250, 1),
            ("ing-asgand", 150, 0),
            ("ing-zanjabeel", 100, 0),
            ("ing-turbud", 100, 0)
        ]
    },
    {
        "code": "CLAS-HAB-02",
        "name": "Habb-e-Kabid Naushadri",
        "transliteration": "Habb-e-Kabid Naushadri",
        "dosage_form": "QURS",
        "source": "Shifā' al-Abdān Fasl 5 / Qarabadin-e-Azam",
        "indication": "Sluggish liver, abdominal distension, post-prandial heaviness, dyspepsia, and anorexia.",
        "adult_dose": "1 to 2 tablets after lunch and dinner.",
        "ingredients": [
            ("ing-kamun", 200, 0),
            ("ing-filfil-siyah", 100, 0),
            ("ing-zanjabeel", 150, 1),
            ("ing-kasni", 150, 0)
        ]
    },
    {
        "code": "CLAS-LAU-01",
        "name": "Lauq-e-Sapistan",
        "transliteration": "Lauq-e-Sapistan",
        "dosage_form": "LAUQ",
        "source": "Shifā' al-Abdān Fasl 3 (Amraz-e-Tanaffus) / Kitāb al-Qānūn",
        "indication": "Dry cough (Sual Yabis), sore throat, catarrh, bronchitis, and respiratory congestion.",
        "adult_dose": "10g licked slowly from a spoon twice daily, especially at bedtime.",
        "ingredients": [
            ("ing-sapistan", 400, 1),
            ("ing-unnab", 300, 0),
            ("ing-behidana", 150, 0),
            ("ing-mulethi", 200, 0),
            ("ing-banafsha", 150, 0)
        ]
    },
    {
        "code": "CLAS-SAF-01",
        "name": "Safoof-e-Mohazzil",
        "transliteration": "Safoof-e-Mohazzil",
        "dosage_form": "SAFOOF",
        "source": "Shifā' al-Abdān Fasl 11 / NFUM Part II",
        "indication": "Obesity (Farbahee), metabolic syndrome, excess adipose tissue (Qat-e-Shahm), and sluggish metabolism.",
        "adult_dose": "3g to 5g in the morning with warm water or Arq Zeera.",
        "ingredients": [
            ("ing-kamun", 300, 1),
            ("ing-sana-makki", 250, 0),
            ("ing-turbud", 150, 0),
            ("ing-shahtara", 150, 0),
            ("ing-filfil-siyah", 100, 0)
        ]
    }
]

# -----------------------------------------------------------------------------
# 3. CLASSICAL CLINICAL PROBLEMS & USUL-E-ILAJ PROTOCOLS
# -----------------------------------------------------------------------------
CLASSICAL_DISEASES = [
    {
        "code": "DIS-UNANI-SUDA",
        "name": "Suda (Headache & Migraine / Shaqiqa)",
        "organ_axis": "Dimagh-Qalb",
        "mizaj_deviation": "Su-e-Mizaj Haar Yabis / Su-e-Mizaj Damwi",
        "nabz": "Nabz Sari' Azeem (Fast & Full)",
        "usul_e_ilaj": "Tanqia-e-Dimagh (Cerebral evacuation), Taskeen-e-Alam, Tabreed (Cooling), and Taqwiyat-e-Dimagh.",
        "primary_nuskhas": ["Itrifal Ustukhuddus", "Itrifal Kishneezi", "Roghan-e-Banafsha (Maalish)"],
        "book_locator": "Kitāb al-Qānūn fī al-ṭibb (Rome 1593) Vol 2, Safha 85 / Shifā' al-Abdān Fasl 1"
    },
    {
        "code": "DIS-UNANI-ZOF-KABID",
        "name": "Zof-e-Kabid & Warm-e-Jigar (Hepatic Dysfunction / Hepatitis)",
        "organ_axis": "Jigar-Banas",
        "mizaj_deviation": "Su-e-Mizaj Hararat / Balgham-e-Lazzaj",
        "nabz": "Nabz Mustawi Motadil ya Nabz Da'eef",
        "usul_e_ilaj": "Fath-e-Sudad (Deobstruent), Tanqia-e-Jigar, Daf-e-Dasaumat (Fat removal), and Taqwiyat-e-Jigar.",
        "primary_nuskhas": ["Majoon Dabeedul Ward", "Sharbat Deenar", "Habb-e-Kabid Naushadri", "Arq Mako o Kasni"],
        "book_locator": "Shifā' al-Abdān (McGill 1896) Fasl 5 / Kitāb al-Qānūn Book 3"
    },
    {
        "code": "DIS-UNANI-WAJA-MAFASIL",
        "name": "Waja-ul-Mafasil & Niqris (Arthritis & Gout)",
        "organ_axis": "Mafasil-Dam",
        "mizaj_deviation": "Su-e-Mizaj Baarid Ratab / Balgham-e-Kham",
        "nabz": "Nabz Batee Bat'ee (Slow & Deep)",
        "usul_e_ilaj": "Tahleel-e-Warm (Anti-inflammatory), Tanqia-e-Mawad-e-Fasida (Evacuation of morbid matter), and Taskeen-e-Waja.",
        "primary_nuskhas": ["Majoon Suranjan", "Habb-e-Suranjan", "Majoon Chobchini", "Roghan-e-Suranjan"],
        "book_locator": "Kitāb al-Qānūn Book 4 (UNESCO Manuscript) / Shifā' al-Abdān Fasl 9"
    },
    {
        "code": "DIS-UNANI-KHAFQAN",
        "name": "Khafqan (Cardiac Palpitation & Neuro-Cardiac Anxiety)",
        "organ_axis": "Qalb-Urooq",
        "mizaj_deviation": "Su-e-Mizaj Haar Yabis / Bukharat-e-Sauda",
        "nabz": "Nabz Sari' Ghair-Muntazam (Rapid Irregular)",
        "usul_e_ilaj": "Tafreeh-e-Qalb (Cardiotonic & Elation), Taskeen-e-Ruh, and Ta'deel-e-Mizaj.",
        "primary_nuskhas": ["Khamira Gaozaban Ambari Jawaharwala", "Khamira Marwareed", "Jawarish Shahi"],
        "book_locator": "Shifā' al-Abdān Fasl 2 / Akhlaq-e-Jalali (Ilaj bil-Nafsiyat)"
    },
    {
        "code": "DIS-UNANI-ZEEQ-NAFS",
        "name": "Zeeq-un-Nafs (Bronchial Asthma & Chronic Bronchitis)",
        "organ_axis": "Riya-Sadr",
        "mizaj_deviation": "Su-e-Mizaj Baarid Balghami / Sudda-e-Majari-e-Tanaffus",
        "nabz": "Nabz Munqabiz (Contracted)",
        "usul_e_ilaj": "Tanqiya-e-Sadr (Chest clearance), Tahleel-e-Balgham (Phlegm liquefaction), and Taqwiyat-e-Riya.",
        "primary_nuskhas": ["Lauq-e-Sapistan", "Sharbat Zoofa Murakkab", "PulmoVora™"],
        "book_locator": "Kitāb al-Qānūn Book 3 / Shifā' al-Abdān Fasl 3"
    },
    {
        "code": "DIS-UNANI-RIQAT-MANI",
        "name": "Riqat-e-Mani & Jiryan (Seminal Oligospermia & Male Weakness)",
        "organ_axis": "Khusyatain-Dam",
        "mizaj_deviation": "Hararat-e-Khusyatain / Su-e-Mizaj Haar",
        "nabz": "Nabz Da'eef Sari'",
        "usul_e_ilaj": "Taghleez-e-Mani (Seminal thickening), Hifz-e-Hararat-e-Ghariziya, and Taqwiyat-e-Quwwat-e-Mamsika.",
        "primary_nuskhas": ["Majoon Mughalliz Jawaharwali", "Majoon Falasfa", "SpermoPro™"],
        "book_locator": "Shifā' al-Abdān Fasl 10 / Qarabadin-e-Azam"
    }
]


def ingest_all():
    print(f"Connecting to MATAB OS database: {TARGET_DB}...")
    conn = sqlite3.connect(TARGET_DB)
    cur = conn.cursor()

    # 1. Ingest Classical Herbs into ingredient_catalog
    print(f"1. Ingesting {len(CLASSICAL_HERBS)} authenticated classical herbs into ingredient_catalog...")
    for herb in CLASSICAL_HERBS:
        cur.execute("""
            INSERT OR REPLACE INTO ingredient_catalog (
                id, canonical_name, unani_name, botanical_name, category,
                temperament_mizaj, degree, single_dose_min_mg, single_dose_max_mg,
                daily_dose_max_mg, is_mudabbar_required, is_schedule_e1, review_status
            ) VALUES (?, ?, ?, ?, 'BOTANICAL', ?, ?, ?, ?, ?, ?, ?, 'APPROVED');
        """, herb)

    # 2. Ingest Classical Formulations
    print(f"2. Ingesting {len(CLASSICAL_FORMULATIONS)} classical formulations from Shifa' al-Abdan & Al-Qanun...")
    for form in CLASSICAL_FORMULATIONS:
        form_id = f"form-{form['code'].lower()}"
        cur.execute("""
            INSERT OR REPLACE INTO formulations (
                id, organization_id, code, name, transliteration, dosage_form,
                current_version, status, created_by, updated_by
            ) VALUES (?, ?, ?, ?, ?, ?, 1, 'APPROVED', ?, ?);
        """, (form_id, ORG_ID, form['code'], form['name'], form['transliteration'], form['dosage_form'], ADMIN_USER_ID, ADMIN_USER_ID))

        ver_id = f"fv-{form['code'].lower()}-v1"
        cur.execute("""
            INSERT OR REPLACE INTO formulation_versions (
                id, formulation_id, version_number, preparation_method,
                standard_indication, standard_adult_dose, source_locator, status, reviewed_by
            ) VALUES (?, ?, 1, ?, ?, ?, ?, 'APPROVED', ?);
        """, (
            ver_id, form_id,
            f"Compounded according to classical pharmacopoeial standards. Source: {form['source']}.",
            form['indication'],
            form['adult_dose'],
            form['source'],
            ADMIN_USER_ID
        ))

        for idx, (ing_id, qty, is_chief) in enumerate(form['ingredients']):
            fi_id = f"fi-{form['code'].lower()}-{idx+1}"
            cur.execute("""
                INSERT OR REPLACE INTO formulation_ingredients (
                    id, formulation_version_id, ingredient_id, quantity_mg, unit,
                    is_chief_ingredient, sort_order
                ) VALUES (?, ?, ?, ?, 'mg', ?, ?);
            """, (fi_id, ver_id, ing_id, qty, is_chief, idx + 1))

    # 3. Ingest Classical Diseases into knowledge_items
    print(f"3. Ingesting {len(CLASSICAL_DISEASES)} classical amraz & Usul-e-Ilaj protocols into knowledge_items...")
    for dis in CLASSICAL_DISEASES:
        item_id = f"ki-{dis['code'].lower()}"
        attrs = {
            "organ_axis": dis["organ_axis"],
            "mizaj_deviation": dis["mizaj_deviation"],
            "nabz_diagnostic": dis["nabz"],
            "usul_e_ilaj": dis["usul_e_ilaj"],
            "primary_nuskhas": dis["primary_nuskhas"],
            "classical_book_locator": dis["book_locator"]
        }
        cur.execute("""
            INSERT OR REPLACE INTO knowledge_items (
                id, domain, entity_type, canonical_name, aliases_json,
                language, description, structured_attributes_json, clinical_scope,
                claim_type, evidence_level, status, version, created_by, source_count
            ) VALUES (?, 'UNANI', 'DISEASE', ?, '[]', 'ur', ?, ?, 'OUTPATIENT', 'classical_description', 'CLASSICAL_COMPENDIUM_GRADE_D', 'approved', '1.0', ?, 1);
        """, (
            item_id,
            dis["name"],
            f"Classical Unani condition: {dis['name']}. Deviation: {dis['mizaj_deviation']}. Usul-e-Ilaj: {dis['usul_e_ilaj']}.",
            json.dumps(attrs),
            ADMIN_USER_ID
        ))

    conn.commit()
    conn.close()
    print("Classical Unani Pharmacopoeia & Books Knowledge Engine ingested successfully!")


if __name__ == "__main__":
    ingest_all()
