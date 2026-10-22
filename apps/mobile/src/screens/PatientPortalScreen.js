import React, { useState } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Linking, Alert } from 'react-native';
import { theme } from '../theme';
import { Header } from '../components/Header';
import { useAuth } from '../context/AuthContext';

export const PatientPortalScreen = () => {
  const { selectedPatient } = useAuth();
  const [activeSegment, setActiveSegment] = useState('RX'); // 'RX' | 'DIET' | 'APPOINTMENTS'

  const patient = selectedPatient || {
    full_name: 'Mohammad Zubair',
    mrn: 'ZMD-2026-001',
    mizaj: 'Balghami (Phlegmatic)',
    prescriptions: [
      {
        id: 'rx-001',
        date: '2026-10-22',
        protocol: 'P-03: Dyspepsia & IBS Gastric Cascade',
        usul: 'Tadeel-e-Mizaj-e-Meda wa Taqwiyat-e-Hazm',
        items: [
          { name: 'Jawarish Kamuni', dose: '5g Twice Daily', vehicle: 'Water after meals', time: 'Morning & Evening after meal' },
          { name: 'Habb-e-Kabid Naushadri', dose: '2 Tablets Twice Daily', vehicle: 'Arq Badiyan (50ml)', time: 'Before meals' }
        ],
        diet: 'Moong dal khichdi, pomegranate juice, warm cumin water. Avoid oily, spicy, fried foods and cold drinks.',
        parhez: 'Do not sleep immediately after eating. Walk 100 paces after dinner. Avoid drinking cold water during meals.'
      }
    ]
  };

  const rx = patient.prescriptions?.[0];

  const handleContactDoctor = () => {
    const text = encodeURIComponent(`Assalamu Alaikum Dr. Tariq Ahmad, I am ${patient.full_name} (MRN: ${patient.mrn}). I have a query regarding my prescription.`);
    Linking.openURL(`https://wa.me/919800000001?text=${text}`);
  };

  const handleCallClinic = () => {
    Linking.openURL('tel:+919800000001');
  };

  return (
    <View style={styles.container}>
      <Header title="My Health Companion" subtitle="Active Prescriptions &amp; Diet Plan" />

      {/* Patient Profile Banner */}
      <View style={styles.profileCard}>
        <View style={styles.avatarCircle}>
          <Text style={styles.avatarText}>{patient.full_name?.charAt(0) || 'P'}</Text>
        </View>
        <View style={styles.profileText}>
          <Text style={styles.patientName}>{patient.full_name}</Text>
          <Text style={styles.mrnText}>MRN: <strong>{patient.mrn}</strong></Text>
          <View style={styles.mizajBadge}>
            <Text style={styles.mizajText}>⚖️ Mizaj: {patient.mizaj || 'Balghami'}</Text>
          </View>
        </View>
      </View>

      {/* Navigation Segments */}
      <View style={styles.segmentContainer}>
        <TouchableOpacity 
          style={[styles.segmentBtn, activeSegment === 'RX' && styles.segmentBtnActive]}
          onPress={() => setActiveSegment('RX')}
        >
          <Text style={[styles.segmentText, activeSegment === 'RX' && styles.segmentTextActive]}>💊 Prescriptions</Text>
        </TouchableOpacity>
        <TouchableOpacity 
          style={[styles.segmentBtn, activeSegment === 'DIET' && styles.segmentBtnActive]}
          onPress={() => setActiveSegment('DIET')}
        >
          <Text style={[styles.segmentText, activeSegment === 'DIET' && styles.segmentTextActive]}>🍲 Diet &amp; Parhez</Text>
        </TouchableOpacity>
        <TouchableOpacity 
          style={[styles.segmentBtn, activeSegment === 'APPOINTMENTS' && styles.segmentBtnActive]}
          onPress={() => setActiveSegment('APPOINTMENTS')}
        >
          <Text style={[styles.segmentText, activeSegment === 'APPOINTMENTS' && styles.segmentTextActive]}>📅 Next Visit</Text>
        </TouchableOpacity>
      </View>

      <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent}>
        {activeSegment === 'RX' && (
          <View style={styles.card}>
            <View style={styles.rxHeaderRow}>
              <Text style={styles.cardHeader}>CURRENT PRESCRIPTION</Text>
              <Text style={styles.rxDate}>{rx?.date || 'Today'}</Text>
            </View>
            <Text style={styles.protocolName}>{rx?.protocol}</Text>
            <Text style={styles.usulText}>Usul-e-Ilaj: {rx?.usul}</Text>

            <View style={styles.divider} />

            <Text style={styles.itemsTitle}>MEDICINES &amp; DOSAGE TIMINGS:</Text>
            {rx?.items?.map((it, idx) => (
              <View key={idx} style={styles.medBox}>
                <View style={styles.medTopRow}>
                  <Text style={styles.medName}>🌿 {it.name}</Text>
                  <View style={styles.dosePill}>
                    <Text style={styles.dosePillText}>{it.dose}</Text>
                  </View>
                </View>
                <Text style={styles.medVehicle}>↳ Take with: <strong>{it.vehicle}</strong></Text>
                <Text style={styles.medTime}>⏰ Timing: {it.time}</Text>
              </View>
            ))}

            <View style={styles.verifiedSignBox}>
              <Text style={styles.verifiedSignText}>✓ Signed by: Hakeem Tariq Ahmad (BUMS)</Text>
              <Text style={styles.verifiedClinic}>ZAYVORA Matab Dawakhana • Delhi</Text>
            </View>
          </View>
        )}

        {activeSegment === 'DIET' && (
          <View style={styles.card}>
            <Text style={styles.cardHeader}>🍲 ILAJ BIL GHIZA (DIET PLAN)</Text>
            <Text style={styles.dietDesc}>
              In Unani medicine, proper food acts as medicine to restore humeral balance.
            </Text>

            <View style={styles.dietBox}>
              <Text style={styles.dietSectionHeader}>✅ Recommended Foods:</Text>
              <Text style={styles.dietBody}>{rx?.diet || 'Light vegetable khichdi, pomegranate, barley water.'}</Text>
            </View>

            <View style={[styles.dietBox, { backgroundColor: '#fef2f2', borderColor: '#fca5a5' }]}>
              <Text style={[styles.dietSectionHeader, { color: '#b91c1c' }]}>⛔ Parhez (Strictly Avoid):</Text>
              <Text style={[styles.dietBody, { color: '#991b1b' }]}>{rx?.parhez || 'Oily, sour, excessively spiced foods.'}</Text>
            </View>
          </View>
        )}

        {activeSegment === 'APPOINTMENTS' && (
          <View style={styles.card}>
            <Text style={styles.cardHeader}>📅 FOLLOW-UP VISIT &amp; BOOKING</Text>
            <View style={styles.apptBox}>
              <Text style={styles.apptDate}>Next Review: In 14 Days</Text>
              <Text style={styles.apprDoctor}>Practitioner: Hakeem Tariq Ahmad</Text>
              <Text style={styles.apptLocation}>Facility: Central Matab OPD • Room 1</Text>
            </View>

            <TouchableOpacity 
              style={styles.bookVisitBtn}
              onPress={() => Alert.alert('Request Sent', 'Your follow-up appointment request has been submitted to Front Desk reception.')}
            >
              <Text style={styles.bookVisitText}>Request Appointment Slot</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Quick Contact Doctor & Clinic */}
        <View style={styles.contactRow}>
          <TouchableOpacity style={styles.waContactBtn} onPress={handleContactDoctor}>
            <Text style={styles.waContactText}>💬 WhatsApp Hakeem</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.callContactBtn} onPress={handleCallClinic}>
            <Text style={styles.callContactText}>📞 Call Clinic</Text>
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
  profileCard: {
    backgroundColor: '#fff',
    flexDirection: 'row',
    alignItems: 'center',
    padding: theme.spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.border,
  },
  avatarCircle: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: theme.colors.accentLight,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
    borderWidth: 2,
    borderColor: theme.colors.accent,
  },
  avatarText: {
    fontSize: 20,
    fontWeight: '800',
    color: theme.colors.accent,
  },
  profileText: {
    flex: 1,
  },
  patientName: {
    fontSize: 16,
    fontWeight: '800',
    color: theme.colors.textPrimary,
  },
  mrnText: {
    fontSize: 11,
    color: theme.colors.textSecondary,
    marginTop: 1,
  },
  mizajBadge: {
    backgroundColor: theme.colors.primaryLight,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 6,
    alignSelf: 'flex-start',
    marginTop: 4,
  },
  mizajText: {
    fontSize: 10,
    fontWeight: '700',
    color: theme.colors.primaryDark,
  },
  segmentContainer: {
    flexDirection: 'row',
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.border,
  },
  segmentBtn: {
    flex: 1,
    paddingVertical: 10,
    alignItems: 'center',
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
  },
  segmentBtnActive: {
    borderBottomColor: theme.colors.primary,
  },
  segmentText: {
    fontSize: 11,
    fontWeight: '600',
    color: theme.colors.textSecondary,
  },
  segmentTextActive: {
    color: theme.colors.primaryDark,
    fontWeight: '800',
  },
  scroll: {
    flex: 1,
  },
  scrollContent: {
    padding: theme.spacing.md,
    paddingBottom: 30,
  },
  card: {
    backgroundColor: '#fff',
    borderRadius: theme.borderRadius.md,
    padding: theme.spacing.md,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  rxHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  cardHeader: {
    fontSize: 12,
    fontWeight: '800',
    color: theme.colors.primaryDark,
    letterSpacing: 0.5,
  },
  rxDate: {
    fontSize: 11,
    color: theme.colors.textMuted,
  },
  protocolName: {
    fontSize: 13,
    fontWeight: '700',
    color: theme.colors.textPrimary,
    marginTop: 6,
  },
  usulText: {
    fontSize: 11,
    color: theme.colors.textSecondary,
    marginTop: 2,
  },
  divider: {
    height: 1,
    backgroundColor: '#f1f5f9',
    marginVertical: 10,
  },
  itemsTitle: {
    fontSize: 11,
    fontWeight: '800',
    color: theme.colors.textSecondary,
    marginBottom: 8,
  },
  medBox: {
    backgroundColor: '#f8fafc',
    padding: 10,
    borderRadius: 8,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  medTopRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  medName: {
    fontSize: 13,
    fontWeight: '700',
    color: theme.colors.textPrimary,
  },
  dosePill: {
    backgroundColor: theme.colors.primaryLight,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 6,
  },
  dosePillText: {
    fontSize: 10,
    fontWeight: '700',
    color: theme.colors.primaryDark,
  },
  medVehicle: {
    fontSize: 11,
    color: theme.colors.textSecondary,
    marginTop: 4,
  },
  medTime: {
    fontSize: 11,
    color: '#0369a1',
    fontWeight: '600',
    marginTop: 2,
  },
  verifiedSignBox: {
    marginTop: 10,
    padding: 8,
    backgroundColor: '#ecfdf5',
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#a7f3d0',
  },
  verifiedSignText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#065f46',
  },
  verifiedClinic: {
    fontSize: 10,
    color: '#047857',
    marginTop: 1,
  },
  dietDesc: {
    fontSize: 12,
    color: theme.colors.textSecondary,
    lineHeight: 16,
    marginVertical: 6,
  },
  dietBox: {
    backgroundColor: '#f0fdf4',
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#bbf7d0',
    marginBottom: 10,
  },
  dietSectionHeader: {
    fontSize: 12,
    fontWeight: '700',
    color: '#166534',
    marginBottom: 4,
  },
  dietBody: {
    fontSize: 12,
    color: '#14532d',
    lineHeight: 17,
  },
  apptBox: {
    backgroundColor: '#f8fafc',
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: theme.colors.border,
    marginBottom: 12,
  },
  apptDate: {
    fontSize: 14,
    fontWeight: '800',
    color: theme.colors.primary,
  },
  apprDoctor: {
    fontSize: 12,
    color: theme.colors.textPrimary,
    marginTop: 3,
  },
  apptLocation: {
    fontSize: 11,
    color: theme.colors.textSecondary,
    marginTop: 2,
  },
  bookVisitBtn: {
    backgroundColor: theme.colors.primary,
    paddingVertical: 10,
    borderRadius: 8,
    alignItems: 'center',
  },
  bookVisitText: {
    color: '#fff',
    fontWeight: '700',
    fontSize: 12,
  },
  contactRow: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 4,
  },
  waContactBtn: {
    flex: 1,
    backgroundColor: '#25d366',
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  waContactText: {
    color: '#fff',
    fontWeight: '700',
    fontSize: 12,
  },
  callContactBtn: {
    flex: 1,
    backgroundColor: theme.colors.primary,
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  callContactText: {
    color: '#fff',
    fontWeight: '700',
    fontSize: 12,
  }
});
