"""Medical Library & Classical Compendia Domain Engine.
ZAYVORA MATAB OS - Governed Healthcare Platform.

Indexes, catalogs, and searches classical Unani compendia, statutory AYUSH formularies,
and modern biomedical reference texts. Bridges directly into KAVS (Knowledge Authenticity
and Verification System) and the Clinical Decision Support (CDS) engine.
"""

import os
import re
import json
import uuid
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from apps.api.database.connection import DatabaseConnection
from apps.api.core.errors import NotFoundError, ValidationError


CATEGORIES = {
    "CLASSICAL_CANON": "Classical Canons & Ancient Compendia (Ibn Sina, Al-Razi, Azam Khan)",
    "PHARMACOPOEIA_FORMULARY": "Official Formularies & Qarabadeen (NFUM, Hamdard, Majidi, Haziq)",
    "MATERIA_MEDICA": "Materia Medica & Single Herbs / Mufradat (Makhzan al-Mufradat, Azizi)",
    "DIAGNOSTICS_SURGERY": "Diagnostics & Surgical Treatises (Nabz, Baul, Zahrawi, Ibn al-Quff)",
    "MODERN_INTERNAL_MEDICINE": "Modern Internal Medicine & Pathology (Harrison, Davidson, Hutchison, Robbins)",
    "PRINCIPLES_PHYSIOLOGY": "Principles of Tibb & Physiology (Umoor Tabiya, Nafisi, Asbab Sitta)",
    "REGIMENTAL_THERAPY": "Regimental Therapies / Ilaj bil Tadbeer (Hijama, Fasd, Dalk, Hammam)",
    "TERMINOLOGY_GOVERNANCE": "Standard Terminologies & Dictionaries (WHO, CCRUM Standard Unani Terminology)"
}


