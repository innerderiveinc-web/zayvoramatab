"""Seed script for ZAYVORA Protocol Kits (K-01 to K-21) and Herb-Drug Safety Matrix."""

import sqlite3
import uuid

KITS = [
    ("K-01", "DIABETES CONTROL KIT", "HepaClear + DiabEase + MindBalance", "T2DM HbA1c >7%; Pre-diabetes", 3800, 5500, "AYUSH", "CLINIC"),
    ("K-02", "METABOLIC BURN KIT", "HepaClear + MetaboBurn-M + LipidClear", "Obesity BMI >25; Metabolic syndrome", 4000, 6000, "FSSAI+AYUSH", "CLINIC"),
    ("K-03", "LIPID MANAGEMENT KIT", "LipidClear + HepaClear + CardioGuard", "Dyslipidaemia; Statin adjunct", 3500, 5000, "AYUSH", "CLINIC"),
    ("K-04", "BLOOD PRESSURE KIT", "HyperCalm (AYUSH-Rx) + CardioGuard + MindBalance", "HTN Stage 1-2; Stress HTN", 4500, 7000, "AYUSH (Rx)", "ADVANCED_RX"),
    ("K-05", "CARDIAC PROTECTION KIT", "CardioGuard + LipidClear + HyperCalm", "IHD; Post-MI rehabilitation; High CVD risk", 5500, 8000, "AYUSH", "ADVANCED_RX"),
    ("K-06", "STRESS-ANXIETY KIT", "MindBalance + Sleep+Stress", "GAD; Burnout; HPA dysregulation", 2500, 3800, "FSSAI+AYUSH", "RETAIL"),
    ("K-07", "SLEEP RESTORE KIT", "Sleep+Stress + MindBalance", "Insomnia; Sleep latency; Non-restorative sleep", 2200, 3500, "FSSAI", "RETAIL"),
    ("K-08", "RESPIRATORY CARE KIT", "LungEase + Immunity", "Asthma adjunct; COPD; Allergic rhinitis", 2800, 4000, "FSSAI", "CLINIC"),
    ("K-09", "JOINT CARE KIT", "JointFree + Immunity", "OA; Gout; Arthritis; Joint inflammation", 3000, 4500, "FSSAI", "CLINIC"),
    ("K-10", "ED RESTORE KIT (Rx)", "VigorX-ED (AYUSH-Rx) + TestoVital Classic + MindBalance", "ED; Psychogenic + Vasculogenic", 6000, 9000, "AYUSH (Rx)", "ADVANCED_RX"),
    ("K-11", "MALE FERTILITY KIT", "FertiMax-M + Fertility PRO + SemenGuard", "Oligospermia; Asthenospermia; High DFI", 7000, 10000, "FSSAI+AYUSH", "ADVANCED_RX"),
    ("K-12", "TESTOSTERONE RESTORE KIT", "TestoVital Classic + Men Daily", "Low T; Secondary hypogonadism", 5000, 7500, "AYUSH", "CLINIC"),
    ("K-13", "PROSTATE HEALTH KIT", "ProstaGuard + UroClear + Men Daily", "BPH; LUTS; Prostatitis", 3500, 5000, "FSSAI", "CLINIC"),
    ("K-14", "PCOS KIT", "CycloCare-PCOS + HepaClear + MindBalance", "PCOS all phenotypes; Insulin-resistant PCOS", 4500, 6500, "FSSAI", "CLINIC"),
    ("K-15", "LEUCORRHOEA KIT", "LeucoClear + FemCare-L + Women Daily", "BV; Candida; Recurrent vaginal infection", 3500, 5000, "FSSAI", "CLINIC"),
    ("K-16", "CYCLE CARE KIT", "UterTone + FemCare-L + Women Daily", "Dysmenorrhoea; Menorrhagia; PMS; LPD", 3200, 4800, "FSSAI", "CLINIC"),
    ("K-17", "MENOPAUSE KIT", "MenoPease + Women Daily + CardioGuard", "Hot flushes; Vaginal atrophy; Bone loss; Mood", 4500, 7000, "FSSAI", "CLINIC"),
    ("K-18", "FEMALE FERTILITY KIT", "FertiliWomen + CycloCare-PCOS + UterTone", "Unexplained infertility; PCOS-fertility; IVF support", 6000, 9000, "FSSAI", "ADVANCED_RX"),
    ("K-19", "IMMUNITY SHIELD KIT", "Immunity + LungEase", "Prevention; Post-viral; Recurrent infections", 2500, 3500, "FSSAI", "RETAIL"),
    ("K-20", "GUT RESTORE KIT", "GutEase-IBS + HepaClear + MindBalance", "IBS; Leaky gut; Dysbiosis", 3000, 4500, "FSSAI", "CLINIC"),
    ("K-21", "HAIR RESTORE KIT", "HairRoot-X + Women Daily + MindBalance", "Androgenic alopecia; Telogen effluvium", 2800, 4000, "FSSAI", "RETAIL")
]

