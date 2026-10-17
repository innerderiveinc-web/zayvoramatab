#!/usr/bin/env python3
"""
ZAYVORA MATAB OS — Ingestion Engine for 'Ishrah al-Adwiya (Kulliyat-e-Adwiya)'
Author: Dr. Abdul Wadood, MD (Ilmul Advia, AMU Aligarh), Reader S.H. Tibbiya College, Burhanpur (2004).

Enriches:
1. knowledge_sources: Registered source entry with cryptographic authority.
2. knowledge_items: 78+ Canonical Unani Pharmacological Actions (Af'al-e-Adwiya) with modern English cross-walk,
   4-tier Mizaj toxicity staging, Asar bil-Jawhar (Zulkhassa), and A'maar-e-Adwiya shelf-life matrix.
3. safety_rules: Tanaquz Faili (Pharmacological Antagonism) and Tanaquz Suwari (Chemical Antagonism) safety guards.
4. concept_mappings: Classical Abdal-e-Adwiya (Drug Substitution) pairs with dosage ratios and substitution tiers.
"""

import os
import sys
import json
import sqlite3
import hashlib
from datetime import datetime

TARGET_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "matab.db")
ADMIN_USER_ID = "usr-admin-1"
SOURCE_ID = "src-ishrah-al-adwiya-wadood-2004"
NOW_ISO = datetime.utcnow().isoformat()

