import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput, Alert } from 'react-native';
import { theme } from '../theme';
import { Header } from '../components/Header';
import { MatabApi } from '../services/api';

export const StaffQueueScreen = () => {
  const [activeTab, setActiveTab] = useState('QUEUE'); // 'QUEUE' | 'DISPENSARY'
  const [tokens, setTokens] = useState([]);
  const [newPatientName, setNewPatientName] = useState('');
  const [newPatientPhone, setNewPatientPhone] = useState('');
  const [isUrgent, setIsUrgent] = useState(false);

  useEffect(() => {
    loadQueue();
  }, []);

  const loadQueue = async () => {
    try {
      const q = await MatabApi.getQueue();
      setTokens(q);
    } catch (e) {
      console.warn('Queue load error:', e);
    }
  };

  const handleIssueToken = async () => {
    if (!newPatientName.trim()) {
      Alert.alert('Required', 'Please enter patient name.');
      return;
    }

    const nextNum = tokens.length + 1;
    const newToken = {
      token: `T-0${nextNum}`,
      patient_name: newPatientName,
      mrn: `ZMD-2026-${String(nextNum).padStart(3, '0')}`,
      status: 'WAITING',
      priority: isUrgent ? 'URGENT' : 'NORMAL',
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setTokens([newToken, ...tokens]);
    setNewPatientName('');
    setNewPatientPhone('');
    setIsUrgent(false);
    Alert.alert('Token Issued 🎟️', `Token: ${newToken.token}\nPatient: ${newToken.patient_name}\nStatus: WAITING FOR DOCTOR`);
  };

  const handleTransitionStatus = (tokenStr, nextStatus) => {
    setTokens(tokens.map(t => {
      if (t.token === tokenStr) {
        return { ...t, status: nextStatus };
      }
      return t;
    }));
  };

  return (
    <View style={styles.container}>
      <Header title="Front Desk &amp; Dispensary" subtitle="Queue Management &amp; FEFO Stock" />

      {/* Tab Switcher */}
      <View style={styles.tabContainer}>
        <TouchableOpacity 
          style={[styles.tabBtn, activeTab === 'QUEUE' && styles.tabBtnActive]}
          onPress={() => setActiveTab('QUEUE')}
        >
          <Text style={[styles.tabText, activeTab === 'QUEUE' && styles.tabTextActive]}>
            🎟️ OPD Token Queue ({tokens.filter(t => t.status === 'WAITING').length} Waiting)
          </Text>
        </TouchableOpacity>
        <TouchableOpacity 
          style={[styles.tabBtn, activeTab === 'DISPENSARY' && styles.tabBtnActive]}
          onPress={() => setActiveTab('DISPENSARY')}
        >
          <Text style={[styles.tabText, activeTab === 'DISPENSARY' && styles.tabTextActive]}>
            💊 Dispensary &amp; Stock
          </Text>
        </TouchableOpacity>
      </View>

      <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent}>
        {activeTab === 'QUEUE' ? (
          <>
            {/* Quick Walk-in Registration */}
            <View style={styles.card}>
              <Text style={styles.cardHeader}>⚡ FAST WALK-IN TOKEN GENERATOR</Text>
              <TextInput 
                style={styles.input}
                value={newPatientName}
                onChangeText={setNewPatientName}
                placeholder="Patient Full Name"
                placeholderTextColor={theme.colors.textMuted}
              />
              <TextInput 
                style={styles.input}
                value={newPatientPhone}
                onChangeText={setNewPatientPhone}
                placeholder="Mobile Number (for WhatsApp Rx)"
                placeholderTextColor={theme.colors.textMuted}
                keyboardType="phone-pad"
              />
              <View style={styles.urgentRow}>
                <TouchableOpacity 
                  style={[styles.urgentToggle, isUrgent && styles.urgentToggleActive]}
                  onPress={() => setIsUrgent(!isUrgent)}
                >
                  <Text style={[styles.urgentToggleText, isUrgent && styles.urgentToggleTextActive]}>
                    {isUrgent ? '🚨 URGENT / EMERGENCY' : '○ Normal Priority'}
                  </Text>
                </TouchableOpacity>

                <TouchableOpacity style={styles.issueBtn} onPress={handleIssueToken}>
                  <Text style={styles.issueBtnText}>Issue Token ➔</Text>
                </TouchableOpacity>
              </View>
            </View>

            {/* Live Queue Cards */}
            <View style={styles.card}>
              <Text style={styles.cardHeader}>📋 TODAY'S OPD QUEUE</Text>
              {tokens.map((item, idx) => {
                let badgeBg = '#fef3c7';
                let badgeColor = '#92400e';
                if (item.status === 'IN_CONSULTATION') {
                  badgeBg = theme.colors.primaryLight;
                  badgeColor = theme.colors.primaryDark;
                } else if (item.status === 'DISPENSED') {
                  badgeBg = theme.colors.successBg;
                  badgeColor = theme.colors.success;
                }

                return (
                  <View key={idx} style={styles.queueItem}>
                    <View style={styles.tokenCircle}>
                      <Text style={styles.tokenText}>{item.token}</Text>
                    </View>
                    <View style={styles.queueInfo}>
                      <View style={styles.queueHeaderRow}>
                        <Text style={styles.patientName}>{item.patient_name}</Text>
                        <Text style={styles.queueTime}>{item.time}</Text>
                      </View>
                      <Text style={styles.patientSub}>{item.mrn} {item.priority === 'URGENT' && '• 🚨 Urgent'}</Text>
                      <View style={styles.statusActionRow}>
                        <View style={[styles.statusBadge, { backgroundColor: badgeBg }]}>
                          <Text style={[styles.statusBadgeText, { color: badgeColor }]}>{item.status}</Text>
                        </View>
                        {item.status === 'WAITING' && (
                          <TouchableOpacity 
                            style={styles.actionCallBtn}
                            onPress={() => handleTransitionStatus(item.token, 'IN_CONSULTATION')}
                          >
                            <Text style={styles.actionCallText}>Call to Doctor ➔</Text>
                          </TouchableOpacity>
                        )}
                        {item.status === 'IN_CONSULTATION' && (
                          <TouchableOpacity 
                            style={styles.actionDispenseBtn}
                            onPress={() => handleTransitionStatus(item.token, 'DISPENSED')}
                          >
                            <Text style={styles.actionDispenseText}>Mark Dispensed ✓</Text>
                          </TouchableOpacity>
                        )}
                      </View>
                    </View>
                  </View>
                );
              })}
            </View>
          </>
        ) : (
          /* Dispensary & FEFO stock view */
          <View style={styles.card}>
            <Text style={styles.cardHeader}>📦 DISPENSARY FEFO STOCK &amp; BATCHES</Text>
            <Text style={styles.cardSub}>First-Expiry-First-Out dispensing verification</Text>
            
            {[
              { name: 'Jawarish Kamuni (Classical)', batch: 'BAT-2026-08', stock: '2,400 g', exp: '2027-08', status: 'IN_STOCK' },
              { name: 'Habb-e-Kabid Naushadri', batch: 'BAT-2026-11', stock: '1,200 hab', exp: '2027-11', status: 'IN_STOCK' },
              { name: 'Majun Suranjan (Mudabbar)', batch: 'BAT-2026-04', stock: '850 g', exp: '2026-12', status: 'LOW_STOCK' },
              { name: 'Itrifal Ustukhuddus', batch: 'BAT-2026-09', stock: '1,500 g', exp: '2027-09', status: 'IN_STOCK' },
              { name: 'Sharbat Deenar', batch: 'BAT-2026-02', stock: '18 bottles', exp: '2027-02', status: 'IN_STOCK' },
            ].map((st, i) => (
              <View key={i} style={styles.stockItem}>
                <View>
                  <Text style={styles.stockName}>{st.name}</Text>
                  <Text style={styles.stockMeta}>Batch: <strong>{st.batch}</strong> • Exp: {st.exp}</Text>
                </View>
                <View style={{ alignItems: 'flex-end' }}>
                  <Text style={styles.stockQty}>{st.stock}</Text>
                  <Text style={[styles.stockStatusBadge, st.status === 'LOW_STOCK' ? { color: '#b91c1c' } : { color: '#15803d' }]}>
                    {st.status === 'LOW_STOCK' ? '⚠️ Reorder' : '✓ Good'}
                  </Text>
                </View>
              </View>
            ))}
          </View>
        )}
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.background,
  },
  tabContainer: {
    flexDirection: 'row',
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.border,
  },
  tabBtn: {
    flex: 1,
    paddingVertical: 12,
    alignItems: 'center',
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
  },
  tabBtnActive: {
    borderBottomColor: theme.colors.primary,
  },
  tabText: {
    fontSize: 12,
    fontWeight: '600',
    color: theme.colors.textSecondary,
  },
  tabTextActive: {
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
  cardHeader: {
    fontSize: 12,
    fontWeight: '800',
    color: theme.colors.primaryDark,
    letterSpacing: 0.5,
    marginBottom: 10,
  },
  cardSub: {
    fontSize: 11,
    color: theme.colors.textMuted,
    marginBottom: 10,
  },
  input: {
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: 8,
    paddingHorizontal: 12,
    height: 40,
    fontSize: 13,
    marginBottom: 8,
    backgroundColor: '#f8fafc',
  },
  urgentRow: {
    flexDirection: 'row',
    gap: 8,
    alignItems: 'center',
    marginTop: 4,
  },
  urgentToggle: {
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  urgentToggleActive: {
    backgroundColor: '#fee2e2',
    borderColor: '#ef4444',
  },
  urgentToggleText: {
    fontSize: 11,
    color: theme.colors.textSecondary,
    fontWeight: '600',
  },
  urgentToggleTextActive: {
    color: '#b91c1c',
    fontWeight: '700',
  },
  issueBtn: {
    flex: 1,
    backgroundColor: theme.colors.primary,
    height: 38,
    borderRadius: 8,
    justifyContent: 'center',
    alignItems: 'center',
  },
  issueBtnText: {
    color: '#fff',
    fontWeight: '700',
    fontSize: 12,
  },
  queueItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#f1f5f9',
  },
  tokenCircle: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: theme.colors.primaryLight,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
    borderWidth: 1,
    borderColor: theme.colors.primary,
  },
  tokenText: {
    fontSize: 13,
    fontWeight: '800',
    color: theme.colors.primaryDark,
  },
  queueInfo: {
    flex: 1,
  },
  queueHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  patientName: {
    fontSize: 13,
    fontWeight: '700',
    color: theme.colors.textPrimary,
  },
  queueTime: {
    fontSize: 10,
    color: theme.colors.textMuted,
  },
  patientSub: {
    fontSize: 11,
    color: theme.colors.textSecondary,
    marginTop: 1,
  },
  statusActionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 6,
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
  },
  statusBadgeText: {
    fontSize: 10,
    fontWeight: '700',
  },
  actionCallBtn: {
    backgroundColor: theme.colors.infoBg,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
  },
  actionCallText: {
    fontSize: 10,
    fontWeight: '700',
    color: theme.colors.info,
  },
  actionDispenseBtn: {
    backgroundColor: theme.colors.successBg,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
  },
  actionDispenseText: {
    fontSize: 10,
    fontWeight: '700',
    color: theme.colors.success,
  },
  stockItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#f1f5f9',
  },
  stockName: {
    fontSize: 12,
    fontWeight: '700',
    color: theme.colors.textPrimary,
  },
  stockMeta: {
    fontSize: 10,
    color: theme.colors.textSecondary,
    marginTop: 2,
  },
  stockQty: {
    fontSize: 12,
    fontWeight: '800',
    color: theme.colors.primaryDark,
  },
  stockStatusBadge: {
    fontSize: 10,
    fontWeight: '700',
    marginTop: 2,
  }
});
