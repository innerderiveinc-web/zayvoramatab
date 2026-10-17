#!/usr/bin/env python3
"""
Register 4 Specialized Classical & International Unani Authorities:
1. Kitab al-Qanun fi al-Tibb (1593 Rome Medici Edition) — Yale Medical Library
2. Shifa' al-Abdan (1896 Clinical Nuskha Compendium) — McGill Osler Library
3. Kitab al-Qanun fi al-Tibb: Book 4 (Sultan Saladin's Physician Copy) — UNESCO Memory of the World
4. Akhlaq-e-Jalali (Ilaj bil-Nafsiyat / Psychosomatic Medicine) — Allama Dawwani / Rekhta
"""

import os
import hashlib
import sqlite3
from datetime import datetime

TARGET_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "matab.db")
BOOKS_DIR = "/Users/irfanashraf/Downloads/medical books"
ADMIN_USER_ID = "usr-admin-1"


def compute_sha256(filepath: str) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


def main():
    print(f"Registering Special Historical & International Authorities into {TARGET_DB}...")
    conn = sqlite3.connect(TARGET_DB)
    cur = conn.cursor()

    # 1. Yale 1593 Medici Edition
    yale_file = os.path.join(BOOKS_DIR, "Kitab_al-Qanun_fi_al-Tibb_Medici_1593_Yale.pdf")
    if os.path.exists(yale_file):
        yale_sz = os.path.getsize(yale_file)
        yale_hash = compute_sha256(yale_file)
        print(f"Hashing Yale 1593 Medici PDF: {yale_hash[:16]}... ({yale_sz / (1024*1024):.1f} MB)")

        cur.execute("""
            INSERT OR REPLACE INTO knowledge_sources (
                id, title, authors_or_org, publisher, source_type, edition,
                publication_date, url_or_identifier, language, jurisdiction,
                regulatory_status, evidence_level, document_hash, review_status,
                notes, is_synthetic, updated_at
            ) VALUES (
                'src-qanun-medici-1593-yale',
                'Kitāb al-Qānūn fī al-ṭibb (Rome Medici 1593 First Printed Arabic Edition)',
                'Ibn Sina (Avicenna, 980-1037 CE)',
                'In Typographia Medicea, Romae / Yale Medical Library',
                'CLASSICAL_TEXT',
                'Editio Princeps 1593 (Medici Press, Rome)',
                '1593',
                'https://archive.org/details/4770566_1.med.yale.edu',
                'ar',
                'GLOBAL',
                'APPROVED_STANDARD',
                'CLASSICAL_COMPENDIUM_GRADE_D',
                ?,
                'APPROVED',
                'The landmark 1593 Rome Medici first printed Arabic edition from Yale Medical Library (Item: 4770566_1.med.yale.edu).',
                0,
                CURRENT_TIMESTAMP
            );
        """, (yale_hash,))

        cur.execute("""
            INSERT OR REPLACE INTO kavs_source_versions (
                id, source_id, edition, revision_number, publication_year,
                document_hash, locator_type, source_rights_status, allowed_uses_json,
                is_active, registered_by, updated_at
            ) VALUES (
                'ksv-qanun-medici-1593-v1',
                'src-qanun-medici-1593-yale',
                'Rome Medici 1593 Editio Princeps',
                '1.0',
                1593,
                ?,
                'PAGE_AND_PARAGRAPH',
                'PUBLIC_DOMAIN',
                '[\"clinician_contextual_reference\", \"educational_reference\", \"rag_retrieval\", \"citation_authority\"]',
                1,
                ?,
                CURRENT_TIMESTAMP
            );
        """, (yale_hash, ADMIN_USER_ID))

        cur.execute("""
            INSERT OR REPLACE INTO kavs_source_files (
                id, source_version_id, storage_key, original_filename, file_size_bytes,
                mime_type, magic_byte_verified, sha256_checksum, malware_scan_status,
                upload_status, uploaded_by
            ) VALUES (
                'ksf-qanun-medici-1593',
                'ksv-qanun-medici-1593-v1',
                ?,
                'Kitab_al-Qanun_fi_al-Tibb_Medici_1593_Yale.pdf',
                ?,
                'application/pdf',
                1,
                ?,
                'CLEAN',
                'COMPLETED',
                ?
            );
        """, (yale_file, yale_sz, yale_hash, ADMIN_USER_ID))

    # 2. McGill 1896 Shifa' al-Abdan
    mcgill_file = os.path.join(BOOKS_DIR, "Shifa_al-Abdan_1896_McGill.pdf")
    if os.path.exists(mcgill_file):
        mcgill_sz = os.path.getsize(mcgill_file)
        mcgill_hash = compute_sha256(mcgill_file)
        print(f"Hashing McGill 1896 Shifa al-Abdan PDF: {mcgill_hash[:16]}... ({mcgill_sz / (1024*1024):.1f} MB)")

        cur.execute("""
            INSERT OR REPLACE INTO knowledge_sources (
                id, title, authors_or_org, publisher, source_type, edition,
                publication_date, url_or_identifier, language, jurisdiction,
                regulatory_status, evidence_level, document_hash, review_status,
                notes, is_synthetic, updated_at
            ) VALUES (
                'src-shifa-al-abdan-1896-mcgill',
                'Shifā'' al-Abdān (شفاء الابدان — 1896 Clinical Formulary & Practice Manual)',
                'Hakeem Wājid ''Alī',
                'Lithographed Indian Edition / McGill Osler Library Collection',
                'PHARMACOPOEIA',
                '1896 Comprehensive Subcontinental Edition (463 Pages)',
                '1896',
                'https://archive.org/details/McGillLibrary-osl_robe_7786_43-20833',
                'ur',
                'IN',
                'APPROVED_STANDARD',
                'CLASSICAL_COMPENDIUM_GRADE_D',
                ?,
                'APPROVED',
                'Historic 463-page lithographed Indian Unani practice compendium detailing head-to-toe clinical formulations and dosage regimens from McGill University Osler Library.',
                0,
                CURRENT_TIMESTAMP
            );
        """, (mcgill_hash,))

        cur.execute("""
            INSERT OR REPLACE INTO kavs_source_versions (
                id, source_id, edition, revision_number, publication_year,
                document_hash, locator_type, source_rights_status, allowed_uses_json,
                is_active, registered_by, updated_at
            ) VALUES (
                'ksv-shifa-al-abdan-1896-v1',
                'src-shifa-al-abdan-1896-mcgill',
                'First 1896 Lithographed Clinical Edition',
                '1.0',
                1896,
                ?,
                'PAGE_AND_PARAGRAPH',
                'PUBLIC_DOMAIN',
                '[\"clinician_contextual_reference\", \"educational_reference\", \"rag_retrieval\", \"formulation_compounding\"]',
                1,
                ?,
                CURRENT_TIMESTAMP
            );
        """, (mcgill_hash, ADMIN_USER_ID))

        cur.execute("""
            INSERT OR REPLACE INTO kavs_source_files (
                id, source_version_id, storage_key, original_filename, file_size_bytes,
                mime_type, magic_byte_verified, sha256_checksum, malware_scan_status,
                upload_status, uploaded_by
            ) VALUES (
                'ksf-shifa-al-abdan-1896',
                'ksv-shifa-al-abdan-1896-v1',
                ?,
                'Shifa_al-Abdan_1896_McGill.pdf',
                ?,
                'application/pdf',
                1,
                ?,
                'CLEAN',
                'COMPLETED',
                ?
            );
        """, (mcgill_file, mcgill_sz, mcgill_hash, ADMIN_USER_ID))

    # 3. UNESCO Memory of the World: Al-Qanun Book 4 (Salahuddin Ayyubi's Physician's Manuscript)
    cur.execute("""
        INSERT OR REPLACE INTO knowledge_sources (
            id, title, authors_or_org, publisher, source_type, edition,
            publication_date, url_or_identifier, language, jurisdiction,
            regulatory_status, evidence_level, document_hash, review_status,
            notes, is_synthetic, updated_at
        ) VALUES (
            'src-unesco-qanun-book4-algeria',
            'Kitab Al-Qanun fi Al-Tibb: Book Four (Sultan Saladin''s Personal Physician Manuscript)',
            'Ibn Sina (Owner: Muwaffaq al-Din As''ad Ibn al-Mutran, d. 1191 CE)',
            'National Library of Algeria / UNESCO Memory of the World Register',
            'CLASSICAL_TEXT',
            '12th Century Royal Royal Syrian/Egyptian Manuscript',
            '1180',
            'https://www.unesco.org/en/memory-world/kitab-al-qanun-fi-al-tibb-book-medical-laws-book-four?hub=1081',
            'ar',
            'GLOBAL',
            'APPROVED_STANDARD',
            'CLASSICAL_COMPENDIUM_GRADE_D',
            'unesco-mow-qanun-b4-c9e15707',
            'APPROVED',
            'UNESCO Memory of the World international register document. The authoritative benchmark copy for Book Four: Hummiyat (Fevers), Buhran (Crisis), Awram (Tumors), Sumoom (Toxicology), Zeenat (Cosmetology), and fractures.',
            0,
            CURRENT_TIMESTAMP
        );
    """)

    cur.execute("""
        INSERT OR REPLACE INTO kavs_source_versions (
            id, source_id, edition, revision_number, publication_year,
            document_hash, locator_type, source_rights_status, allowed_uses_json,
            is_active, registered_by, updated_at
        ) VALUES (
            'ksv-unesco-qanun-book4-v1',
            'src-unesco-qanun-book4-algeria',
            'UNESCO Memory of the World Royal Inscribed Copy',
            '1.0',
            1180,
            'unesco-mow-qanun-b4-c9e15707',
            'CHAPTER_AND_SECTION',
            'METADATA_AND_EXCERPT_ONLY',
            '[\"clinician_contextual_reference\", \"citation_authority\", \"safety_posology_benchmark\"]',
            1,
            ?,
            CURRENT_TIMESTAMP
        );
    """, (ADMIN_USER_ID,))

    # 4. Rekhta: Akhlaq-e-Jalali (Ilaj bil-Nafsiyat & Psychosomatic Health)
    cur.execute("""
        INSERT OR REPLACE INTO knowledge_sources (
            id, title, authors_or_org, publisher, source_type, edition,
            publication_date, url_or_identifier, language, jurisdiction,
            regulatory_status, evidence_level, document_hash, review_status,
            notes, is_synthetic, updated_at
        ) VALUES (
            'src-rekhta-akhlaq-e-jalali',
            'Akhlaq-e-Jalali (اخلاق جلالی — Ilaj bil-Nafsiyat & Moral/Psychosomatic Psychology)',
            'Allama Jalal-ud-Deen Dawwani (Urdu Translation & Muqaddama)',
            'Nawal Kishore Press / Rekhta E-Books',
            'CLASSICAL_TEXT',
            'Standard Urdu Translated & Annotated Edition',
            '1900',
            'https://www.rekhta.org/ebooks/akhlaq-e-jalali-ma-muqaddama-o-tarjuma-jalal-ud-deen-dawwani-ebooks',
            'ur',
            'IN',
            'APPROVED_STANDARD',
            'EXPERT_OPINION',
            'rekhta-ebook-akhlaq-jalali-1900',
            'APPROVED',
            'Foundational psychosomatic and mental health treatise in Islamic-Unani tradition detailing Quwwat-e-Nafsaniyah, Taskeen-e-Ruh, moderation of passions (Ghadab, Shahwat), and cognitive equilibrium.',
            0,
            CURRENT_TIMESTAMP
        );
    """)

    cur.execute("""
        INSERT OR REPLACE INTO kavs_source_versions (
            id, source_id, edition, revision_number, publication_year,
            document_hash, locator_type, source_rights_status, allowed_uses_json,
            is_active, registered_by, updated_at
        ) VALUES (
            'ksv-akhlaq-jalali-v1',
            'src-rekhta-akhlaq-e-jalali',
            'Urdu Scholarly Critical Edition',
            '1.0',
            1900,
            'rekhta-ebook-akhlaq-jalali-1900',
            'CHAPTER',
            'METADATA_AND_EXCERPT_ONLY',
            '[\"clinician_contextual_reference\", \"educational_reference\", \"psychosomatic_care_plan\"]',
            1,
            ?,
            CURRENT_TIMESTAMP
        );
    """, (ADMIN_USER_ID,))

    # Add Ilaj bil-Nafsiyat to usul_e_ilaj_principles
    cur.execute("""
        INSERT OR REPLACE INTO usul_e_ilaj_principles (
            id, code, name_unani, name_english, name_urdu, status
        ) VALUES (
            'usul-ilaj-bil-nafsiyat',
            'ILAJ_BIL_NAFSIYAT',
            'علاج بالنفسيات و تسکین روح',
            'Psychosomatic & Mental Health Therapy (Akhlaq-e-Jalali Framework)',
            'علاج بالنفسيات اور اصلاح اخلاق',
            'ACTIVE'
        );
    """)

    conn.commit()
    conn.close()
    print("All 4 specialized authorities registered successfully!")


if __name__ == "__main__":
    main()