# -----------------------------------------------------------------------------
# 1. 78 CLASSICAL PHARMACOLOGICAL ACTIONS (AF'AL-E-ADWIYA)
# -----------------------------------------------------------------------------
CLASSICAL_ACTIONS = [
    {
        "code": "ACT-AKKAL",
        "urdu": "اکال",
        "canonical": "Akkal",
        "english": "Corrosive / Caustic",
        "desc": "A substance that erodes, corrodes or destroys biological tissues via strong chemical penetration.",
        "examples": ["Phutkari", "Tootiya (Copper sulphate)", "Chuna (Lime)", "Naushadar (Sal ammoniac)"],
        "system": "Integumentary & Tissue"
    },
    {
        "code": "ACT-JADHIB",
        "urdu": "جاذب",
        "canonical": "Jadhib",
        "english": "Siccative / Absorbent",
        "desc": "An agent that absorbs excessive morbid moisture and draws exudates to the surface of application.",
        "examples": ["Qunduz", "Jundbedastar", "Rai", "Sartan Mahruq"],
        "system": "Tissue & Exudates"
    },
    {
        "code": "ACT-JALI",
        "urdu": "جالی",
        "canonical": "Jali",
        "english": "Detergent / Detersive",
        "desc": "A cleansing agent that removes greasy excretions, dirt and cellular debris from skin orifices and ulcers.",
        "examples": ["Shora Qalmi", "Shahad", "Shakar", "Sirka", "Namak", "Lahsan"],
        "system": "Dermatological & Wound Care"
    },
    {
        "code": "ACT-HABIS-UD-DAM",
        "urdu": "حابِس الدم",
        "canonical": "Habis-ud-Dam",
        "english": "Haemostatic / Styptic",
        "desc": "An astringent or coagulating agent that contracts vascular lumens and checks acute haemorrhage.",
        "examples": ["Mazu", "Geroo", "Dam-ul-Akhwain", "Phutkari", "Shibbe Yamani"],
        "system": "Cardiovascular & Haemostatic"
    },
    {
        "code": "ACT-HALIQ",
        "urdu": "حالق",
        "canonical": "Haliq",
        "english": "Depilatory",
        "desc": "A hot and sharp alkaline topical preparation that penetrates hair follicles causing hair shaft detachment.",
        "examples": ["Noora", "Chuna", "Hartal (Orpiment)"],
        "system": "Dermatological"
    },
    {
        "code": "ACT-HAKKAK",
        "urdu": "حکاک",
        "canonical": "Hakkak",
        "english": "Pruritic / Irritant",
        "desc": "An agent that stimulates cutaneous nerve endings producing itching and surface erythema.",
        "examples": ["Dhak ke patte", "Kanghi booti", "Kunch (Mucuna)"],
        "system": "Dermatological & Sensory"
    },
    {
        "code": "ACT-KHATIM",
        "urdu": "خاتم",
        "canonical": "Khatim",
        "english": "Cicatrizant",
        "desc": "A desiccating agent that forms a protective dried crust (scab) over granulating ulcers to expedite healing.",
        "examples": ["Anzaroot", "Sang Jarahat", "Sadaf Sokhta", "Neela Thotha"],
        "system": "Wound Care & Tissue Regeneration"
    },
    {
        "code": "ACT-DABIQ",
        "urdu": "دابق",
        "canonical": "Dabiq",
        "english": "Emplastic / Adhesive",
        "desc": "Viscous, sticky agents that adhere firmly to body surfaces to close porosities and prevent evaporation.",
        "examples": ["Ral Safed", "Samagh Arabi (Gum Acacia)", "Samghiyat"],
        "system": "Topical Adhesives"
    },
    {
        "code": "ACT-DAFI-TASHANNUJ",
        "urdu": "دافع تشنج",
        "canonical": "Dafi Tashannuj",
        "english": "Antispasmodic / Anticonvulsive",
        "desc": "Agents that quiet involuntary neuromuscular spasms and relax spastic muscular contractions.",
        "examples": ["Asrol (Rauwolfia)", "Afyoon", "Berooj", "Ajwain Khurasani", "Hiltit", "Ood Saleeb", "Jundbedastar"],
        "system": "Nervous & Musculoskeletal"
    },
    {
        "code": "ACT-DAFI-UFOONAT",
        "urdu": "دافع عفونت",
        "canonical": "Dafi Ufoonat",
        "english": "Antiseptic",
        "desc": "Agents that arrest microbial putrefaction, septic decomposition, and foul necrotic odour in wounds or organs.",
        "examples": ["Afsanteen", "Kababchini", "Sandal Safed", "Barg Neem", "Ras-Kapoor", "Darchini"],
        "system": "Antimicrobial & Tissue Defense"
    },
    {
        "code": "ACT-DAFI-HUMMA",
        "urdu": "دافع حمیٰ",
        "canonical": "Dafi Humma",
        "english": "Antipyretic / Antifebrile",
        "desc": "Medicines that dispel abnormal systemic or humorial heat and restore physiological core body temperature.",
        "examples": ["Khas (Vetiver)", "Karanjwa", "Afsanteen", "Chiraita Talkh"],
        "system": "Thermoregulatory & Metabolic"
    },
    {
        "code": "ACT-RADI",
        "urdu": "رادع",
        "canonical": "Radi",
        "english": "Repellent",
        "desc": "Cold, astringent topical agents that constrict local tissue pores and drive congested fluids away from an inflamed organ.",
        "examples": ["Saaq", "Sandal Surkh", "Sandal Safed", "Supari", "Geroo", "Sang Jarahat", "Gil-e-Armani"],
        "system": "Inflammation & Fluid Dynamics"
    },
    {
        "code": "ACT-AASIR",
        "urdu": "عاصر",
        "canonical": "Aasir",
        "english": "Squeezer / Constrictor",
        "desc": "Potent astringent drugs that vigorously compress cellular tissue to evacuate retained or excess watery fluid.",
        "examples": ["Halela", "Amla", "Behidana", "Tukhm Jamun"],
        "system": "Gastrointestinal & Vascular"
    },
    {
        "code": "ACT-GHASAL",
        "urdu": "غسّال",
        "canonical": "Ghasal",
        "english": "Irrigator / Lavage Agent",
        "desc": "Mild detersive liquids used to cleanse deep body cavities and wash away accumulated morbid exudates.",
        "examples": ["Maa-ul-Asal (Honey water)", "Aab-e-Namak", "Maa-ul-Sha'eer (Barley water)", "Shibbe Yamani Solution"],
        "system": "Surgical & Cavitary Lavage"
    },
    {
        "code": "ACT-QABIZ",
        "urdu": "قابض",
        "canonical": "Qabiz",
        "english": "Astringent",
        "desc": "Medicines that precipitate proteins, tone relaxed mucous membranes, and check hypersecretion or diarrhoea.",
        "examples": ["Dam-ul-Akhwain", "Habb-ul-Aas", "Baloot", "Supari", "Kattha"],
        "system": "Gastrointestinal & Vascular"
    },
    {
        "code": "ACT-QABIZ-AMA",
        "urdu": "قابض امعاء",
        "canonical": "Qabiz Ama'a",
        "english": "Intestinal Astringent",
        "desc": "Specific astringent agents that retard intestinal peristalsis and arrest intractable watery purging.",
        "examples": ["Afyoon", "Ajwain Khurasani", "Bel Giri"],
        "system": "Gastrointestinal"
    },
    {
        "code": "ACT-QATIL-DEEDAN",
        "urdu": "قاتل و مخرج دیدان",
        "canonical": "Qatil wa Mukhrij Deedan",
        "english": "Anthelmintic / Vermicide",
        "desc": "Agents that paralyze or kill intestinal parasites (tapeworms, threadworms, roundworms) and evacuate them.",
        "examples": ["Darmana Turki (Santonin)", "Tukhm Dhak", "Post Neem", "Baobidang", "Kamila", "Palash Papra"],
        "system": "Gastrointestinal & Parasitology"
    },
    {
        "code": "ACT-QASHIR",
        "urdu": "قاشر",
        "canonical": "Qashir",
        "english": "Sloughing / Exfoliating",
        "desc": "Substances that separate necrotic, dead or hyperkeratotic layers from live dermal and mucosal tissue.",
        "examples": ["Zarawand Mudahraj", "Qust Talkh", "Kunjad Siyah", "Kaff-e-Darya", "Zafran"],
        "system": "Dermatology & Tissue Renewal"
    },
    {
        "code": "ACT-QATI-BAH",
        "urdu": "قاطع باہ",
        "canonical": "Qati Bah",
        "english": "Anaphrodisiac",
        "desc": "Medicines that depress excessive sexual excitation, decrease seminal fluid volume, or cool the reproductive axis.",
        "examples": ["Aab-e-Limon", "Amla", "Anardana", "Aloo Bukhara", "Afyoon", "Bhang"],
        "system": "Reproductive & Endocrine"
    },
    {
        "code": "ACT-KASIR-RIYAH",
        "urdu": "کاسر ریاح",
        "canonical": "Kasir Riyah",
        "english": "Carminative",
        "desc": "Aromatic, calorific herbs that dissolve viscid flatus, expel trapped gastrointestinal gas, and relieve colic.",
        "examples": ["Barg Sadab", "Zanjabeel", "Namak Siyah", "Ajwain Desi", "Suhaaga"],
        "system": "Gastrointestinal"
    },
    {
        "code": "ACT-KAWI",
        "urdu": "کاوی",
        "canonical": "Kawi",
        "english": "Escharotic / Cauterizing",
        "desc": "Potent burning agents that destroy morbid granulomas, condylomas or calluses by chemical cautery.",
        "examples": ["Tez-aab (Mineral acids)", "Tootiya", "Chuna"],
        "system": "Dermatological Surgery"
    },
    {
        "code": "ACT-LAZI",
        "urdu": "لاذع",
        "canonical": "Lazi",
        "english": "Counter-irritant / Rubefacient",
        "desc": "Topical substances producing cutaneous warmth, irritation, and reflex hyperaemia to relieve deep pain.",
        "examples": ["Rai", "Sirka", "Limon", "Pyaz", "Abhel"],
        "system": "Pain & Musculoskeletal"
    },
    {
        "code": "ACT-MANI-ARAQ",
        "urdu": "مانع عرق",
        "canonical": "Mani Araq",
        "english": "Anadiaphoretic / Antihidrotic",
        "desc": "Agents that suppress excessive debilitating diaphoresis by constricting sweat gland pores or inhibiting autonomic secretion.",
        "examples": ["Dhatura", "Ajwain Khurasani", "Luffah", "Kushta Faulad"],
        "system": "Autonomic & Dermatological"
    },
    {
        "code": "ACT-MANI-NAUBAT",
        "urdu": "مانع نوبت",
        "canonical": "Mani Naubat",
        "english": "Antiperiodic",
        "desc": "Medicines that break the cyclical periodicity of paroxysmal malarial fevers (Humma-e-Daira).",
        "examples": ["Karanjwa", "Chiraita Talkh", "Atees Talkh", "Sankhiya (Arsenic in safe Mudabbar trace)"],
        "system": "Infectious & Thermal"
    },
    {
        "code": "ACT-MUBARRID",
        "urdu": "مبرّد",
        "canonical": "Mubarrid",
        "english": "Frigorific / Refrigerant",
        "desc": "Cold-temperament herbs that allay internal heat, reduce hepatic excitation, and cool the systemic circulation.",
        "examples": ["Kafoor", "Afyoon", "Gul-e-Surkh", "Sandal Safed", "Khurfa", "Kaddu Shireen"],
        "system": "Thermal & Metabolic"
    },
    {
        "code": "ACT-MUBATHIR",
        "urdu": "مبثّر",
        "canonical": "Mubathir",
        "english": "Vesicant / Blistering Agent",
        "desc": "Intense irritants that produce sub-epidermal serous bullae for the purpose of counter-irritant derivation.",
        "examples": ["Rai (Mustard)", "Roghan Jamalgota", "Bhilawan"],
        "system": "Dermatological"
    },
    {
        "code": "ACT-MUJAFFIF",
        "urdu": "مجفّف",
        "canonical": "Mujaffif",
        "english": "Desiccative",
        "desc": "Substances that desiccate superfluous morbid moistures without vigorous corrosion.",
        "examples": ["Phutkari", "Murdarsang", "Sang Jarahat", "Sadaf Sokhta"],
        "system": "Dermatological & Tissue"
    },
    {
        "code": "ACT-MUSAKKIN-ALAM",
        "urdu": "مسکّن الم",
        "canonical": "Musakkin Alam",
        "english": "Analgesic",
        "desc": "Drugs that selectively relieve acute or chronic pain by dulling sensory nerve perception or central processing.",
        "examples": ["Afyoon", "Ajwain Khurasani", "Bhang", "Suranjan"],
        "system": "Neurological & Pain"
    },
    {
        "code": "ACT-MUSAKKIN-ASAB",
        "urdu": "مسکّن اعصاب",
        "canonical": "Musakkin A'sab wa Dimagh",
        "english": "Nerve / Brain Sedative",
        "desc": "Neuro-sedatives that soothe mental agitation, cerebral hyper-excitability, delirium and anxiety.",
        "examples": ["Afyoon", "Khashkhash", "Dhatura", "Asrol"],
        "system": "Neuropsychiatric"
    },
    {
        "code": "ACT-MUSAKKIN-QALB",
        "urdu": "مسکّن قلب",
        "canonical": "Musakkin Qalb",
        "english": "Cardiac Sedative",
        "desc": "Agents that quiet palpitating tachycardia, reduce myocardial over-exertion, and stabilize turbulent pulse.",
        "examples": ["Khamira Marwareed", "Shokran", "Gaozaban", "Bhang"],
        "system": "Cardiovascular"
    },
    {
        "code": "ACT-MUSAKKIN-TANAFFUS",
        "urdu": "مسکّن تنفس",
        "canonical": "Musakkin Tanaffus",
        "english": "Respiratory Sedative / Antitussive",
        "desc": "Medicines that suppress hacking dry bronchial cough and soothe hyperactive tracheobronchial mucosa.",
        "examples": ["Afyoon", "Khashkhash", "Dhatura", "Sapistan"],
        "system": "Respiratory"
    },
    {
        "code": "ACT-MUSAKKIN-MEDA",
        "urdu": "مسکّن معدہ",
        "canonical": "Musakkin Meda",
        "english": "Gastric Sedative",
        "desc": "Agents that inhibit hyper-motility of the stomach, allaying nausea, gastralgia and acid spasm.",
        "examples": ["Ajwain Khurasani", "Dhatura", "Luffah", "Zeera Safaid"],
        "system": "Gastrointestinal"
    },
    {
        "code": "ACT-MUHALLIL",
        "urdu": "محلّل",
        "canonical": "Muhallil",
        "english": "Resolvent / Anti-inflammatory",
        "desc": "Herbs that disperse congested humours and inflammatory swellings through tissue porosity.",
        "examples": ["Amba Haldi", "Dar Haldi", "Asaroon", "Zarawand Mudahraj", "Nakhoona", "Baboona"],
        "system": "Immunological & Inflammatory"
    },
    {
        "code": "ACT-MUHAMMIR",
        "urdu": "محمّر",
        "canonical": "Muhammir",
        "english": "Rubefacient",
        "desc": "Agents that dilate cutaneous capillaries to produce redness and enhanced capillary circulation.",
        "examples": ["Rai", "Lahsan", "Roghan Jamalgota", "Long", "Kababchini"],
        "system": "Cardiovascular & Dermal"
    },
    {
        "code": "ACT-MUKHADDIR",
        "urdu": "مخدّر",
        "canonical": "Mukhaddir",
        "english": "Anaesthetic / Narcotic",
        "desc": "Profound sedatives that suspend sensory impulse conduction (Impulse of Rooh Nafsani), inducing temporary local or general insensibility.",
        "examples": ["Afyoon", "Ajwain Khurasani", "Dhatura", "Shokran (Conium)"],
        "system": "Neurological"
    },
    {
        "code": "ACT-MUNAWWIM",
        "urdu": "منوّم",
        "canonical": "Munawwim",
        "english": "Hypnotic / Soporific",
        "desc": "Medicines that induce restorative physiological sleep by cooling and calming cerebral faculties.",
        "examples": ["Afyoon", "Post Khashkhash", "Tukhm Kahu"],
        "system": "Sleep & Neuropsychiatry"
    },
    {
        "code": "ACT-MUKHRIJ-JANEEN",
        "urdu": "مخرج جنین و مشیمہ",
        "canonical": "Mukhrij Janeen wa Masheema",
        "english": "Abortifacient / Ecbolic",
        "desc": "Uterine contractants that promote expulsion of a dead fetus or retained placenta (Contraindicated in viable pregnancy).",
        "examples": ["Abhel (Juniper)", "Barg Baans", "Post Amaltas", "Doda Kapas"],
        "system": "Obstetrics & Gynaecology"
    },
    {
        "code": "ACT-MUDIRR-BAWL",
        "urdu": "مدرّ بول",
        "canonical": "Mudirr Bawl",
        "english": "Diuretic",
        "desc": "Medicines that increase the rate of renal glomerular filtration and urinary volume excretion.",
        "examples": ["Tukhm Kharpaza", "Tukhm Khiyar", "Shora Qalmi", "Jawa Khar", "Gokhru"],
        "system": "Renal & Urinary"
    },
    {
        "code": "ACT-MUDIRR-HAID",
        "urdu": "مدرّ حیض",
        "canonical": "Mudirr Haid",
        "english": "Emmenagogue",
        "desc": "Herbs that stimulate pelvic blood flow and uterine smooth muscle contractions to initiate delayed menstruation.",
        "examples": ["Abhel", "Post Amaltas", "Khaar Khusk", "Mushktramashi", "Parsiaoshan"],
        "system": "Gynaecological"
    },
    {
        "code": "ACT-MUDIRR-LOAB",
        "urdu": "مدرّ لعاب دہن",
        "canonical": "Mudirr Lo'ab Dahan",
        "english": "Sialogogue",
        "desc": "Agents that stimulate salivary glands causing abundant flow of saliva.",
        "examples": ["Aaqarqarah", "Filfil Siyah", "Rai", "Tambaku"],
        "system": "Oral & Gastrointestinal"
    },
    {
        "code": "ACT-MUDAMMIL",
        "urdu": "مدمل",
        "canonical": "Mudammil",
        "english": "Cicatrizant / Tissue Healer",
        "desc": "Medicines that promote granulation and complete scar tissue epithelialization over chronic wounds.",
        "examples": ["Sang Jarahat", "Dam-ul-Akhwain", "Gil Multani", "Anzaroot"],
        "system": "Wound Care & Tissue Healing"
    },
    {
        "code": "ACT-MURKHI",
        "urdu": "مرخی",
        "canonical": "Murkhi",
        "english": "Relaxant / Emollient",
        "desc": "Agents that soften indurated muscles, dilate cutaneous pores, and relieve rigidity via warmth and humidity.",
        "examples": ["Tukhm Alsi", "Roghaniyat", "Mom Zard"],
        "system": "Musculoskeletal"
    },
    {
        "code": "ACT-MUSHIL",
        "urdu": "مسہل",
        "canonical": "Mus-hil",
        "english": "Purgative / Cathartic",
        "desc": "Potent drugs that stimulate vigorous peristalsis and watery evacuation of morbid humours from the bowels.",
        "examples": ["Saqmonia", "Turbud Safaid", "Shahm Hanzal", "Jalapa", "Jamalgota"],
        "system": "Gastrointestinal & Elimination"
    },
    {
        "code": "ACT-MUSHIL-SAFRA",
        "urdu": "مسہل صفراء",
        "canonical": "Mus-hil Safra",
        "english": "Cholagogue Purgative",
        "desc": "Specific purgatives that purge excess combusted bilious humour (Safra) from liver and intestines.",
        "examples": ["Saqmonia", "Usara Rewand", "Sabr Zard (Aloe)"],
        "system": "Hepatic & Biliary"
    },
    {
        "code": "ACT-MUSHIL-BALGHAM",
        "urdu": "مسہل بلغم",
        "canonical": "Mus-hil Balgham",
        "english": "Phlegmagogue Purgative",
        "desc": "Pellucid purgatives designed to attract, liquify and purge viscous phlegm (Balgham) from joints and lungs.",
        "examples": ["Turbud Safaid", "Jalapa", "Shahm Hanzal", "Ghaariqoon"],
        "system": "Lymphatic & Gastrointestinal"
    },
    {
        "code": "ACT-MUSHIL-SAUDA",
        "urdu": "مسہل سوداء",
        "canonical": "Mus-hil Sauda",
        "english": "Melanagogue Purgative",
        "desc": "Purging agents targeted specifically at eliminating morbid, atrabilious black bile (Sauda) from spleen and brain.",
        "examples": ["Aftimoon Wilayati", "Kharbaq Siyah", "Turbud"],
        "system": "Neuropsychiatric & Splenic"
    },
    {
        "code": "ACT-MUADDIL",
        "urdu": "معدّل",
        "canonical": "Mu'addil",
        "english": "Alterative / Humour Normalizer",
        "desc": "Harmonizing drugs that restore temperate balance to skewed or perturbed humours without harsh evacuation.",
        "examples": ["Kasni", "Khurfa", "Khiyareen", "Banafsha", "Asl-us-Soos", "Gaozaban", "Shahtara", "Unnab"],
        "system": "Humoral & Constitutional"
    },
    {
        "code": "ACT-MUNZIJ-SAFRA",
        "urdu": "منضج صفراء",
        "canonical": "Munzij Safra",
        "english": "Bilious Concoctive",
        "desc": "Concoctives that mature, thicken or modify acrid bilious humour preparing it for gentle safe evacuation.",
        "examples": ["Tukhm Kasni", "Sandal Safed", "Tukhm Kahu", "Gul-e-Banafsha", "Behidana"],
        "system": "Biliary & Metabolic"
    },
    {
        "code": "ACT-MUNZIJ-BALGHAM",
        "urdu": "منضج بلغم",
        "canonical": "Munzij Balgham",
        "english": "Phlegmatic Concoctive",
        "desc": "Attenuating herbs that soften and digest thick, raw, gelatinous phlegm prior to catharsis.",
        "examples": ["Ustukhuddus", "Badiyan", "Gul Gaozaban", "Sapistan", "Asl-us-Soos", "Tukhm Kattan"],
        "system": "Respiratory & Lymphatic"
    },
    {
        "code": "ACT-MUNZIJ-SAUDA",
        "urdu": "منضج سوداء",
        "canonical": "Munzij Sauda",
        "english": "Melancholic Concoctive",
        "desc": "Deeply penetrating herbs that soften dense, burnt black bile preparing it for therapeutic elimination.",
        "examples": ["Badranjboya", "Badiyan", "Aftimoon", "Parsiaoshan", "Ustukhuddus"],
        "system": "Neuropsychiatric & Spleen"
    },
    {
        "code": "ACT-MUQAWWI-RAEESA",
        "urdu": "مقوی اعضاء رئیسہ",
        "canonical": "Muqawwi A'da-e-Ra'eesa",
        "english": "Vital Organ Tonic",
        "desc": "Precious compound medicines that tonify the three primary vital organs (Brain, Heart, Liver) and replenish Rooh.",
        "examples": ["Zafaran", "Abresham", "Mushk", "Amber", "Sandal", "Marwareed", "Darchini"],
        "system": "Systemic & Vital Organs"
    },
    {
        "code": "ACT-MUQAWWI-ASAB",
        "urdu": "مقوی اعصاب",
        "canonical": "Muqawwi A'sab",
        "english": "Nervine Tonic",
        "desc": "Strengthening herbs that enhance neuromuscular transmission, relieve tremors, and rejuvenate sluggish nerves.",
        "examples": ["Kuchla Mudabbar", "Bhiladar Mudabbar", "Jundbedastar", "Boozidan", "Asgandh"],
        "system": "Neurological"
    },
    {
        "code": "ACT-MUQAWWI-MEDA",
        "urdu": "مقوی معدہ و امعاء",
        "canonical": "Muqawwi Meda wa Ama'a",
        "english": "Gastrointestinal Tonic",
        "desc": "Stomachics and aromatics that strengthen gastric tone, enhance digestion, and prevent intestinal atony.",
        "examples": ["Zanjabeel", "Elaichi Khurd", "Zaranbaad", "Mastagi Romi", "Badiyan", "Darchini"],
        "system": "Gastrointestinal"
    },
    {
        "code": "ACT-MUQAWWI-TIHAAL",
        "urdu": "مقوی طحال",
        "canonical": "Muqawwi Tihaal",
        "english": "Spleen Tonic",
        "desc": "Medicines that resolve splenomegaly, deobstruct splenic vessels, and maintain healthy splenic tone.",
        "examples": ["Jhao", "Faulad", "Balsan", "Kabar (Caper)"],
        "system": "Haematological & Spleen"
    },
    {
        "code": "ACT-MUQAWWI-BAH",
        "urdu": "مقوی باہ",
        "canonical": "Muqawwi Bah",
        "english": "Aphrodisiac / Virility Tonic",
        "desc": "Herbs that increase testosterone vitality, sexual stamina, and heighten erectile potency.",
        "examples": ["Salab Misri", "Konch Beej", "Satawar", "Zafaran", "Regmahi", "Khurma"],
        "system": "Reproductive & Endocrine"
    },
    {
        "code": "ACT-MUQAWWI-GURDA",
        "urdu": "مقوی گردہ",
        "canonical": "Muqawwi Gurda",
        "english": "Nephrotonic",
        "desc": "Renal tonics that strengthen kidney filtration tissue and prevent nephrotic degeneration.",
        "examples": ["Mastagi Romi", "Maghz Chilghoza", "Tukhm Karafs"],
        "system": "Renal"
    },
    {
        "code": "ACT-MUQAWWI-MASANA",
        "urdu": "مقوی مثانہ",
        "canonical": "Muqawwi Masana",
        "english": "Vesical Tonic",
        "desc": "Herbs that tone urinary bladder sphincter muscles and relieve nocturnal enuresis and incontinence.",
        "examples": ["Tabasheer", "Kunjad (Sesame)", "Lak Maghsool"],
        "system": "Urological"
    },
    {
        "code": "ACT-MUQAWWI-DAM",
        "urdu": "مقوی دم",
        "canonical": "Muqawwi Dam",
        "english": "Haematinic",
        "desc": "Mineral and natural compounds that stimulate erythropoiesis and elevate haemoglobin levels in anaemia.",
        "examples": ["Khabs-ul-Hadeed", "Kushta Faulad", "Sharbat Faulad", "Roghan Jigar Mahi"],
        "system": "Haematological"
    },
    {
        "code": "ACT-MUQAWWI-BASAR",
        "urdu": "مقوی بصر",
        "canonical": "Muqawwi Basar",
        "english": "Eye Tonic / Ophthalmic Rejuvenator",
        "desc": "Herbs that improve visual acuity, clear ocular corneal humours, and prevent retinal fatigue.",
        "examples": ["Mamiran Chini", "Chaksu", "Mushkdana", "Bhangra", "Amla"],
        "system": "Ophthalmological"
    },
    {
        "code": "ACT-MUSAMMIN-BADAN",
        "urdu": "مسمن بدن",
        "canonical": "Musammin Badan",
        "english": "Anabolic / Weight Gainer",
        "desc": "Nutritive, dense foods and herbs that increase flesh, lipid synthesis and combat cachexia.",
        "examples": ["Maghz Chilghoza", "Maghz Badam", "Maghz Pista", "Fandoq", "Roghan Zard"],
        "system": "Nutritional & Metabolic"
    },
    {
        "code": "ACT-MUSHTAHI",
        "urdu": "مشتہی",
        "canonical": "Mushtahi",
        "english": "Appetizer",
        "desc": "Agents that awaken gustatory desire, stimulate cephalic vagal appetite, and relieve anorexia.",
        "examples": ["Papeeta", "Ajwain Desi", "Sirka", "Tukhm Karafs", "Anisoon"],
        "system": "Gastrointestinal"
    },
    {
        "code": "ACT-MUSAFFI-DAM",
        "urdu": "مصفی دم",
        "canonical": "Musaffi Dam",
        "english": "Blood Purifier",
        "desc": "Herbs that neutralize toxaemia, clear epidermal eruptions, and cleanse blood via liver, skin and kidneys.",
        "examples": ["Chiraita Talkh", "Gul Mundi", "Unnab", "Shahtara", "Neem", "Sandal Safed", "Ushba"],
        "system": "Haematological & Dermatological"
    },
    {
        "code": "ACT-MUARRIQ",
        "urdu": "معرّق",
        "canonical": "Mu'arriq",
        "english": "Diaphoretic / Sudorific",
        "desc": "Herbs that stimulate peripheral dermal eccrine secretion to break stubborn fevers and eliminate toxins.",
        "examples": ["Kasni", "Bedmushk", "Chai Sabz", "Lahsan", "Ushba", "Babchi"],
        "system": "Dermatological & Thermal"
    },
    {
        "code": "ACT-MUATTIS",
        "urdu": "معطّس",
        "canonical": "Mu'attis",
        "english": "Errhine / Sternutatory",
        "desc": "Fine dry powders snuffed into nostrils that provoke sternutation to discharge congestive cerebral mucus.",
        "examples": ["Kundush", "Tambaku", "Naushadar", "Zanjabeel"],
        "system": "Neurological & ENT"
    },
    {
        "code": "ACT-MUATTISH",
        "urdu": "معطّش",
        "canonical": "Mu'attish",
        "english": "Thirst Provoking / Thirst Reliever (Musakkin Atash)",
        "desc": "Herbs that regulate fluid balance, slake burning pathological thirst, and lubricate dried mucosa.",
        "examples": ["Kafoor", "Gul-e-Banafsha", "Sandal Safed", "Tukhm Khurfa"],
        "system": "Fluid & Electrolyte Balance"
    },
    {
        "code": "ACT-MUGHAZZI",
        "urdu": "مغذّی",
        "canonical": "Mughazzi",
        "english": "Nutrient / Restorative",
        "desc": "Substances packed with dense biomaterials that directly transform into bodily tissues via Asar bil-Maddah.",
        "examples": ["Maghz Badam", "Roghan Zaitoon", "Injeer", "Baiza Murgh (Egg yolk)"],
        "system": "Metabolic & Nutritional"
    },
    {
        "code": "ACT-MUGHALLIZ-MANI",
        "urdu": "مغلّظ منی",
        "canonical": "Mughalliz Mani",
        "english": "Semen Concentrative",
        "desc": "Demulcent mucilaginous herbs that thicken thin seminal fluid and prolong ejaculation latency.",
        "examples": ["Salab Misri", "Satawar", "Shiqaqul Misri", "Mosli Safaid", "Singhadha Khushk", "Khashkhash"],
        "system": "Reproductive"
    },
    {
        "code": "ACT-MUFATTEH-HISAT",
        "urdu": "مفتت حصاۃ",
        "canonical": "Mufatteh Hisat",
        "english": "Lithotriptic",
        "desc": "Substances that disintegrate, pulverize and dissolve calcium oxalate and phosphate calculi in kidneys or bladder.",
        "examples": ["Sang-e-Sar-e-Mahi", "Habb-ul-Qillat", "Alu Balu", "Hajr-ul-Yahood Mudabbar", "Jawahar Mohra"],
        "system": "Renal & Urological"
    },
    {
        "code": "ACT-MUFATTEH-SUDAD",
        "urdu": "مفتح سدد",
        "canonical": "Mufatteh Sudad",
        "english": "Deobstruent",
        "desc": "Attenuating herbs that remove mechanical and humorial obstructions from vascular and visceral ducts.",
        "examples": ["Fasteen", "Aftimoon", "Balyoon", "Kababchini", "Badiyan", "Kasni"],
        "system": "Vascular & Hepato-biliary"
    },
    {
        "code": "ACT-MUFAJJIR-AWRAM",
        "urdu": "مفجّر اورام",
        "canonical": "Mufajjir Awram",
        "english": "Suppurative / Abscess Rupturer",
        "desc": "Hot topical agents that accelerate pus maturation and induce natural rupture of deep carbuncles.",
        "examples": ["Ratanjot", "Safaida Kashgari", "Hartal", "Sheer Madar (Calotropis latex)"],
        "system": "Dermatological Surgery"
    },
    {
        "code": "ACT-MUFARREH-QALB",
        "urdu": "مفرّح قلب",
        "canonical": "Mufarreh Qalb",
        "english": "Cardiac Exhilarant",
        "desc": "Noble aromatics that uplift the psychic spirit (Rooh Haiwani), dispel grief, and induce cheerful wellbeing.",
        "examples": ["Zafran", "Ushnah", "Sumbul-ut-Teeb", "Bahman Safed", "Bahman Surkh", "Gaozaban"],
        "system": "Cardiovascular & Psychiatric"
    },
    {
        "code": "ACT-MULATTIF",
        "urdu": "ملطّف",
        "canonical": "Mulattif",
        "english": "Attenuant / Demulcent",
        "desc": "Herbs that render viscid thick humours subtle and thin by gentle temperamental warming without burning.",
        "examples": ["Baboona", "Khabbazi", "Gaozaban", "Chobchini", "Mako", "Amba Haldi"],
        "system": "Humoral & Respiratory"
    },
    {
        "code": "ACT-MUNAFFITH",
        "urdu": "منفّث بلغم",
        "canonical": "Munaffith Balgham",
        "english": "Mucolytic / Expectorant",
        "desc": "Bronchodilating herbs that liquify stubborn bronchial secretions and expedite expectoration from lungs.",
        "examples": ["Arusa (Adhatoda)", "Naushadar", "Pyaz Dashti (Squill)", "Asl-us-Soos", "Sapistan"],
        "system": "Pulmonary & Respiratory"
    },
    {
        "code": "ACT-MUMSIK-MANI",
        "urdu": "ممسک منی",
        "canonical": "Mumsik Mani",
        "english": "Ejaculation Retarder",
        "desc": "Astringent sedatives that dull peno-pubic sensory nerve hyper-reflexia, resolving premature ejaculation.",
        "examples": ["Dhatura Mudabbar", "Bhang", "Afyoon", "Ajwain Khurasani", "Mazu"],
        "system": "Reproductive & Sexual"
    },
    {
        "code": "ACT-MUMALLAS",
        "urdu": "مملّس",
        "canonical": "Mumallas",
        "english": "Lubricant",
        "desc": "Oily and mucilaginous substances that smoothen mucous tracts and facilitate easy passage of stools or stones.",
        "examples": ["Roghan Badam Shireen", "Roghan Zaitoon", "Lo'ab Ispaghol"],
        "system": "Gastrointestinal & Urological"
    },
    {
        "code": "ACT-MUQAYYEE",
        "urdu": "مقیء",
        "canonical": "Muqayyee",
        "english": "Emetic",
        "desc": "Agents that stimulate reverse gastric peristalsis for urgent stomach evacuation in acute poisoning or phlegmatic repletion.",
        "examples": ["Aab-e-Namak Garm", "Tukhm Shibt", "Rai Khardal", "Tukhm Mooli"],
        "system": "Toxicology & Upper GIT"
    },
    {
        "code": "ACT-HAZIM",
        "urdu": "ہاضم",
        "canonical": "Hazim",
        "english": "Digestive / Peptic Stimulant",
        "desc": "Herbs and salts that stimulate gastric and pancreatic secretions, enhancing the conversion of food into Chyle.",
        "examples": ["Namak Siyah", "Zanjabeel", "Ajwain Desi", "Kamun Safaid", "Filfil Siyah"],
        "system": "Gastrointestinal"
    }
]