class MedicalLibraryService:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def _get_connection(self):
        return DatabaseConnection(self.db_path).get_connection()

    def _fingerprint_file(self, filepath: str) -> str:
        """Compute fast deterministic SHA-256 fingerprint for medical book files."""
        h = hashlib.sha256()
        sz = os.path.getsize(filepath)
        with open(filepath, "rb") as f:
            # Read first 2MB
            h.update(f.read(2 * 1024 * 1024))
            if sz > 4 * 1024 * 1024:
                # Seek to last 2MB for large PDFs
                f.seek(-2 * 1024 * 1024, os.SEEK_END)
                h.update(f.read())
        return h.hexdigest()

    def _derive_book_metadata(self, filename: str, filepath: str) -> Dict[str, Any]:
        """Classify book and derive rich clinical metadata from filename and context."""
        fl = filename.lower()
        sz_bytes = os.path.getsize(filepath)
        ext = os.path.splitext(filename)[1].replace(".", "").upper() or "PDF"

        # Defaults
        title = os.path.splitext(filename)[0].replace("_", " ").replace("-", " ")
        title_orig = None
        author = "Clinical Editorial Board"
        category = "CLASSICAL_CANON"
        language = "URDU"
        era = "Classical Historical Benchmark"
        significance = "Standard authoritative reference in medical curriculum and practice."
        topics = ["Unani Medicine", "Clinical Therapeutics"]

        # 1. Al-Qanun fi al-Tibb (Canon of Medicine)
        if "qanoon" in fl or "qanun" in fl or "canon" in fl or "قانون" in filename:
            author = "Ibn Sina (Avicenna, 980-1037 CE)"
            category = "CLASSICAL_CANON"
            era = "Islamic Golden Age (1025 CE)"
            significance = "The supreme canonical authority of classical Unani medicine; synthesized Hippocratic-Galenic principles with rigorous clinical taxonomy."
            topics = ["Kulliyat", "Mizaj", "Mufradat", "Amraz-e-Khasa", "Amraz-e-Aama"]
            if "1593" in fl or "yale" in fl:
                title = "Kitab al-Qanun fi al-Tibb (Medici 1593 Rome Edition, Yale Facsimile)"
                title_orig = "كتاب القانون في الطب"
                language = "ARABIC"
            elif "tarjuma" in fl or "shaikh" in fl:
                title = "Tarjuma Al-Qanun fi al-Tibb (Urdu Translation)"
                title_orig = "ترجمہ القانون فی الطب شیخ بو علی سینا"
                language = "URDU"
            elif "mojzal" in fl:
                title = "Mojaz al-Qanun (Ibn al-Nafis Synopsis)"
                title_orig = "موجز القانون"
                language = "URDU"
            elif "vol. 1" in fl:
                title = "The Canon of Medicine - Volume 1 (General Principles & Anatomy)"
                language = "ENGLISH"
            elif "vol. 2" in fl:
                title = "The Canon of Medicine - Volume 2 (Natural Materia Medica)"
                language = "ENGLISH"
            elif "مکمل" in filename:
                title = "Al-Qanun fi al-Tibb (Mukammal Complete Text)"
                title_orig = "القانون فی الطب مکمل"
                language = "ARABIC"
            else:
                title = "Al-Qanun fi al-Tibb (The Canon of Medicine)"
                title_orig = "القانون فی الطب"
                language = "MULTILINGUAL"

        # 2. Kitab al-Hawi (Rhazes / Al-Razi)
        elif "hawi" in fl or "حاوی" in filename:
            author = "Abu Bakr Mohammad ibn Zakariya al-Razi (Rhazes, 865-925 CE)"
            category = "CLASSICAL_CANON"
            era = "Classical Golden Age (9th-10th Century CE)"
            significance = "Rhazes' monumental 23-volume bedside casebook; the world's first comprehensive empirical clinical case archive."
            topics = ["Differential Diagnosis", "Clinical Case Logs", "Experimental Pharmacology"]
            if "اعصاب" in filename or "aasab" in fl:
                title = "Kitab al-Hawi fi al-Tibb - Jild 1 (Amraz-e-Aasab / Neurology)"
                title_orig = "کتاب الحاوی جلد اول - امراض اعصاب"
                language = "URDU"
            elif "چشم" in filename or "chashm" in fl:
                title = "Kitab al-Hawi fi al-Tibb - Jild 2 (Amraz-e-Chashm / Ophthalmology)"
                title_orig = "کتاب الحاوی جلد دوم - امراض چشم"
                language = "URDU"
            elif "۱۱" in filename or "11" in fl:
                title = "Kitab al-Hawi fi al-Tibb - Jild 11"
                title_orig = "کتاب الحاوی جلد ۱۱"
                language = "ARABIC"
            elif "۲۱" in filename or "21" in fl:
                title = "Kitab al-Hawi fi al-Tibb - Jild 21 (Pharmacology & Materia Medica)"
                title_orig = "کتاب الحاوی جلد ۲۱ حصہ ۱"
                language = "ARABIC"
            elif "hayderabad" in fl:
                title = "Kitab al-Hawi fi al-Tibb (Dairatul Ma'arif Hyderabad Critical Edition)"
                title_orig = "الحاوي في الطب - طبعة حيدر آباد"
                language = "ARABIC"
            else:
                title = "Kitab al-Hawi fi al-Tibb (Comprehensive Medical Encyclopedia)"
                title_orig = "کتاب الحاوی فی الطب"
                language = "URDU"

        # 3. Iksir-e-Azam (Hakim Mohammad Azam Khan)
        elif "iksir" in fl or "اکسیر" in filename:
            title = "Iksir-e-Azam (Complete 4-Volume Clinical Compendium)"
            title_orig = "اکسیر اعظم (کتب خانہ طبیب)"
            author = "Hakim Mohammad Azam Khan (1813-1902 CE)"
            category = "CLASSICAL_CANON"
            language = "URDU"
            era = "19th Century CE"
            significance = "Most comprehensive Unani clinical practice compendium detailing diseases a capite ad calcem (head to toe) with exact compound prescriptions."
            topics = ["Clinical Medicine", "Compound Formulations", "Differential Symptomatology"]

        # 4. Firdaus al-Hikmat (Tabari)
        elif "firdaus" in fl or "فردوس" in filename:
            title = "Firdaus al-Hikmat fi al-Tibb (Paradise of Wisdom)"
            title_orig = "فردوس الحکمت کامل فی الطب"
            author = "Ali ibn Sahl Rabban al-Tabari (838-870 CE)"
            category = "CLASSICAL_CANON"
            language = "URDU"
            era = "850 CE (Abbasid Era)"
            significance = "First comprehensive Greco-Arab medical encyclopedia encompassing pediatrics, psychology, toxicology, and Indian medicine."
            topics = ["General Medicine", "Pediatrics", "Psychiatry", "Toxicology"]

        # 5. Al-Mu'alajat al-Buqratiya
        elif "buqrat" in fl or "بقراط" in filename:
            title = "Al-Mu'alajat al-Buqratiya (Hippocratic Clinical Therapeutics)"
            title_orig = "المعالجات البقراطیہ"
            author = "Abu al-Hasan Ahmad ibn Muhammad al-Tabari (10th Century CE)"
            category = "CLASSICAL_CANON"
            language = "URDU"
            era = "10th Century CE"
            significance = "Bedside Hippocratic treatment protocols and clinical regimens for chronic complex disorders."
            topics = ["Hippocratic Medicine", "Clinical Regimens", "Materia Medica"]

        # 6. Al-Zahrawi (Surgery)
        elif "zahrawi" in fl or "زھراوی" in filename:
            title = "Jarahiyat-e-Zahrawi (Kitab al-Tasrif Surgical Treatise)"
            title_orig = "جراحیات زھراوی - التصریف لمن عجز عن التالیف"
            author = "Abu al-Qasim Khalaf ibn al-Abbas al-Zahrawi (Albucasis, 936-1013 CE)"
            category = "DIAGNOSTICS_SURGERY"
            language = "URDU"
            era = "1000 CE (Cordoba, Al-Andalus)"
            significance = "Father of surgery's 30-volume masterwork introducing over 200 surgical instruments, sutures, and operative interventions."
            topics = ["Operative Surgery", "Surgical Instruments", "Cautery", "Wound Care"]

        # 7. Ibn al-Quff (Kitab al-Umdah fi al-Jarahat)
        elif "umdah" in fl or "عمدہ" in filename:
            title = "Kitab al-Umdah fi al-Jarahat (Classical Treatise on Surgery & Anatomy)"
            title_orig = "کتاب العمدہ فی الجراحۃ"
            author = "Amin al-Dawla Ibn al-Quff al-Karaki (1233-1286 CE, Damascus)"
            category = "DIAGNOSTICS_SURGERY"
            language = "ARABIC"
            era = "13th Century CE"
            significance = "Pioneering medieval manual on surgical anatomy, vascular ligation, and trauma management."
            topics = ["Surgical Anatomy", "Vascular Surgery", "Trauma Care"]

        # 8. Ibn Zuhr (Kitab al-Taysir)
        elif "taysir" in fl or "تیسیر" in filename:
            title = "Kitab al-Taysir fi al-Mudawat wa al-Tadbir"
            title_orig = "کتاب التیسیر فی المداواۃ والتدبیر"
            author = "Abu Marwan Abd al-Malik Ibn Zuhr (Avenzoar, 1094-1162 CE)"
            category = "CLASSICAL_CANON"
            language = "ARABIC"
            era = "12th Century CE (Al-Andalus)"
            significance = "First experimental pharmacological treatise demonstrating rational drug therapy, pericarditis, and tracheostomy."
            topics = ["Rational Therapeutics", "Experimental Pharmacology", "Internal Medicine"]

        # 9. Kamil al-Sina'a al-Tibbiyya (Ali ibn al-Abbas al-Majusi / Haly Abbas)
        elif "kamil" in fl or "کامل" in filename:
            title = "Kamil al-Sina'a al-Tibbiyya (Kitab al-Malaki / Royal Book)"
            title_orig = "ترجمہ کامل الصناعۃ الطبیۃ (کتاب الملکی)"
            author = "Ali ibn al-Abbas al-Majusi (Haly Abbas, 930-994 CE)"
            category = "CLASSICAL_CANON"
            language = "URDU"
            era = "10th Century CE"
            significance = "Masterpiece on clinical medicine, embryology, neuroanatomy, and capillary circulation preceding Harvey."
            topics = ["Neuroanatomy", "Embryology", "Systemic Pathology"]

        # 10. Sharah Asbab wa Alamat (Hakim Mohammad Kabiruddin)
        elif "sharah asbab" in fl or "اسباب" in fl:
            vol_num = "1"
            if "2" in fl: vol_num = "2"
            elif "3" in fl: vol_num = "3"
            elif "4" in fl: vol_num = "4"
            title = f"Sharah Asbab wa Alamat - Jild {vol_num} (Clinical Symptomatology)"
            title_orig = f"شرح اسباب و علامات جلد {vol_num}"
            author = "Burhan al-Din Nafis / Urdu translation by Hakim Mohammad Kabiruddin"
            category = "CLASSICAL_CANON"
            language = "URDU"
            era = "20th Century Urdu Translation"
            significance = "Definitive BUMS reference text for clinical diagnosis, etiology (Asbab), and pathognomonic symptoms (Alamat)."
            topics = ["Etiology", "Symptomatology", "Clinical Diagnosis"]

        # 11. Kulliyat-e-Nafisi
        elif "nafisi" in fl or "نفیسی" in filename:
            title = "Kulliyat-e-Nafisi (Principles of Medicine Commentary)"
            title_orig = "کلیات نفیسی"
            author = "Burhan al-Din Nafis ibn Iwaz al-Kirmani (d. 1449 CE)"
            category = "PRINCIPLES_PHYSIOLOGY"
            language = "URDU"
            era = "15th Century CE"
            significance = "The most esteemed classical commentary on the theoretical foundation of Unani medicine (Umoor Tabiya & Mizaj)."
            topics = ["Umoor Tabiya", "Mizaj", "Akhlat", "Quwa wa Af'al"]

        # 12. National Formulary of Unani Medicine (NFUM)
        elif "national formulary" in fl or "nfum" in fl:
            part = "Part I" if "part-i" in fl or "part 1" in fl else "Part IV"
            title = f"National Formulary of Unani Medicine ({part})"
            author = "Ministry of AYUSH, Government of India / CCRUM"
            category = "PHARMACOPOEIA_FORMULARY"
            language = "ENGLISH"
            era = "Contemporary Statutory Standard"
            significance = "Official statutory formulary recognized under the Second Schedule of the Drugs and Cosmetics Act 1940."
            topics = ["Formulary", "Statutory Standards", "Compound Formulations", "Dosage Standards"]

        # 13. Essential Unani Medicines List
        elif "essential_unani" in fl or "essential" in fl:
            title = "Essential Unani Medicines List for Health Facilities"
            author = "Ministry of AYUSH, Government of India"
            category = "PHARMACOPOEIA_FORMULARY"
            language = "ENGLISH"
            era = "2024-2025 Edition"
            significance = "Government benchmark listing mandatory Unani formulations for Primary, Secondary and Tertiary AYUSH centers."
            topics = ["Essential Medicines", "Public Health", "AYUSH Standards"]

        # 14. Qarabadeen Compendia (Hamdard, Majidi, Qadiri, Sarkari, Azam)
        elif "qarabadeen" in fl or "qarabdeen" in fl or "قرابادین" in filename:
            category = "PHARMACOPOEIA_FORMULARY"
            language = "URDU"
            era = "Traditional Benchmark"
            topics = ["Qarabadeen", "Compound Formulations", "Shelf Life", "Advia Murakkaba"]
            if "hamdard" in fl:
                title = "Qarabadeen Hamdard Kamil (Complete Hamdard Pharmacopoeia)"
                title_orig = "قرابادین ہمدرد کامل"
                author = "Hamdard Laboratories / Hakim Abdul Hameed"
                significance = "Industry gold-standard pharmacopoeia for classical Unani manufacturing and clinical dispensary dispensing."
            elif "majidi" in fl:
                title = "Qarabadeen Majidi"
                title_orig = "قرابادین مجیدی"
                author = "Dawakhana Hakim Ajmal Khan / Hakeem Abdul Majeed"
                significance = "Standard authoritative formulary of Hindustani classical Unani manufacturing."
            elif "qaderi" in fl or "qadiri" in fl:
                title = "Qarabadeen-e-Qadiri"
                title_orig = "قرابادین قادری"
                author = "Hakim Mohammad Akbar Arzani"
                significance = "Classical 18th-century Persian/Urdu pharmacopoeia of high clinical repute."
            elif "sarkari" in fl:
                title = "Qarabadeen-e-Sarkari (Official Unani Formulary)"
                title_orig = "قرابادین سرکاری"
                author = "Government Central Pharmacy & Formulary Board"
                significance = "Statutory state formulary for standardized clinical compounding."
            elif "azam" in fl or "اعظم" in filename:
                title = "Qarabadeen-e-Azam (Urdu)"
                title_orig = "قرابادین اعظم اردو"
                author = "Hakim Mohammad Azam Khan"
                significance = "The definitive pharmacopeia detailing thousands of compound preparations."
            else:
                title = "Qarabadeen (Classical Formulation Pharmacopoeia)"
                author = "Classical Formulary Board"

        # 15. Bayaz-e-Kabir & Bayaz-e-Ajmal
        elif "bayaz" in fl or "بیاض" in filename:
            category = "PHARMACOPOEIA_FORMULARY"
            language = "URDU"
            era = "20th Century Classical"
            topics = ["Formulation Recipes", "Dawa-Sazi", "Clinical Experience"]
            if "ajmal" in fl:
                title = "Bayaz-e-Ajmal (Clinical Prescriptions of Masih-ul-Mulk)"
                title_orig = "بیاض اجمل"
                author = "Hakeem Ajmal Khan"
                significance = "Handwritten clinical Pearls and empirical formulas of Hakim Ajmal Khan."
            else:
                title = "Bayaz-e-Kabir (Dawa-Sazi wa Murakkabat Part 2)"
                title_orig = "بیاض کبیر حصہ دوم"
                author = "Hakeem Mohammad Kabiruddin"
                significance = "Practical laboratory manual of Unani pharmacy and compounding procedures."

        # 16. Haziq (Hakim Ajmal Khan)
        elif "hajik" in fl or "haziq" in fl or "حاذق" in filename:
            title = "Al-Haziq (Principles of Clinical Practice & Prescription Writing)"
            title_orig = "حاذق - مسیح الملک حکیم اجمل خان"
            author = "Maseeh-ul-Mulk Hakeem Ajmal Khan (1868-1927)"
            category = "PHARMACOPOEIA_FORMULARY"
            language = "URDU"
            era = "Early 20th Century"
            significance = "Master clinical treatise covering clinical practice, diagnostic subtleties, and prescription writing in Delhi."
            topics = ["Clinical Practice", "Prescription Writing", "Differential Regimens"]

        # 17. Makhzan al-Mufradat & Mufradat (Materia Medica)
        elif "makhzan" in fl or "mufradat" in fl or "مفردات" in filename:
            category = "MATERIA_MEDICA"
            language = "URDU"
            era = "Classical & Contemporary Benchmark"
            topics = ["Materia Medica", "Medicinal Plants", "Mizaj of Herbs", "Abdal (Substitutes)"]
            if "azizi" in fl:
                title = "Mufradat-e-Azizi"
                title_orig = "مفردات عزیزی"
                author = "Hakim Abdul Aziz Lucknowi"
                significance = "Standard Lucknow school Materia Medica reference."
            elif "muzaffar" in fl or "مظفر" in filename:
                title = "Khawas al-Adviya wa Kitab al-Mufradat"
                title_orig = "کتاب المفردات المعروف خواص الادویہ حکیم مظفر حسین"
                author = "Hakim Muzaffar Husain"
                significance = "Comprehensive botanical and pharmacological handbook for Unani herbs."
            else:
                title = "Makhzan al-Mufradat (Materia Medica Encyclopedia)"
                title_orig = "مخزن المفردات و خواص الادویہ"
                author = "Hakim Mohammad Kabiruddin"
                significance = "Unrivaled encyclopedia of single Unani drugs detailing Mizaj, Af'al, Mazarrat, and Musleh (correctives)."

        # 18. Kitab al-Murakkabat
        elif "murakkabat" in fl or "مرکبات" in filename:
            category = "PHARMACOPOEIA_FORMULARY"
            language = "URDU"
            era = "Academic & Clinical Standard"
            topics = ["Murakkabat", "Compound Formulations", "BUMS Syllabus"]
            if "zillur" in fl:
                title = "Kitab al-Murakkabat (Aligarh Academic Edition)"
                title_orig = "کتاب المرکبات - حکیم سید ظل الرحمن"
                author = "Hakim Syed Zillur Rehman (Aligarh)"
                significance = "Premier academic reference on compound Unani formulations with verified classical lineages."
            elif "azmi" in fl or "bums" in fl:
                title = "Murakkabat Advia (Complete BUMS Syllabus)"
                title_orig = "مرکبات ادویہ - حکیم وسیم احمد اعظمی"
                author = "Hakim Waseem Ahmad Azmi"
                significance = "Comprehensive curriculum text approved for BUMS and MD (Ilmul Advia) degree courses."
            elif "ghulam" in fl or "جیلانی" in filename:
                title = "Kitab al-Murakkabat"
                title_orig = "کتاب المرکبات حکیم غلام جیلانی"
                author = "Hakim Ghulam Jeelani"
                significance = "Master clinical formulary from the Punjab Unani medical tradition."
            else:
                title = "Kitab al-Murakkabat (Unani Compound Formulations)"
                title_orig = "کتاب المرکبات"
                author = "Hakim Muzaffar Husain / Classical Formulary Board"

        # 19. Tashkhees (Diagnostics)
        elif "tashkhees" in fl or "تشخیص" in filename:
            title = "Kitab-ul-Tashkhees wa Usool-e-Tashkhees (Clinical Diagnostics)"
            title_orig = "کتاب التشخیص و اصول تشخیص"
            author = "Dr. Zubair Ansari / Unani Diagnostic Council"
            category = "DIAGNOSTICS_SURGERY"
            language = "URDU"
            era = "Modern Clinical Unani"
            significance = "Comprehensive manual on Nabz (Pulse 10 parameters), Baul (Urine inspection), Baraz (Stool), and clinical examination."
            topics = ["Nabz (Pulse)", "Baul (Urinalysis)", "Baraz", "Clinical Assessment"]

        # 20. Umoor Tabiya & Asbab Sitta Zarooriya
        elif "umoor" in fl or "umur" in fl or "asbab" in fl or "طبیعیہ" in filename:
            title = "Umoor Tabiya wa Asbab-e-Sitta Zarooriya (Principles of Health & Physiology)"
            title_orig = "امور طبیعیہ و توضحیات اسباب ستہ ضروریہ"
            author = "Hakim Mohammad Kabiruddin"
            category = "PRINCIPLES_PHYSIOLOGY"
            language = "URDU"
            era = "Classical Benchmark"
            significance = "Foundational principles of human physiology: Arkan, Mizaj, Akhlat, Aaza, Arwah, Quwa, Af'al, and Six Lifestyle Essentials."
            topics = ["Umoor Tabiya", "Asbab Sitta", "Preventive Health", "Temperament"]

        # 21. Ilaj bil Tadbeer (Regimental Therapy)
        elif "tadbeer" in fl or "تدبیر" in filename:
            title = "Ilaj bil Tadbeer (Manual of Regimental Therapy)"
            title_orig = "علاج بالتدبیر"
            author = "AYUSH & CCRUM Regimental Therapy Faculty"
            category = "REGIMENTAL_THERAPY"
            language = "URDU"
            era = "Contemporary Benchmark"
            significance = "Clinical manual on non-pharmacological interventions: Hijama (Cupping), Fasd (Venesection), Dalk (Massage), Hammam, Nutool, and Riyazat."
            topics = ["Hijama", "Fasd", "Regimental Therapies", "Dalk"]

        # 22. Terminologies
        elif "terminology" in fl or "terminologies" in fl or "مصطلحات" in filename:
            title = "WHO & CCRUM Standard Medical Terminologies on Unani Medicine"
            author = "World Health Organization (WHO) & CCRUM"
            category = "TERMINOLOGY_GOVERNANCE"
            language = "ENGLISH"
            era = "International Regulatory Standard"
            significance = "Harmonized international standardized definitions, diagnostic nomenclature, and botanical correlates for Unani medicine."
            topics = ["Standardized Nomenclature", "ICD-11 TM2", "WHO Benchmarks"]

        # 23. Harrison's Principles of Internal Medicine
        elif "harrison" in fl:
            ed = "21st Edition" if "21" in fl else ("20th Edition" if "20" in fl else "19th Edition")
            title = f"Harrison's Principles of Internal Medicine ({ed})"
            author = "J. Larry Jameson, Anthony S. Fauci, Dennis L. Kasper, Stephen L. Hauser, Dan L. Longo, Joseph Loscalzo"
            category = "MODERN_INTERNAL_MEDICINE"
            language = "ENGLISH"
            era = "Global Modern Gold Standard"
            significance = "Foremost global reference for pathophysiology, internal medicine, evidence-based disease management, and clinical trials."
            topics = ["Internal Medicine", "Pathophysiology", "Cardiology", "Neurology", "Infectious Diseases"]

        # 24. Davidson's Medicine
        elif "davidson" in fl:
            ed = "23rd Edition" if "23" in fl else "2nd Edition Essentials"
            title = f"Davidson's Principles and Practice of Medicine ({ed})"
            author = "Stuart H. Ralston, Ian D. Penman, Mark W. J. Strachan, Richard P. Hobson"
            category = "MODERN_INTERNAL_MEDICINE"
            language = "ENGLISH"
            era = "Modern Clinical Standard"
            significance = "Authoritative international text on clinical medicine, patient examination, and clinical decision-making."
            topics = ["Clinical Medicine", "Differential Diagnosis", "Systemic Therapeutics"]

        # 25. Hutchison's Clinical Methods
        elif "hutchison" in fl:
            title = "Hutchison's Clinical Methods (23rd Edition)"
            author = "Michael Glynn, William M. Drake"
            category = "MODERN_INTERNAL_MEDICINE"
            language = "ENGLISH"
            era = "Modern Clinical Examination Gold Standard"
            significance = "The quintessential clinical guide to physical examination, bedside history elicitation, and diagnostic reasoning."
            topics = ["Bedside History", "Physical Examination", "Clinical Signs"]

        # 26. Robbins Pathology
        elif "robbins" in fl:
            title = "Robbins Basic Pathology (10th Edition)"
            author = "Vinay Kumar, Abul K. Abbas, Jon C. Aster"
            category = "MODERN_INTERNAL_MEDICINE"
            language = "ENGLISH"
            era = "Modern Pathology Standard"
            significance = "World's foundational textbook on general pathology, cellular injury, inflammation, and molecular genetics."
            topics = ["Pathology", "Cellular Injury", "Inflammation", "Hemodynamics"]

        # 27. Bailey & Love's Surgery
        elif "bailey" in fl:
            title = "Bailey & Love's Short Practice of Surgery (27th Edition)"
            author = "P. Ronan O'Connell, Andrew W. McCaskie, Robert D. Sayers"
            category = "DIAGNOSTICS_SURGERY"
            language = "ENGLISH"
            era = "Modern Surgical Standard"
            significance = "International benchmark textbook on surgical pathophysiology, operative decisions, and trauma care."
            topics = ["Operative Surgery", "Trauma", "Perioperative Care"]

        # 28. Dermatology
        elif "dermatology" in fl:
            title = "Dermatology RR6 Mahajan Prep (Clinical Dermatology Guide)"
            author = "Dr. Saurabh Mahajan"
            category = "MODERN_INTERNAL_MEDICINE"
            language = "ENGLISH"
            era = "Clinical Dermatology Benchmark"
            significance = "High-yield clinical dermatology guide for cutaneous manifestations of systemic disease."
            topics = ["Dermatology", "Cutaneous Lesions", "Skin Infections"]

        # 29. Matab wa Nuskha Naweesi (Dispensary Practice)
        elif "مطب" in filename or "nuskha" in fl:
            title = "Matab wa Nuskha Naweesi (Clinical Practice & Prescription Compounding)"
            title_orig = "مطب و نسخہ نویسی"
            author = "Hakim Mohammad Kabiruddin"
            category = "PHARMACOPOEIA_FORMULARY"
            language = "URDU"
            era = "20th Century Classical"
            significance = "Practical clinic outpatient manual detailing dispensary management and daily prescription protocols."
            topics = ["Outpatient Matab", "Prescription Writing", "Dispensary Logistics"]

        return {
            "title": title,
            "title_original": title_orig,
            "primary_author": author,
            "authority_category": category,
            "language": language,
            "publication_era": era,
            "filename": filename,
            "file_path": filepath,
            "file_size_bytes": sz_bytes,
            "file_format": ext,
            "clinical_significance": significance,
            "topics": topics
        }

    def index_downloaded_books(self, books_dir: Optional[str] = None) -> Dict[str, Any]:
        """Index all medical books from the configured or local archive directory into the database."""
        from apps.api.config import config, BASE_DIR
        if not books_dir:
            configured = getattr(config, "books_dir", None) or os.getenv("MATAB_BOOKS_DIR")
            candidates = [
                configured,
                str(BASE_DIR / "data" / "medical_books"),
                str(BASE_DIR / "medical_books"),
                "/Users/irfanashraf/Downloads/medical books"
            ]
            for c in candidates:
                if c and os.path.exists(c):
                    books_dir = c
                    break

        if not books_dir or not os.path.exists(books_dir):
            raise NotFoundError(f"Medical books repository not found. Please set MATAB_BOOKS_DIR in .env or place files in 'data/medical_books'.")

        files = sorted([f for f in os.listdir(books_dir) if not f.startswith(".")])
        conn = self._get_connection()
        indexed_count = 0
        bridged_sources_count = 0

        try:
            # Get default organization
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM organizations LIMIT 1;")
            org_row = cursor.fetchone()
            org_id = org_row["id"] if org_row else None

            for fname in files:
                fpath = os.path.join(books_dir, fname)
                if not os.path.isfile(fpath):
                    continue

                meta = self._derive_book_metadata(fname, fpath)
                sha = self._fingerprint_file(fpath)
                slug = re.sub(r'[^A-Z0-9]+', '-', meta['title'][:24].upper()).strip('-')
                file_hash_suffix = hashlib.md5(fname.encode()).hexdigest()[:6].upper()
                code = f"MED-LIB-{slug}-{file_hash_suffix}"

                # Check if already indexed by filename
                cursor.execute("SELECT id FROM medical_library_books WHERE filename = ?;", (fname,))
                existing = cursor.fetchone()

                now = datetime.utcnow().isoformat()
                if existing:
                    book_id = existing["id"]
                    cursor.execute("""
                        UPDATE medical_library_books
                        SET title = ?, title_original = ?, primary_author = ?, authority_category = ?,
                            language = ?, publication_era = ?, file_path = ?, file_size_bytes = ?,
                            file_format = ?, sha256_hash = ?, clinical_significance = ?, topics_json = ?,
                            updated_at = ?
                        WHERE id = ?;
                    """, (
                        meta["title"], meta["title_original"], meta["primary_author"], meta["authority_category"],
                        meta["language"], meta["publication_era"], fpath, meta["file_size_bytes"],
                        meta["file_format"], sha, meta["clinical_significance"], json.dumps(meta["topics"]),
                        now, book_id
                    ))
                else:
                    book_id = f"lib-{uuid.uuid4().hex[:12]}"
                    cursor.execute("""
                        INSERT INTO medical_library_books (
                            id, organization_id, code, title, title_original, primary_author, authority_category,
                            language, publication_era, filename, file_path, file_size_bytes, file_format,
                            sha256_hash, curation_status, clinical_significance, topics_json, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'VERIFIED_BENCHMARK', ?, ?, ?, ?);
                    """, (
                        book_id, org_id, code, meta["title"], meta["title_original"], meta["primary_author"],
                        meta["authority_category"], meta["language"], meta["publication_era"], fname, fpath,
                        meta["file_size_bytes"], meta["file_format"], sha, meta["clinical_significance"],
                        json.dumps(meta["topics"]), now, now
                    ))
                    indexed_count += 1

                # Bridge into clinical_sources if canonical authority
                if meta["authority_category"] in ("CLASSICAL_CANON", "PHARMACOPOEIA_FORMULARY", "MODERN_INTERNAL_MEDICINE"):
                    source_code = f"SRC-{code[8:24]}"
                    cursor.execute("SELECT id FROM clinical_sources WHERE code = ?;", (source_code,))
                    if not cursor.fetchone():
                        cursor.execute("""
                            INSERT INTO clinical_sources (
                                id, organization_id, code, title, author_authority, edition,
                                publication_year, legal_status, url_or_reference, verification_status, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'VERIFIED', ?);
                        """, (
                            f"csrc-{uuid.uuid4().hex[:12]}", org_id, source_code, meta["title"], meta["primary_author"],
                            meta["publication_era"], 2026, "HISTORICAL_BENCHMARK" if "CLASSICAL" in meta["authority_category"] else "STATUTORY",
                            f"file://{fpath}", now
                        ))
                        bridged_sources_count += 1

            conn.commit()
        finally:
            conn.close()

        return {
            "status": "SUCCESS",
            "total_files_examined": len(files),
            "newly_indexed_books": indexed_count,
            "bridged_kavs_sources": bridged_sources_count
        }

    def search_books(
        self,
        query: str = "",
        category: str = "",
        language: str = "",
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Search and filter cataloged medical library items."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            conditions = []
            params = []

            if query:
                q = f"%{query.strip().lower()}%"
                conditions.append("""(
                    LOWER(title) LIKE ? OR
                    LOWER(COALESCE(title_original, '')) LIKE ? OR
                    LOWER(primary_author) LIKE ? OR
                    LOWER(filename) LIKE ? OR
                    LOWER(clinical_significance) LIKE ?
                )""")
                params.extend([q, q, q, q, q])

            if category and category != "ALL":
                conditions.append("authority_category = ?")
                params.append(category)

            if language and language != "ALL":
                conditions.append("language = ?")
                params.append(language)

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            # Count total
            cursor.execute(f"SELECT COUNT(*) as count FROM medical_library_books {where_clause};", params)
            total = cursor.fetchone()["count"]

            # Fetch page
            params.extend([limit, offset])
            cursor.execute(f"""
                SELECT id, code, title, title_original, primary_author, authority_category,
                       language, publication_era, filename, file_path, file_size_bytes, file_format,
                       sha256_hash, curation_status, clinical_significance, topics_json, created_at
                FROM medical_library_books
                {where_clause}
                ORDER BY
                    CASE authority_category
                        WHEN 'CLASSICAL_CANON' THEN 1
                        WHEN 'PHARMACOPOEIA_FORMULARY' THEN 2
                        WHEN 'MATERIA_MEDICA' THEN 3
                        WHEN 'DIAGNOSTICS_SURGERY' THEN 4
                        WHEN 'MODERN_INTERNAL_MEDICINE' THEN 5
                        ELSE 6
                    END,
                    title ASC
                LIMIT ? OFFSET ?;
            """, params)

            books = []
            for r in cursor.fetchall():
                books.append({
                    "id": r["id"],
                    "code": r["code"],
                    "title": r["title"],
                    "title_original": r["title_original"],
                    "primary_author": r["primary_author"],
                    "authority_category": r["authority_category"],
                    "authority_category_label": CATEGORIES.get(r["authority_category"], r["authority_category"]),
                    "language": r["language"],
                    "publication_era": r["publication_era"],
                    "filename": r["filename"],
                    "file_path": r["file_path"],
                    "file_size_mb": round(r["file_size_bytes"] / (1024 * 1024), 2),
                    "file_format": r["file_format"],
                    "sha256_hash": r["sha256_hash"],
                    "curation_status": r["curation_status"],
                    "clinical_significance": r["clinical_significance"],
                    "topics": json.loads(r["topics_json"] or "[]"),
                    "created_at": r["created_at"]
                })

            return {
                "total": total,
                "limit": limit,
                "offset": offset,
                "books": books
            }
        finally:
            conn.close()

    def get_library_stats(self) -> Dict[str, Any]:
        """Aggregate statistics on the medical library."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count, SUM(file_size_bytes) as total_bytes FROM medical_library_books;")
            overall = cursor.fetchone()
            total_books = overall["count"]
            total_gb = round((overall["total_bytes"] or 0) / (1024 * 1024 * 1024), 2)

            cursor.execute("""
                SELECT authority_category, COUNT(*) as count
                FROM medical_library_books
                GROUP BY authority_category
                ORDER BY count DESC;
            """)
            by_category = {r["authority_category"]: r["count"] for r in cursor.fetchall()}

            cursor.execute("""
                SELECT language, COUNT(*) as count
                FROM medical_library_books
                GROUP BY language
                ORDER BY count DESC;
            """)
            by_language = {r["language"]: r["count"] for r in cursor.fetchall()}

            return {
                "total_books": total_books,
                "total_size_gb": total_gb,
                "by_category": by_category,
                "by_language": by_language,
                "categories_catalog": CATEGORIES
            }
        finally:
            conn.close()

    def get_book_by_id(self, book_id: str) -> Dict[str, Any]:
        """Get details for a single book."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM medical_library_books WHERE id = ? OR code = ?;
            """, (book_id, book_id))
            r = cursor.fetchone()
            if not r:
                raise NotFoundError(f"Medical book not found: {book_id}")

            return {
                "id": r["id"],
                "code": r["code"],
                "title": r["title"],
                "title_original": r["title_original"],
                "primary_author": r["primary_author"],
                "authority_category": r["authority_category"],
                "authority_category_label": CATEGORIES.get(r["authority_category"], r["authority_category"]),
                "language": r["language"],
                "publication_era": r["publication_era"],
                "filename": r["filename"],
                "file_path": r["file_path"],
                "file_size_mb": round(r["file_size_bytes"] / (1024 * 1024), 2),
                "file_format": r["file_format"],
                "sha256_hash": r["sha256_hash"],
                "curation_status": r["curation_status"],
                "clinical_significance": r["clinical_significance"],
                "topics": json.loads(r["topics_json"] or "[]"),
                "created_at": r["created_at"]
            }
        finally:
            conn.close()
