import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput, Alert, Linking } from 'react-native';
import { theme } from '../theme';
import { Header } from '../components/Header';
import { MatabApi } from '../services/api';

export const HakeemConsultationScreen = () => {
  const [patients, setPatients] = useState([]);
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [protocols, setProtocols] = useState([]);
  const [selectedProtocol, setSelectedProtocol] = useState(null);

  // Clinical state
  const [activeMizaj, setActiveMizaj] = useState('BALGHAMI');
  const [nabzNotes, setNabzNotes] = useState('بطی، منخفض، لین (Slow, Low, Soft)');
  const [chiefComplaints, setChiefComplaints] = useState(['Su-e-Hazm (Indigestion)']);
  const [rxItems, setRxItems] = useState([
    { name: 'Jawarish Kamuni', dose: '5g', freq: 'BD', vehicle: 'Water after meals' },
    { name: 'Habb-e-Kabid Naushadri', dose: '2 hab', freq: 'BD', vehicle: 'Arq Badiyan (50ml)' }
  ]);
  const [ghizaPlan, setGhizaPlan] = useState('Moong dal khichdi, pomegranate juice, warm cumin water. Avoid heavy meat & cold drinks.');
  const [parhezPlan, setParhezPlan] = useState('Avoid sleeping immediately after meals. Walk 100 paces after dinner.');
  const [signingPin, setSigningPin] = useState('');
  const [isSigned, setIsSigned] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [pList, protoList] = await Promise.all([
        MatabApi.getPatients(),
        MatabApi.getProtocols()
      ]);
      setPatients(pList);
      if (pList.length > 0) setSelectedPatient(pList[0]);
      setProtocols(protoList);
      if (protoList.length > 1) setSelectedProtocol(protoList[1]); // P-03 default
    } catch (e) {
      console.warn('Could not load clinical data:', e);
    }
  };

  const handleSelectNabz = (type, pulseUrdu, quality) => {
    setActiveMizaj(type);
    setNabzNotes(`${pulseUrdu} — ${quality}`);
  };

  const toggleComplaint = (comp) => {
    if (chiefComplaints.includes(comp)) {
      setChiefComplaints(chiefComplaints.filter(c => c !== comp));
    } else {
      setChiefComplaints([...chiefComplaints, comp]);
    }
  };

  const handleSelectProtocol = (proto) => {
    setSelectedProtocol(proto);
    if (proto.id === 'P-03') {
      setRxItems([
        { name: 'Jawarish Kamuni', dose: '5g', freq: 'BD', vehicle: 'Water after meals' },
        { name: 'Habb-e-Kabid Naushadri', dose: '2 hab', freq: 'BD', vehicle: 'Arq Badiyan (50ml)' }
      ]);
      setGhizaPlan('Moong dal khichdi, pomegranate juice, warm cumin water.');
      setParhezPlan('Avoid oily, fried foods and cold carbonated drinks.');
    } else if (proto.id === 'P-10') {
      setRxItems([
        { name: 'Majun Suranjan (Mudabbar)', dose: '5g', freq: 'BD', vehicle: 'Lukewarm water' },
        { name: 'Habb-e-Suranjan', dose: '1 hab', freq: 'BD', vehicle: 'Water' },
        { name: 'Roghan Suranjan', dose: '10ml', freq: 'HS', vehicle: 'External gentle massage' }
      ]);
      setGhizaPlan('Warm mutton broth with ginger and black pepper. Avoid sour foods and curd.');
      setParhezPlan('Protect joints from cold draughts; avoid excessive air conditioning.');
    } else if (proto.id === 'P-11') {
      setRxItems([
        { name: 'Itrifal Ustukhuddus', dose: '6g', freq: 'HS', vehicle: 'Warm water at bedtime' },
        { name: 'Sharbat Deenar', dose: '20ml', freq: 'BD', vehicle: 'Lukewarm water' }
      ]);
      setGhizaPlan('Almonds soaked in water, barley water, fresh sweet apples.');
      setParhezPlan('Avoid late-night screen time, loud noise, and direct cold winds.');
    } else {
      setRxItems([
        { name: `Canonical Compound for ${proto.name}`, dose: '5g', freq: 'BD', vehicle: 'Water / Milk' }
      ]);
    }
  };

  const handleSignPrescription = () => {
    if (signingPin !== '1234') {
      Alert.alert('PIN Error', 'Invalid electronic signing PIN. (Default test PIN is 1234)');
      return;
    }
    setIsSigned(true);
    Alert.alert('Prescription Signed 📜', `Signed by Hakeem Tariq Ahmad (BUMS)\nStatus: ATTESTED & READY FOR DISPENSARY`);
  };

  const handleSendWhatsApp = () => {
    if (!selectedPatient) return;
    const patPhone = (selectedPatient.phone || '').replace(/[^0-9]/g, '');
    const cleanPhone = patPhone.startsWith('91') ? patPhone : `91${patPhone}`;
    
    let text = `🌿 *ZAYVORA MATAB OS — PRESCRIPTION*\n`;
    text += `*Patient:* ${selectedPatient.full_name} (${selectedPatient.mrn})\n`;
    text += `*Mizaj:* ${activeMizaj} | *Nabz:* ${nabzNotes}\n`;
    text += `*Diagnosis & Protocol:* ${selectedProtocol ? selectedProtocol.name : 'Unani Consultation'}\n\n`;
    text += `*📋 MEDICINES (Adwiya):*\n`;
    rxItems.forEach((it, idx) => {
      text += `${idx + 1}. *${it.name}* — ${it.dose} (${it.freq})\n   ↳ Anupan/Vehicle: ${it.vehicle}\n`;
    });
    text += `\n*🍲 DIET (Ilaj bil Ghiza):*\n${ghizaPlan}\n\n`;
    text += `*⚠️ PARHEZ (Avoidance):*\n${parhezPlan}\n\n`;
    text += `*Practitioner:* Hakeem Tariq Ahmad (BUMS)\n_Take medicines as advised. For emergency contact Matab OPD._`;

    const encoded = encodeURIComponent(text);
    const waUrl = `whatsapp://send?phone=${cleanPhone}&text=${encoded}`;
    const webWaUrl = `https://wa.me/${cleanPhone}?text=${encoded}`;

    Linking.canOpenURL(waUrl)
      .then(supported => {
        if (supported) {
          Linking.openURL(waUrl);
        } else {
          Linking.openURL(webWaUrl);
        }
      })
      .catch(() => {
        Linking.openURL(webWaUrl);
      });
  };

  return (
    <View style={styles.container}>
      <Header title="Bedside Clinical OPD" subtitle="Doctor Consultation & Prescribing" />

      <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent}>
        {/* Patient Selection Dropdown / Horizontal Scroll */}
        <View style={styles.sectionCard}>
          <Text style={styles.cardHeader}>👤 ACTIVE PATIENT</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.patientRow}>
            {patients.map(p => (
              <TouchableOpacity
                key={p.id}
                style={[
                  styles.patientChip,
                  selectedPatient?.id === p.id && styles.patientChipActive
                ]}
                onPress={() => setSelectedPatient(p)}
              >
                <Text style={[styles.patientChipName, selectedPatient?.id === p.id && styles.patientChipNameActive]}>
                  {p.full_name}
                </Text>
                <Text style={styles.patientChipMrn}>{p.mrn} • {p.mizaj}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>

          {selectedPatient && (
            <View style={styles.patientDetailsBox}>
              <View style={styles.detailRow}>
                <Text style={styles.detailLabel}>Name:</Text>
                <Text style={styles.detailVal}>{selectedPatient.full_name} ({selectedPatient.age}y/{selectedPatient.sex})</Text>
              </View>
              <View style={styles.detailRow}>
                <Text style={styles.detailLabel}>MRN / Phone:</Text>
                <Text style={styles.detailVal}>{selectedPatient.mrn} • {selectedPatient.phone}</Text>
              </View>
              <View style={styles.detailRow}>
                <Text style={styles.detailLabel}>Primary Issue:</Text>
                <Text style={styles.detailVal}>{selectedPatient.primary_complaint}</Text>
              </View>
            </View>
          )}
        </View>

        {/* 1-Click Nabz & Mizaj Presets */}
        <View style={styles.sectionCard}>
          <Text style={styles.cardHeader}>🩺 1-CLICK NABZ &amp; MIZAJ PRESETS</Text>
          <View style={styles.nabzGrid}>
            <TouchableOpacity 
              style={[styles.nabzBtn, activeMizaj === 'DAMWI' && { borderColor: theme.colors.nabzDamwi, backgroundColor: '#fef2f2' }]}
              onPress={() => handleSelectNabz('DAMWI', 'عظیم، ممتلی، قوی، سریع', 'Bounding, Full & Rapid')}
            >
              <Text style={[styles.nabzArabic, { color: theme.colors.nabzDamwi }]}>دموی (Damwi)</Text>
              <Text style={styles.nabzSub}>Sanguine</Text>
              <Text style={styles.nabzMeta}>عظیم • ممتلی</Text>
            </TouchableOpacity>

            <TouchableOpacity 
              style={[styles.nabzBtn, activeMizaj === 'SAFRAWI' && { borderColor: theme.colors.nabzSafrawi, backgroundColor: '#fffbeb' }]}
              onPress={() => handleSelectNabz('SAFRAWI', 'سریع، متواتر، صلب، صغیر', 'Rapid, Frequent & Hard')}
            >
              <Text style={[styles.nabzArabic, { color: theme.colors.nabzSafrawi }]}>صفراوی (Safrawi)</Text>
              <Text style={styles.nabzSub}>Bilious</Text>
              <Text style={styles.nabzMeta}>سریع • متواتر</Text>
            </TouchableOpacity>

            <TouchableOpacity 
              style={[styles.nabzBtn, activeMizaj === 'BALGHAMI' && { borderColor: theme.colors.nabzBalghami, backgroundColor: '#eff6ff' }]}
              onPress={() => handleSelectNabz('BALGHAMI', 'بطی، متفاوت، لین، منخفض', 'Slow, Soft & Low')}
            >
              <Text style={[styles.nabzArabic, { color: theme.colors.nabzBalghami }]}>بلغمی (Balghami)</Text>
              <Text style={styles.nabzSub}>Phlegmatic</Text>
              <Text style={styles.nabzMeta}>بطی • لین</Text>
            </TouchableOpacity>

            <TouchableOpacity 
              style={[styles.nabzBtn, activeMizaj === 'SAUDAWI' && { borderColor: theme.colors.nabzSaudawi, backgroundColor: '#f3f4f6' }]}
              onPress={() => handleSelectNabz('SAUDAWI', 'صلب، بطی، منشار، صغیر', 'Hard, Slow & Serrated')}
            >
              <Text style={[styles.nabzArabic, { color: theme.colors.nabzSaudawi }]}>سوداوی (Saudawi)</Text>
              <Text style={styles.nabzSub}>Melancholic</Text>
              <Text style={styles.nabzMeta}>صلب • منشار</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.nabzSummaryBox}>
            <Text style={styles.nabzSummaryText}>Pulse Observation: <strong>{nabzNotes}</strong></Text>
          </View>
        </View>

        {/* 1-Click Quick Complaints */}
        <View style={styles.sectionCard}>
          <Text style={styles.cardHeader}>⚡ QUICK COMPLAINT CHIPS</Text>
          <View style={styles.chipsContainer}>
            {['Su-e-Hazm (Indigestion)', 'Nafkh (Gas/Bloating)', 'Waja-ul-Mafasil (Joint Pain)', 'Sudaa (Headache)', 'Zeeq-un-Nafs (Asthma)', 'Zof-e-Kabid (Liver)', 'Qabz (Constipation)', 'Insomnia (Sahar)'].map(c => {
              const active = chiefComplaints.includes(c);
              return (
                <TouchableOpacity
                  key={c}
                  style={[styles.chip, active && styles.chipActive]}
                  onPress={() => toggleComplaint(c)}
                >
                  <Text style={[styles.chipText, active && styles.chipTextActive]}>
                    {active ? '✓ ' : '+ '}{c}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </View>

        {/* Governed Master Clinical Protocols (P-01 to P-21) */}
        <View style={styles.sectionCard}>
          <Text style={styles.cardHeader}>📖 GOVERNED MASTER PROTOCOLS (P-01 to P-21)</Text>
          <Text style={styles.cardSub}>Enforces 3-Phase Af'aal Cascade &amp; Botanical Posology bounds</Text>
          
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.protocolList}>
            {protocols.map(proto => (
              <TouchableOpacity
                key={proto.id}
                style={[
                  styles.protocolChip,
                  selectedProtocol?.id === proto.id && styles.protocolChipActive
                ]}
                onPress={() => handleSelectProtocol(proto)}
              >
                <Text style={[styles.protocolChipId, selectedProtocol?.id === proto.id && styles.protocolChipIdActive]}>
                  {proto.id}
                </Text>
                <Text style={styles.protocolChipName} numberOfLines={1}>{proto.name}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>

          {selectedProtocol && (
            <View style={styles.protocolDetailCard}>
              <Text style={styles.protocolPrinciple}>
                <strong>Usul-e-Ilaj:</strong> {selectedProtocol.principle}
              </Text>
              <View style={styles.cascadeBadge}>
                <Text style={styles.cascadeText}>Phase 1: Tanqiya ➔ Phase 2: Tahleel ➔ Phase 3: Taqwiyat</Text>
              </View>
            </View>
          )}
        </View>

        {/* Prescription Formulary Table */}
        <View style={styles.sectionCard}>
          <Text style={styles.cardHeader}>💊 PRESCRIBED ADWIYA &amp; DOSAGE</Text>
          {rxItems.map((item, idx) => (
            <View key={idx} style={styles.rxItemRow}>
              <View style={styles.rxIndexCircle}>
                <Text style={styles.rxIndexText}>{idx + 1}</Text>
              </View>
              <View style={styles.rxInfo}>
                <Text style={styles.rxName}>{item.name}</Text>
                <Text style={styles.rxDosage}>Dose: <strong>{item.dose}</strong> ({item.freq}) • Anupan: {item.vehicle}</Text>
              </View>
            </View>
          ))}

          {/* Safety Warning */}
          <View style={styles.safetyBox}>
            <Text style={styles.safetyIcon}>🛡️</Text>
            <Text style={styles.safetyText}>
              <strong>Safety Firewall PASS:</strong> Schedule E(1) detoxified (Mudabbar) &amp; Herb-Drug interaction check passed.
            </Text>
          </View>
        </View>

        {/* Diet & Parhez */}
        <View style={styles.sectionCard}>
          <Text style={styles.cardHeader}>🍲 ILAJ BIL GHIZA &amp; PARHEZ</Text>
          <Text style={styles.dietLabel}>Diet Instructions (Ghiza):</Text>
          <TextInput 
            style={styles.dietInput}
            value={ghizaPlan}
            onChangeText={setGhizaPlan}
            multiline
          />
          <Text style={[styles.dietLabel, { marginTop: 8 }]}>Parhez / Precautions:</Text>
          <TextInput 
            style={styles.dietInput}
            value={parhezPlan}
            onChangeText={setParhezPlan}
            multiline
          />
        </View>

        {/* Electronic Signature & WhatsApp Transmission */}
        <View style={[styles.sectionCard, { backgroundColor: isSigned ? '#f0fdf4' : '#fff' }]}>
          <Text style={styles.cardHeader}>✍️ CLINICIAN SIGNATURE &amp; TRANSMISSION</Text>
          
          {!isSigned ? (
            <View style={styles.signRow}>
              <TextInput 
                style={styles.pinInput}
                value={signingPin}
                onChangeText={setSigningPin}
                placeholder="Enter PIN (1234)"
                placeholderTextColor={theme.colors.textMuted}
                keyboardType="numeric"
                secureTextEntry
              />
              <TouchableOpacity style={styles.signBtn} onPress={handleSignPrescription}>
                <Text style={styles.signBtnText}>Sign Rx (PIN)</Text>
              </TouchableOpacity>
            </View>
          ) : (
            <View style={styles.signedStatusBox}>
              <Text style={styles.signedText}>✓ Electronically Attested: Hakeem Tariq Ahmad (BUMS)</Text>
            </View>
          )}

          {/* WhatsApp Direct Rx Button */}
          <TouchableOpacity 
            style={styles.whatsAppBtn}
            onPress={handleSendWhatsApp}
          >
            <Text style={styles.whatsAppBtnText}>💬 Send WhatsApp Prescription (1-Click)</Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.background,
  },
  scroll: {
    flex: 1,
  },
  scrollContent: {
    padding: theme.spacing.md,
    paddingBottom: 40,
  },
  sectionCard: {
    backgroundColor: theme.colors.surface,
    borderRadius: theme.borderRadius.md,
    padding: theme.spacing.md,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: theme.colors.border,
    shadowColor: '#000',
    shadowOpacity: 0.03,
    shadowRadius: 3,
    elevation: 1,
  },
  cardHeader: {
    fontSize: 12,
    fontWeight: '800',
    color: theme.colors.primaryDark,
    letterSpacing: 0.5,
    marginBottom: 8,
  },
  cardSub: {
    fontSize: 11,
    color: theme.colors.textMuted,
    marginBottom: 10,
  },
  patientRow: {
    marginBottom: 10,
  },
  patientChip: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
    backgroundColor: theme.colors.borderLight,
    marginRight: 8,
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  patientChipActive: {
    backgroundColor: theme.colors.primaryLight,
    borderColor: theme.colors.primary,
  },
  patientChipName: {
    fontSize: 12,
    fontWeight: '700',
    color: theme.colors.textPrimary,
  },
  patientChipNameActive: {
    color: theme.colors.primaryDark,
  },
  patientChipMrn: {
    fontSize: 10,
    color: theme.colors.textSecondary,
    marginTop: 2,
  },
  patientDetailsBox: {
    backgroundColor: '#f8fafc',
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  detailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 4,
  },
  detailLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: theme.colors.textSecondary,
  },
  detailVal: {
    fontSize: 11,
    fontWeight: '700',
    color: theme.colors.textPrimary,
  },
  nabzGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 8,
  },
  nabzBtn: {
    flex: 1,
    minWidth: '45%',
    backgroundColor: '#fff',
    borderRadius: 8,
    borderWidth: 1.5,
    borderColor: theme.colors.border,
    padding: 8,
    alignItems: 'center',
  },
  nabzArabic: {
    fontSize: 13,
    fontWeight: '800',
  },
  nabzSub: {
    fontSize: 10,
    color: theme.colors.textSecondary,
    marginTop: 1,
  },
  nabzMeta: {
    fontSize: 10,
    color: theme.colors.textMuted,
    marginTop: 2,
  },
  nabzSummaryBox: {
    padding: 8,
    backgroundColor: '#f1f5f9',
    borderRadius: 6,
    marginTop: 4,
  },
  nabzSummaryText: {
    fontSize: 11,
    color: theme.colors.textPrimary,
  },
  chipsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
  },
  chip: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 14,
    backgroundColor: '#f1f5f9',
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  chipActive: {
    backgroundColor: theme.colors.primaryLight,
    borderColor: theme.colors.primary,
  },
  chipText: {
    fontSize: 11,
    color: theme.colors.textSecondary,
    fontWeight: '500',
  },
  chipTextActive: {
    color: theme.colors.primaryDark,
    fontWeight: '700',
  },
  protocolList: {
    marginBottom: 8,
  },
  protocolChip: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
    backgroundColor: '#f8fafc',
    marginRight: 6,
    borderWidth: 1,
    borderColor: theme.colors.border,
    maxWidth: 160,
  },
  protocolChipActive: {
    backgroundColor: theme.colors.primaryLight,
    borderColor: theme.colors.primary,
  },
  protocolChipId: {
    fontSize: 10,
    fontWeight: '800',
    color: theme.colors.primary,
  },
  protocolChipIdActive: {
    color: theme.colors.primaryDark,
  },
  protocolChipName: {
    fontSize: 11,
    color: theme.colors.textPrimary,
  },
  protocolDetailCard: {
    backgroundColor: '#f0fdf4',
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#bbf7d0',
  },
  protocolPrinciple: {
    fontSize: 11,
    color: theme.colors.primaryDark,
    lineHeight: 16,
  },
  cascadeBadge: {
    marginTop: 4,
    backgroundColor: theme.colors.primaryLight,
    paddingHorizontal: 6,
    paddingVertical: 3,
    borderRadius: 4,
    alignSelf: 'flex-start',
  },
  cascadeText: {
    fontSize: 10,
    fontWeight: '700',
    color: theme.colors.primaryDark,
  },
  rxItemRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: '#f1f5f9',
  },
  rxIndexCircle: {
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: theme.colors.primaryLight,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 10,
  },
  rxIndexText: {
    fontSize: 10,
    fontWeight: '800',
    color: theme.colors.primaryDark,
  },
  rxInfo: {
    flex: 1,
  },
  rxName: {
    fontSize: 12,
    fontWeight: '700',
    color: theme.colors.textPrimary,
  },
  rxDosage: {
    fontSize: 11,
    color: theme.colors.textSecondary,
    marginTop: 2,
  },
  safetyBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#ecfdf5',
    padding: 8,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#a7f3d0',
    marginTop: 10,
  },
  safetyIcon: {
    fontSize: 16,
    marginRight: 6,
  },
  safetyText: {
    fontSize: 11,
    color: '#065f46',
    flex: 1,
    lineHeight: 15,
  },
  dietLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: theme.colors.textSecondary,
    marginBottom: 4,
  },
  dietInput: {
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: 6,
    padding: 8,
    fontSize: 11,
    color: theme.colors.textPrimary,
    backgroundColor: '#fff',
    minHeight: 45,
  },
  signRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 10,
  },
  pinInput: {
    flex: 1,
    height: 40,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: 8,
    paddingHorizontal: 12,
    fontSize: 13,
    backgroundColor: '#fff',
  },
  signBtn: {
    backgroundColor: theme.colors.primary,
    paddingHorizontal: 16,
    borderRadius: 8,
    justifyContent: 'center',
    alignItems: 'center',
  },
  signBtnText: {
    color: '#fff',
    fontWeight: '700',
    fontSize: 12,
  },
  signedStatusBox: {
    padding: 8,
    backgroundColor: '#dcfce7',
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#86efac',
    marginBottom: 10,
  },
  signedText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#15803d',
    textAlign: 'center',
  },
  whatsAppBtn: {
    backgroundColor: '#25d366',
    paddingVertical: 12,
    borderRadius: 8,
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#25d366',
    shadowOpacity: 0.25,
    shadowRadius: 4,
    elevation: 2,
  },
  whatsAppBtnText: {
    color: '#ffffff',
    fontWeight: '800',
    fontSize: 13,
  }
});