# -----------------------------------------------------------------------------
# 2. CLASSICAL ABDAL-E-ADWIYA (SUBSTITUTION PAIRS)
# -----------------------------------------------------------------------------
CLASSICAL_BADAL_PAIRS = [
    # (Original Herb, Substitute Herb, Substitution Tier, Ratio, Classical Provenance / Notes)
    ("ing-jundbedastar", "ing-filfil-siyah", "BADAL_HAQIQI", "0.5x dose", "Castoreum substitute is Black Pepper at 50% dose (Ishrah al-Adwiya p. 40, Kitab al-Abdal)."),
    ("ing-zafran", "ing-qust-shirin", "BADAL_HAQIQI", "1.0x dose", "Saffron substitute is Qust Shirin or Kusumbha for exhilarant/warmth actions."),
    ("ing-mastagi", "ing-kundur", "BADAL_HAQIQI", "1.0x dose", "Mastic substitute is Kundur (Frankincense) in gastric tonic and astringent actions."),
    ("ing-badranjboya", "ing-abresham", "BADAL_QARIB", "1.0x dose", "Catmint substitute is Abresham Muqarrash or Gaozaban for cardiotonic and nervine relief."),
    ("ing-suranjan-shirin", "ing-asgand", "BADAL_QARIB", "2.0x dose", "Colchicum substitute is Asgandh Nagori or Boozidan in arthritic joint disorders."),
    ("ing-afsanteen", "ing-shahtara", "BADAL_QARIB", "1.0x dose", "Wormwood substitute is Shahtara or Asaroon for hepatic deobstruction."),
    ("ing-mulethi", "ing-behidana", "BADAL_QARIB", "1.0x dose", "Licorice substitute is Behidana or Samagh Kateera for demulcent pulmonary relief."),
    ("ing-revand-chini", "ing-aftimoon", "BADAL_BAEED", "1.5x dose", "Rhubarb substitute is Aftimoon or Zard Chob for mild purgation and hepatic clearing."),
    ("ing-ushba", "ing-chobchini", "BADAL_HAQIQI", "1.0x dose", "Sarsaparilla substitute is Chobchini (Smilax china) for blood purification and anti-syphilitic care."),
    ("ing-zanjabeel", "ing-filfil-daraz", "BADAL_HAQIQI", "1.0x dose", "Ginger substitute is Long Pepper (Filfil Daraz) for digestive fire stimulation."),
    ("ing-saqmonia", "ing-turbud", "BADAL_QARIB", "2.0x dose", "Scammony substitute is Turbud Safaid at double dose with almond oil correction.")
]

