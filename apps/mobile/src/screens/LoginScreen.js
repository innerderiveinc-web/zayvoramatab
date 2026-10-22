import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, TextInput, ScrollView, Modal, Alert } from 'react-native';
import { theme } from '../theme';
import { useAuth } from '../context/AuthContext';
import { MatabApi } from '../services/api';

export const LoginScreen = () => {
  const { loginAsRole, serverHost, updateServerHost } = useAuth();
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [hostInput, setHostInput] = useState(serverHost);
  const [patientInput, setPatientInput] = useState('ZMD-2026-001');
  const [isConnecting, setIsConnecting] = useState(false);

  const handleTestConnection = async () => {
    setIsConnecting(true);
    try {
      const res = await MatabApi.checkHealth();
      Alert.alert('Connection Success 🟢', `Connected to ${res.service || 'Matab OS'}\nUptime: ${Math.round(res.uptime_seconds || 0)}s`);
    } catch (e) {
      Alert.alert('Connection Alert 🟡', `Could not reach ${serverHost}.\nOffline mock dataset will be used for testing.`);
    } finally {
      setIsConnecting(false);
    }
  };

  const handleSaveHost = () => {
    updateServerHost(hostInput);
    setShowConfigModal(false);
    Alert.alert('Saved', `Server URL set to: ${hostInput}`);
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.heroSection}>
        <View style={styles.logoBadge}>
          <Text style={styles.logoIcon}>🌿</Text>
        </View>
        <Text style={styles.heroTitle}>ZAYVORA MATAB OS</Text>
        <Text style={styles.heroSubtitle}>Classical Unani Medicine • Bedside Mobile Suite</Text>
      </View>

      <Text style={styles.sectionLabel}>CHOOSE YOUR MOBILE WORKSPACE</Text>

      {/* Role 1: Hakeem */}
      <TouchableOpacity 
        style={[styles.roleCard, { borderColor: theme.colors.primary }]}
        onPress={() => loginAsRole('HAKEEM', 'hakeem', 'matab123')}
      >
        <View style={[styles.roleIconBox, { backgroundColor: theme.colors.primaryLight }]}>
          <Text style={styles.roleIcon}>👨‍⚕️</Text>
        </View>
        <View style={styles.roleTextContainer}>
          <Text style={styles.roleTitle}>Hakeem Bedside Companion</Text>
          <Text style={styles.roleDesc}>1-Click Nabz presets, 21 Master Protocols, Schedule E(1) safety & WhatsApp Rx</Text>
          <View style={styles.tagRow}>
            <Text style={[styles.tag, { backgroundColor: theme.colors.primaryLight, color: theme.colors.primaryDark }]}>Clinician OPD</Text>
            <Text style={[styles.tag, { backgroundColor: '#fef3c7', color: '#92400e' }]}>PIN: 1234</Text>
          </View>
        </View>
      </TouchableOpacity>

      {/* Role 2: Staff */}
      <TouchableOpacity 
        style={[styles.roleCard, { borderColor: theme.colors.info }]}
        onPress={() => loginAsRole('STAFF', 'reception', 'matab123')}
      >
        <View style={[styles.roleIconBox, { backgroundColor: theme.colors.infoBg }]}>
          <Text style={styles.roleIcon}>🏥</Text>
        </View>
        <View style={styles.roleTextContainer}>
          <Text style={styles.roleTitle}>Front Desk & Pharmacy Staff</Text>
          <Text style={styles.roleDesc}>OPD Token Queue (Waiting ➔ Doctor ➔ Dispensed) & FEFO Inventory</Text>
          <View style={styles.tagRow}>
            <Text style={[styles.tag, { backgroundColor: theme.colors.infoBg, color: theme.colors.info }]}>Tokens & Queue</Text>
            <Text style={[styles.tag, { backgroundColor: '#f1f5f9', color: '#475569' }]}>Dispensary</Text>
          </View>
        </View>
      </TouchableOpacity>

      {/* Role 3: Patient Portal */}
      <View style={[styles.roleCard, { borderColor: theme.colors.accent }]}>
        <View style={[styles.roleIconBox, { backgroundColor: theme.colors.accentLight }]}>
          <Text style={styles.roleIcon}>🧑‍🦱</Text>
        </View>
        <View style={styles.roleTextContainer}>
          <Text style={styles.roleTitle}>Patient Health Companion</Text>
          <Text style={styles.roleDesc}>Active prescriptions, Ilaj bil Ghiza diet schedule, and parhez alerts</Text>
          <View style={styles.patientInputRow}>
            <TextInput 
              style={styles.mrnInput}
              value={patientInput}
              onChangeText={setPatientInput}
              placeholder="Enter Patient MRN or Name"
              placeholderTextColor={theme.colors.textMuted}
            />
            <TouchableOpacity 
              style={styles.patientEnterBtn}
              onPress={() => loginAsRole('PATIENT', patientInput, '')}
            >
              <Text style={styles.patientEnterBtnText}>Open ➔</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>

      {/* Server & Connectivity Settings */}
      <View style={styles.footer}>
        <TouchableOpacity 
          style={styles.configBtn}
          onPress={() => setShowConfigModal(true)}
        >
          <Text style={styles.configBtnText}>⚙️ Server IP: {serverHost}</Text>
        </TouchableOpacity>
        <Text style={styles.versionText}>ZAYVORA MATAB OS v2.0 • Build 2026</Text>
      </View>

      {/* Config Modal */}
      <Modal visible={showConfigModal} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Configure Clinic Server URL</Text>
            <Text style={styles.modalDesc}>
              Enter the IP address of the PC running ZAYVORA MATAB OS on the local clinic Wi-Fi (e.g. http://192.168.1.50:8080):
            </Text>
            <TextInput 
              style={styles.modalInput}
              value={hostInput}
              onChangeText={setHostInput}
              placeholder="http://192.168.1.15:8080"
              autoCapitalize="none"
              autoCorrect={false}
            />
            <View style={styles.modalBtnRow}>
              <TouchableOpacity 
                style={styles.testBtn} 
                onPress={handleTestConnection}
                disabled={isConnecting}
              >
                <Text style={styles.testBtnText}>{isConnecting ? 'Testing...' : 'Test Connection'}</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.saveBtn} onPress={handleSaveHost}>
                <Text style={styles.saveBtnText}>Save &amp; Apply</Text>
              </TouchableOpacity>
            </View>
            <TouchableOpacity 
              style={styles.closeBtn} 
              onPress={() => setShowConfigModal(false)}
            >
              <Text style={styles.closeBtnText}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.background,
  },
  content: {
    padding: theme.spacing.lg,
    paddingTop: 55,
  },
  heroSection: {
    alignItems: 'center',
    marginBottom: 24,
  },
  logoBadge: {
    width: 68,
    height: 68,
    borderRadius: 34,
    backgroundColor: theme.colors.primaryLight,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 12,
    borderWidth: 2,
    borderColor: theme.colors.primary,
  },
  logoIcon: {
    fontSize: 32,
  },
  heroTitle: {
    fontSize: 22,
    fontWeight: '800',
    color: theme.colors.primaryDark,
    letterSpacing: 0.5,
  },
  heroSubtitle: {
    fontSize: 12,
    color: theme.colors.textSecondary,
    marginTop: 4,
  },
  sectionLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: theme.colors.textMuted,
    letterSpacing: 0.8,
    marginBottom: 12,
  },
  roleCard: {
    backgroundColor: theme.colors.surface,
    borderRadius: theme.borderRadius.lg,
    padding: theme.spacing.md,
    marginBottom: 14,
    borderWidth: 1.5,
    flexDirection: 'row',
    alignItems: 'flex-start',
    shadowColor: '#000',
    shadowOpacity: 0.05,
    shadowRadius: 5,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  roleIconBox: {
    width: 44,
    height: 44,
    borderRadius: 10,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  roleIcon: {
    fontSize: 22,
  },
  roleTextContainer: {
    flex: 1,
  },
  roleTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: theme.colors.textPrimary,
  },
  roleDesc: {
    fontSize: 12,
    color: theme.colors.textSecondary,
    marginVertical: 4,
    lineHeight: 16,
  },
  tagRow: {
    flexDirection: 'row',
    gap: 6,
    marginTop: 6,
  },
  tag: {
    fontSize: 10,
    fontWeight: '700',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  patientInputRow: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 8,
  },
  mrnInput: {
    flex: 1,
    height: 38,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: 8,
    paddingHorizontal: 10,
    fontSize: 13,
    color: theme.colors.textPrimary,
    backgroundColor: '#fff',
  },
  patientEnterBtn: {
    backgroundColor: theme.colors.accent,
    borderRadius: 8,
    paddingHorizontal: 14,
    justifyContent: 'center',
    alignItems: 'center',
  },
  patientEnterBtnText: {
    color: '#fff',
    fontWeight: '700',
    fontSize: 12,
  },
  footer: {
    alignItems: 'center',
    marginTop: 20,
    paddingBottom: 25,
  },
  configBtn: {
    paddingVertical: 6,
    paddingHorizontal: 12,
    backgroundColor: theme.colors.borderLight,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  configBtnText: {
    fontSize: 11,
    color: theme.colors.textSecondary,
    fontWeight: '600',
  },
  versionText: {
    fontSize: 10,
    color: theme.colors.textMuted,
    marginTop: 8,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'center',
    padding: 20,
  },
  modalContent: {
    backgroundColor: '#fff',
    borderRadius: 16,
    padding: 20,
    elevation: 6,
  },
  modalTitle: {
    fontSize: 17,
    fontWeight: '700',
    color: theme.colors.textPrimary,
    marginBottom: 6,
  },
  modalDesc: {
    fontSize: 12,
    color: theme.colors.textSecondary,
    lineHeight: 17,
    marginBottom: 12,
  },
  modalInput: {
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: 8,
    padding: 10,
    fontSize: 14,
    marginBottom: 14,
  },
  modalBtnRow: {
    flexDirection: 'row',
    gap: 10,
    marginBottom: 10,
  },
  testBtn: {
    flex: 1,
    paddingVertical: 10,
    backgroundColor: theme.colors.infoBg,
    borderRadius: 8,
    alignItems: 'center',
  },
  testBtnText: {
    color: theme.colors.info,
    fontWeight: '700',
    fontSize: 12,
  },
  saveBtn: {
    flex: 1,
    paddingVertical: 10,
    backgroundColor: theme.colors.primary,
    borderRadius: 8,
    alignItems: 'center',
  },
  saveBtnText: {
    color: '#fff',
    fontWeight: '700',
    fontSize: 12,
  },
  closeBtn: {
    paddingVertical: 8,
    alignItems: 'center',
  },
  closeBtnText: {
    color: theme.colors.textMuted,
    fontSize: 12,
  }
});