INTERACTIONS = [
    ("Asgandh (Withania somnifera)", "Thyroid medications", "Levothyroxine, Carbimazole", "Additive thyroid stimulation — TSH may fall further", "MODERATE", "Monitor TSH at 6 weeks. Reduce thyroid medication dose if TSH <0.5 mIU/L."),
    ("Asgandh (Withania somnifera)", "Sedatives / Hypnotics", "Diazepam, Alprazolam, Zolpidem", "Additive CNS depression", "MODERATE", "Reduce sedative dose by 25-50% if co-prescribing. Monitor for excessive daytime somnolence."),
    ("Asgandh (Withania somnifera)", "Immunosuppressants", "Cyclosporine, Tacrolimus, Sirolimus", "CYP3A4 induction — reduces immunosuppressant serum levels", "HIGH", "AVOID in transplant patients. Immunosuppressant levels must be monitored closely if prescribed."),
    ("Guggul (Commiphora wightii)", "Anticoagulants / Antiplatelets", "Warfarin, Rivaroxaban, Aspirin", "Additive antiplatelet effect — increased bleeding risk", "MODERATE", "INR monitoring at 2 and 4 weeks post-initiation. Advise patient on bruising/bleeding vigilance."),
    ("Guggul (Commiphora wightii)", "Beta-blockers", "Propranolol, Atenolol, Metoprolol", "Pharmacokinetic interaction — reduces beta-blocker AUC", "MODERATE", "Blood pressure monitoring at 2 weeks. Beta-blocker dose may require adjustment."),
    ("Guggul (Commiphora wightii)", "Statins", "Atorvastatin, Rosuvastatin", "Guggulsterones induce CYP3A4 — may reduce statin plasma concentration", "LOW", "Monitor lipid panel at 6 weeks. Additive lipid-lowering often offsets clearance."),
    ("Guggul (Commiphora wightii)", "Immunosuppressants", "Cyclosporine", "Induces CYP3A4 and P-gp — reduces cyclosporine bioavailability by up to 50%", "CONTRAINDICATED", "ABSOLUTELY CONTRAINDICATED in organ transplant recipients."),
    ("Jatamansi (Nardostachys jatamansi)", "MAOIs", "Phenelzine, Tranylcypromine", "Additive MAO-A inhibition — risk of hypertensive crisis or serotonin toxicity", "CONTRAINDICATED", "ABSOLUTELY CONTRAINDICATED with pharmaceutical MAOIs."),
    ("Jatamansi (Nardostachys jatamansi)", "SSRIs / SNRIs", "Sertraline, Escitalopram, Duloxetine", "Additive serotonergic effect — mild serotonin syndrome risk", "MODERATE", "Start Jatamansi at half dose (500mg/day). Monitor for agitation, tachycardia, or diaphoresis."),
    ("Aqarqarha (Anacyclus pyrethrum)", "Antihypertensives", "All classes (ACEi, ARBs, CCBs, Diuretics)", "Cardiac and sympathetic stimulation opposes blood pressure control", "CONTRAINDICATED", "ABSOLUTE CONTRAINDICATION in hypertensive patients. Never prescribe in uncontrolled BP."),
    ("Aqarqarha (Anacyclus pyrethrum)", "Anticoagulants", "Warfarin", "Mild anticoagulant potentiation", "MODERATE", "Monitor INR when initiating Aqarqarha micro-dose."),
    ("Piperine (Filfil Siyah)", "CYP3A4 / P-gp Substrates", "Statins, Calcium channel blockers, Immunosuppressants", "CYP3A4 and P-gp inhibition increases systemic drug bioavailability", "MODERATE", "Ensure piperine dose does not exceed 10mg/day. Review concurrent prescription drugs."),
    ("Mulethi (Glycyrrhiza glabra)", "Antihypertensives", "All antihypertensive classes", "Pseudohyperaldosteronism — glycyrrhizin causes sodium retention, hypokalemia, and elevated BP", "HIGH", "Contraindicated in hypertensive patients. Maximum 4 weeks continuous whole root in normotensive patients."),
    ("Zafran (Crocus sativus)", "Antidepressants / SSRIs", "Fluoxetine, Sertraline, Citalopram", "Additive serotonin pathway stimulation", "MODERATE", "Use cautiously with SSRIs. Keep Zafran dose at 15-30mg/day; avoid exceeding 60mg/day."),
    ("Arjuna (Terminalia arjuna)", "Cardiac Glycosides", "Digoxin", "Additive positive inotropy and cardiac conduction slowing — bradycardia risk", "MODERATE", "Monitor resting heart rate and serum digoxin levels at 2 weeks."),
    ("Arjuna (Terminalia arjuna)", "Calcium Channel Blockers / Beta-Blockers", "Amlodipine, Nifedipine, Metoprolol", "Additive hypotensive and bradycardic effect", "MODERATE", "Monitor blood pressure and pulse rate at 2 weeks.")
]


def seed_kits_and_interactions(db_path: str = "matab.db"):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Seed Kits
    for code, name, prods, ind, pmin, pmax, track, ktype in KITS:
        cur.execute("""
            INSERT INTO protocol_kits (id, kit_code, name, products_included, indication, price_min_inr, price_max_inr, regulatory_track, kit_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(kit_code) DO UPDATE SET
                name = excluded.name,
                products_included = excluded.products_included,
                indication = excluded.indication,
                price_min_inr = excluded.price_min_inr,
                price_max_inr = excluded.price_max_inr,
                regulatory_track = excluded.regulatory_track,
                kit_type = excluded.kit_type;
        """, (f"kit-{uuid.uuid4().hex[:8]}", code, name, prods, ind, pmin, pmax, track, ktype))

    # Seed Interactions
    cur.execute("DELETE FROM herb_drug_interactions;")
    for herb, drug_cls, drugs, desc, sev, mgmt in INTERACTIONS:
        cur.execute("""
            INSERT INTO herb_drug_interactions (id, herb_name, drug_class, specific_drugs, interaction_description, severity, management_protocol)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (f"hdi-{uuid.uuid4().hex[:8]}", herb, drug_cls, drugs, desc, sev, mgmt))

    conn.commit()
    conn.close()
    print(f"Seeded {len(KITS)} Protocol Kits and {len(INTERACTIONS)} Herb-Drug Interactions successfully.")


if __name__ == "__main__":
    seed_kits_and_interactions()