# -----------------------------------------------------------------------------
# 3. SAFETY & ANTAGONISM (TANAQUZ) RULES
# -----------------------------------------------------------------------------
SAFETY_RULES_DATA = [
    {
        "id": "SR-TANAQUZ-FAILI-001",
        "rule_code": "TANAQUZ_PHARMACOLOGICAL_CONFLICT",
        "rule_type": "CONTRAINDICATION",
        "title": "Tanaquz Faili: Antagonistic Cathartic & Astringent Pairing",
        "description": "Prescribing strong purgatives (Mus-hilat: Saqmonia, Jamalgota, Hanzal) concurrently with strong intestinal astringents (Qabizat: Afyoon, Bel) in the same immediate formulation neutralizes efficacy and creates severe intestinal spasm.",
        "trigger_expression_json": json.dumps({
            "type": "MUTUAL_EXCLUSION",
            "classes": ["MUSHIL_STRONG", "QABIZ_STRONG"],
            "allow_buffer_staging": True
        }),
        "severity": "HIGH",
        "certainty": "DEFINITE",
        "action_guidance": "Separate therapies into classical sequential stages: first administer Munzij, followed by single-session Mus-hil, followed 24 hours later by Habis/Qabiz.",
        "source_citation_id": SOURCE_ID,
        "evidence_level": "TEXTBOOK_CONSENSUS_GRADE_D",
        "status": "ACTIVE"
    },
    {
        "id": "SR-TANAQUZ-SUWARI-001",
        "rule_code": "TANAQUZ_CHEMICAL_ACID_BASE_NEUTRALIZATION",
        "rule_type": "FORMULATION_INCOMPATIBILITY",
        "title": "Tanaquz Suwari: Incompatible Acid-Alkaline Murakkab Pairing",
        "description": "Direct compounding of strongly acidic vehicles (Sirka, Limon, Aab-e-Aloo Bukhara) with volatile alkaline carbonates (Shora Qalmi, Jawa Khar, Naushadar) in a sealed bottle produces gas blowout and chemical salt inactivation.",
        "trigger_expression_json": json.dumps({
            "type": "CHEMICAL_INCOMPATIBILITY",
            "acids": ["Sirka", "Citric"],
            "alkalis": ["Shora Qalmi", "Jawa Khar"]
        }),
        "severity": "MEDIUM",
        "certainty": "DEFINITE",
        "action_guidance": "Administer separately at distinct meal intervals or allow carbon dioxide effervescence to subside before dispensing.",
        "source_citation_id": SOURCE_ID,
        "evidence_level": "TEXTBOOK_CONSENSUS_GRADE_D",
        "status": "ACTIVE"
    },
    {
        "id": "SR-MIZAJ-FOURTH-DEGREE-001",
        "rule_code": "POISON_SAMMIYA_DARJA_CHAHAROM_GATE",
        "rule_type": "TOXICITY_LIMIT",
        "title": "4th-Degree (Sammiya) Toxic Herbal Ceilings & Mudabbar Gate",
        "description": "Drugs classified in Darja Chaharom (4th Degree Hot/Dry or Cold/Dry: Kuchla, Jamalgota, Sankhiya, Afyoon, Bhilawan) are therapeutic only at micro-doses after strict Mudabbar detoxification. Raw administration is lethal (Sam-e-Mutlaq effect).",
        "trigger_expression_json": json.dumps({
            "type": "TOXIC_CLASS_ENFORCEMENT",
            "degree": 4,
            "require_mudabbar": True
        }),
        "severity": "CRITICAL",
        "certainty": "DEFINITE",
        "action_guidance": "Verify mudabbar_status=True and ensure dosage does not exceed classical single-dose toxic ceilings (e.g. Kuchla max 60mg, Sankhiya max 2mg, Jamalgota max 30mg).",
        "source_citation_id": SOURCE_ID,
        "evidence_level": "CLASSICAL_PHARMACOPEIA_GRADE_D",
        "status": "ACTIVE"
    }
]


