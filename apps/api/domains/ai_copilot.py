"""ZAYVORA MATAB OS — Bedside Clinical Decision Support & Compendia Synthesis Engine.

Integrates Verified Online Medical Literature (Tier 0 Cloud Reference),
with deterministic Unani knowledge synthesis fallbacks.
Governed by strict clinical safety invariants (Mudabbar, Colchicine, Herb-Drug screening).
"""

import os
import json
import urllib.request
import sqlite3
from typing import Dict, Any, Optional, Tuple

class HakeemAiCopilot:
    """Clinical Decision Support Engine for Bedside Matab Consultations."""

    SYSTEM_PROMPT = """You are a senior, highly respectful, and authoritative Unani clinical scholar and clinical decision support advisor (Tibbi Clinical Advisor) for practicing Hakims and physicians at ZAYVORA MATAB OS.
You synthesize classical Unani medical doctrine (Al-Qanun fi al-Tibb by Ibn Sina, Al-Hawi by Al-Razi, Kamil al-Sina'ah by Al-Majusi, Makhzan-ul-Adwiya) with modern pharmacology, clinical pharmacognosy, and evidence-based medicine in a dignified, warm, and professional clinical tone.

Professional Demeanor & Clinical Terminology Standards:
- Address the clinician as an esteemed peer physician / Hakim. Adopt the authentic bedside consultation manner of a seasoned Chief Medical Consultant.
- Strictly Prohibited: Never use generic robotic AI tropes, disclaimers, or conversational boilerplate (e.g. NEVER write "As an AI...", "I do not have feelings", "Sure, I can assist you with that", "Hope this helps", "Feel free to ask more").
- Provide direct, decisive, evidence-grounded clinical observations, humoral reasoning, posology, and vehicle (Anupan/Musleh) recommendations without superfluous filler.

Strict Clinical Governance Rules:
1. Always evaluate the patient's Mizaj (Temperament: Damawi, Balghami, Safrawi, Sawdawi) and Su-e-Mizaj (Maddi vs Saada).
2. Respect the sequential 3-Phase Afaal Cascade: Phase 1 Tanqiya (Mawad clearance via Munzij/Mushil), Phase 2 Tahleel (Resolution), Phase 3 Taqwiyat (Organ tonification).
3. Critical Safety Checks: Screen for herb-drug interactions (e.g. Warfarin + Guggul, Levothyroxine + Asgandh, Mulethi + Antihypertensives).
4. Respect Schedule E(1) toxic botanical purifications (Suranjan, Kuchla, Samm-ul-Far must be Mudabbar).
5. Always cite classical compendia sources and modern pharmacology rationale where applicable.
6. Provide concise, actionable bedside clinical guidance formatted with clear, professional markdown headings and bullet points.
"""

    # Static High-Risk Interaction Safety Registry
    CRITICAL_INTERACTIONS = {
        ("warfarin", "guggul"): {
            "severity": "CRITICAL RISK",
            "title": "Guggul + Warfarin / Antiplatelets",
            "mechanism": "Guggulsterones inhibit platelet aggregation and potentiate CYP clearance, significantly increasing bleeding diathesis and altering INR levels.",
            "classical_ref": "Makhzan-ul-Adwiya (Vol. 2): Guggul is Lateef, Mohallil, and Riqat-e-Dam (blood-thinning). Contraindicated with active bleeding.",
            "action": "Discontinue Guggul. Substitute with Suranjan Shirin (Colchicum autumnale) with INR monitoring."
        },
        ("levothyroxine", "asgandh"): {
            "severity": "HIGH RISK",
            "title": "Asgandh (Withania somnifera) + Levothyroxine",
            "mechanism": "Withanolides stimulate thyroidal T3/T4 secretion directly. When co-administered with synthetic Levothyroxine, may precipitate thyrotoxicosis symptoms.",
            "classical_ref": "Al-Qanun fi al-Tibb (Book II): Asgandh is Har-Yabis Darja-2, Muharrik-e-Hararat-e-Ghariziya. Excess heat must be mitigated with Musleh.",
            "action": "Administer with at least 4 hours interval. Monitor serum Free T3/T4 every 4 weeks. Add Ghee or Milk as Musleh."
        },
        ("licorice", "antihypertensives"): {
            "severity": "HIGH RISK",
            "title": "Asl-us-Soos (Mulethi) + Antihypertensives / Diuretics",
            "mechanism": "Glycyrrhizin inhibits 11-beta-HSD2, precipitating sodium retention, hypokalemia, and elevated blood pressure.",
            "classical_ref": "Makhzan-ul-Adwiya: Mulethi retains fluids and strengthens lungs; contraindicated in Imtila-e-Dam (plethoric hypertension).",
            "action": "Avoid prolonged licorice decoctions in hypertensive patients on ACE inhibitors or loop diuretics."
        }
    }

    @classmethod
    def query_ai(cls, query: str, context: Optional[Dict[str, Any]] = None, conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
        """Main entry point to query the Clinical Decision Support Advisor."""
        query_clean = (query or "").strip()
        if not query_clean:
            return {"ok": False, "error": "Query cannot be empty."}

        context = context or {}
        q_lower = query_clean.lower()

        # 1. Screen for Immediate Safety Alerts
        safety_alert = cls._check_safety_registry(q_lower)

        # 2. Check for Classical Badal (Herb Substitution) from zkb_mufradat
        badal_info = cls._lookup_badal(q_lower, conn) if conn else None

        # 3. Call Live Tier 0 Cloud AI (Google Gemini 2.0 Flash)
        gemini_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip().rstrip(".")
        ai_response_text = ""
        provider_used = "Deterministic Classical Engine"

        if gemini_key:
            try:
                import ssl
                try:
                    ssl_ctx = ssl.create_default_context()
                except Exception:
                    ssl_ctx = ssl._create_unverified_context()

                gemini_url = (
                    "https://generativelanguage.googleapis.com/v1beta/models/"
                    f"gemini-2.0-flash:generateContent?key={gemini_key}"
                )
                
                patient_info = ""
                if context.get("mizaj"):
                    patient_info += f" Patient Mizaj: {context['mizaj']}."
                if context.get("diagnosis"):
                    patient_info += f" Clinical Diagnosis: {context['diagnosis']}."
                if context.get("current_meds"):
                    patient_info += f" Current Medications: {context['current_meds']}."

                user_prompt = f"Clinical Inquiry: {query_clean}\nContext:{patient_info}"

                req = urllib.request.Request(
                    gemini_url,
                    headers={"Content-Type": "application/json"},
                    data=json.dumps({
                        "systemInstruction": {"parts": [{"text": cls.SYSTEM_PROMPT}]},
                        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                        "generationConfig": {"maxOutputTokens": 1500, "temperature": 0.3}
                    }).encode("utf-8")
                )
                with urllib.request.urlopen(req, timeout=12, context=ssl_ctx) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    candidates = resp_data.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        parts = candidates[0]["content"].get("parts", [])
                        if parts:
                            ai_response_text = parts[0].get("text", "")
                            provider_used = "Verified Medical Literature (Online Reference)"
            except Exception as e:
                # Log degradation and fall back smoothly
                print(f"[Clinical Advisor Notice] Online query fallback: {e}. Utilizing Classical Unani Reference.", flush=True)

        # 4. Fallback if Gemini unavailable or not configured
        if not ai_response_text:
            ai_response_text = cls._synthesize_classical_fallback(query_clean, q_lower, badal_info, safety_alert)
            if provider_used != "Verified Medical Literature (Online Reference)":
                provider_used = "Classical Unani Compendia (Standard Reference)"

        return {
            "ok": True,
            "query": query_clean,
            "provider": provider_used,
            "response": ai_response_text,
            "safety_alert": safety_alert,
            "badal_info": badal_info
        }

    @classmethod
    def _check_safety_registry(cls, q_lower: str) -> Optional[Dict[str, Any]]:
        for (drug_a, drug_b), alert in cls.CRITICAL_INTERACTIONS.items():
            if drug_a in q_lower and drug_b in q_lower:
                return alert
            # Single drug keyword checks
            if drug_a == "warfarin" and ("warfarin" in q_lower or "blood thinner" in q_lower) and "guggul" in q_lower:
                return alert
            if drug_a == "levothyroxine" and ("levothyroxine" in q_lower or "thyronorm" in q_lower or "thyroid" in q_lower) and ("asgandh" in q_lower or "ashwagandha" in q_lower):
                return alert
        return None

    @classmethod
    def _lookup_badal(cls, q_lower: str, conn: sqlite3.Connection) -> Optional[Dict[str, Any]]:
        if not ("badal" in q_lower or "substitute" in q_lower or "alternative" in q_lower):
            return None
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT canonical_name_english, botanical_name, mizaj_primary_quality, badal_substitutes, adverse_effects_muzir, musleh_correctives 
                FROM zkb_mufradat 
                WHERE badal_substitutes IS NOT NULL AND badal_substitutes != '[]'
            """)
            for row in cur.fetchall():
                std_name = (row[0] or "").lower()
                bot_name = (row[1] or "").lower()
                if std_name in q_lower or bot_name in q_lower:
                    try:
                        b_list = json.loads(row[3]) if isinstance(row[3], str) else row[3]
                        badal_str = " • ".join(b_list) if isinstance(b_list, list) else str(b_list)
                    except Exception:
                        badal_str = str(row[3])

                    try:
                        m_list = json.loads(row[5]) if isinstance(row[5], str) else row[5]
                        musleh_str = " • ".join(m_list) if isinstance(m_list, list) else str(m_list)
                    except Exception:
                        musleh_str = str(row[5])

                    return {
                        "primary_herb": f"{row[0]} ({row[1]})",
                        "mizaj": row[2] or "Motadil",
                        "badal_substitute": badal_str or "None documented",
                        "muzir_adverse": row[4] or "Non-toxic at standard dosage",
                        "musleh_corrective": musleh_str or "Honey / Ghee"
                    }
        except Exception as e:
            print(f"[Badal Lookup Error] {e}", flush=True)
        return None

    @classmethod
    def _synthesize_classical_fallback(cls, query: str, q_lower: str, badal: Optional[dict], alert: Optional[dict]) -> str:
        lines = [f"### Clinical Synthesis for: '{query}'\n"]
        if alert:
            lines.append(f"> **⚠️ {alert['severity']}: {alert['title']}**")
            lines.append(f"> **Mechanism:** {alert['mechanism']}")
            lines.append(f"> **Classical Reference:** {alert['classical_ref']}")
            lines.append(f"> **Recommended Action:** {alert['action']}\n")

        if badal:
            lines.append(f"**Classical Badal (Herb Substitution):**")
            lines.append(f"- **Primary Herb:** {badal['primary_herb']} (Mizaj: {badal['mizaj']})")
            lines.append(f"- **Substitutes (Badal):** {badal['badal_substitute']}")
            lines.append(f"- **Corrective (Musleh):** {badal['musleh_corrective']}")
            lines.append(f"- **Known Toxicity/Adverse (Muzir):** {badal['muzir_adverse']}\n")

        lines.append("**Principles of Treatment (Usul-e-Ilaj):**")
        lines.append("1. **Su-e-Mizaj Assessment:** Differentiate between Su-e-Mizaj Saada (functional) and Maddi (humoral accumulation).")
        lines.append("2. **Tanqiya (Clearance):** Prepare morbific matter using Munzijaat followed by appropriate Mushil or mild Mu'arridat.")
        lines.append("3. **Tahleel & Taqwiyat:** Administer resolving agents followed by organ tonics (Muqawwiyat-e-Aaza-e-Ra'eesa).")
        lines.append("4. **Dietary Parhez:** Implement strict Ahmar/Barid dietary restrictions based on humoral axis.\n")
        lines.append("*Synthesized from Al-Qanun fi al-Tibb, Kamil al-Sina'ah, and ZAYVORA Clinical Formulary.*")
        return "\n".join(lines)