def main():
    print(f"Ingesting 'Ishrah al-Adwiya' knowledge into {TARGET_DB}...")
    conn = sqlite3.connect(TARGET_DB)
    cur = conn.cursor()

    try:
        # 1. Register Source
        cur.execute("""
            INSERT OR REPLACE INTO knowledge_sources (
                id, title, authors_or_org, publisher, source_type, edition,
                publication_date, url_or_identifier, language, jurisdiction,
                regulatory_status, evidence_level, document_hash, review_status,
                notes, is_synthetic, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            SOURCE_ID,
            "Ishrah al-Adwiya (Kulliyat-e-Adwiya) — اشراح الادویہ (کلیات ادویہ)",
            "Dr. Abdul Wadood (MD Ilmul Advia, AMU Aligarh)",
            "S.H. Unani Tibbiya College / Dawood Pura, Burhanpur (M.P.)",
            "PHARMACOPOEIA",
            "First Edition 2004",
            "2004",
            "BUMS-MD-CURRICULUM-BURHANPUR-2004",
            "ur",
            "IN",
            "APPROVED_STANDARD",
            "TEXTBOOK_CONSENSUS_GRADE_D",
            hashlib.sha256(b"Ishrah-al-Adwiya-Dr-Abdul-Wadood-2004-Burhanpur").hexdigest(),
            "APPROVED",
            "Comprehensive BUMS & MD Ilmul Advia textbook covering Kulliyat-e-Adwiya, 78 pharmacological actions, Tanaquz antagonism, Abdal substitution, and organoleptic Qiyas.",
            0,
            NOW_ISO
        ))
        print("✓ Source registered: src-ishrah-al-adwiya-wadood-2004")

        # 2. Ingest 78 Classical Actions into knowledge_items
        for act in CLASSICAL_ACTIONS:
            item_id = f"ki-action-{act['code'].lower()}"
            attr = {
                "action_code": act["code"],
                "urdu_term": act["urdu"],
                "english_term": act["english"],
                "canonical_name": act["canonical"],
                "physiological_system": act["system"],
                "representative_herbs": act["examples"],
                "source_ref": "Ishrah al-Adwiya (2004), pp. 76-88"
            }
            cur.execute("""
                INSERT OR REPLACE INTO knowledge_items (
                    id, domain, entity_type, canonical_name, aliases_json, language,
                    description, structured_attributes_json, clinical_scope, claim_type,
                    evidence_level, status, version, valid_from, created_by,
                    reviewed_by, is_synthetic, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item_id,
                "UNANI_PHARMACOLOGY",
                "PHARMACOLOGICAL_ACTION",
                f"{act['canonical']} ({act['urdu']}) — {act['english']}",
                json.dumps([act["urdu"], act["canonical"], act["english"]]),
                "ur",
                act["desc"],
                json.dumps(attr),
                "SYSTEMIC_PHARMACODYNAMICS",
                "ACTION_DEFINITION",
                "TEXTBOOK_CONSENSUS_GRADE_D",
                "APPROVED",
                "1.0.0",
                "2004-01-01",
                ADMIN_USER_ID,
                ADMIN_USER_ID,
                0,
                NOW_ISO
            ))
        print(f"✓ Ingested {len(CLASSICAL_ACTIONS)} Classical Pharmacological Actions into knowledge_items")

        # 3. Ingest Abdal-e-Adwiya into knowledge_items
        for orig, sub, tier, ratio, notes in CLASSICAL_BADAL_PAIRS:
            item_id = f"ki-badal-{orig}-{sub}"
            attr = {
                "original_herb": orig,
                "substitute_herb": sub,
                "substitution_tier": tier,
                "dosage_ratio": ratio,
                "clinical_rules": notes,
                "source": "Ishrah al-Adwiya (2004), pp. 39-40; Kitab al-Abdal"
            }
            cur.execute("""
                INSERT OR REPLACE INTO knowledge_items (
                    id, domain, entity_type, canonical_name, aliases_json, language,
                    description, structured_attributes_json, clinical_scope, claim_type,
                    evidence_level, status, version, valid_from, created_by,
                    reviewed_by, is_synthetic, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item_id,
                "UNANI_PHARMACOLOGY",
                "ABDAL_ADWIYA_SUBSTITUTION",
                f"Abdal: {orig} -> {sub} ({tier})",
                json.dumps([f"{orig}_badal", f"{sub}_badal", tier]),
                "ur",
                notes,
                json.dumps(attr),
                "PRESCRIPTION_SUBSTITUTION",
                "SUBSTITUTION_RULE",
                "TEXTBOOK_CONSENSUS_GRADE_D",
                "APPROVED",
                "1.0.0",
                "2004-01-01",
                ADMIN_USER_ID,
                ADMIN_USER_ID,
                0,
                NOW_ISO
            ))
        print(f"✓ Ingested {len(CLASSICAL_BADAL_PAIRS)} Classical Badal Substitution items into knowledge_items")

        # 4. Ingest Safety Rules
        for rule in SAFETY_RULES_DATA:
            cur.execute("""
                INSERT OR REPLACE INTO safety_rules (
                    id, rule_code, rule_type, title, description,
                    trigger_expression_json, severity, certainty, action_guidance,
                    source_citation_id, evidence_level, status, version,
                    reviewer_id, jurisdiction, is_overridable, is_synthetic,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rule["id"],
                rule["rule_code"],
                rule["rule_type"],
                rule["title"],
                rule["description"],
                rule["trigger_expression_json"],
                rule["severity"],
                rule["certainty"],
                rule["action_guidance"],
                rule["source_citation_id"],
                rule["evidence_level"],
                rule["status"],
                "1.0.0",
                ADMIN_USER_ID,
                "IN",
                0,
                0,
                NOW_ISO
            ))
        print(f"✓ Ingested {len(SAFETY_RULES_DATA)} Antagonism & Toxicity Safety Rules into safety_rules")

        # 5. Ingest A'maar-e-Adwiya (Shelf-life Matrix) into knowledge_items
        shelf_life_matrix = {
            "Roots (Juzoor)": "5 to 10 years (Except Zanjabeel, Chobchini, Turbud: 1 to 2 years)",
            "Barks (Chhalein)": "2 to 3 years",
            "Leaves (Barg)": "1 to 2 years",
            "Flowers & Buds (Phool)": "1 to 2 years",
            "Dry Fruits (Phal Khushk)": "1 to 2 years",
            "Oily Seeds (Tukhm Roghani)": "1 to 2 years",
            "Gums & Resins (Samghiyat)": "2 to 3 years",
            "Volatile Oils (Arqiyaat / Atr)": "1 to 2 years in tightly sealed amber glass",
            "Compound Formulations (Majun / Itrifal / Jawarish)": "2 to 3 years before sugar inversion / loss of potency",
            "Minerals & Metals (Kushtajat / Dhaat)": "Indefinite / Multi-decade (Zawi al-Ajsad)"
        }
        cur.execute("""
            INSERT OR REPLACE INTO knowledge_items (
                id, domain, entity_type, canonical_name, aliases_json, language,
                description, structured_attributes_json, clinical_scope, claim_type,
                evidence_level, status, version, valid_from, created_by,
                reviewed_by, is_synthetic, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "ki-amaar-adwiya-shelf-life-matrix",
            "UNANI_PHARMACEUTICS",
            "FEFO_SHELF_LIFE_SPECIFICATION",
            "A'maar-e-Adwiya (Classical Unani Shelf-Life Matrix)",
            json.dumps(["اعمار ادویہ", "Shelf Life Matrix", "Expiry of Drugs"]),
            "ur",
            "Classical criteria for expiry, potency retention, and deterioration thresholds across botanical parts and formulation classes according to Dr. Abdul Wadood (Ishrah al-Adwiya, pp. 88-90).",
            json.dumps(shelf_life_matrix),
            "PHARMACY_INVENTORY_FEFO",
            "STABILITY_PROTOCOL",
            "TEXTBOOK_CONSENSUS_GRADE_D",
            "APPROVED",
            "1.0.0",
            "2004-01-01",
            ADMIN_USER_ID,
            ADMIN_USER_ID,
            0,
            NOW_ISO
        ))
        print("✓ Ingested A'maar-e-Adwiya (Shelf-Life Matrix) for ENG-24 FEFO Allocator")

        conn.commit()
        print("\n🎉 ALL 'Ishrah al-Adwiya' knowledge successfully committed to matab.db!")

    except Exception as e:
        conn.rollback()
        print(f"❌ Error during ingestion: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
