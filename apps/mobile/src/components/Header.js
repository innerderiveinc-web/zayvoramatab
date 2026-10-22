import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { theme } from '../theme';
import { useAuth } from '../context/AuthContext';

export const Header = ({ title, subtitle, showBack, onBack }) => {
  const { activeRole, logout, setActiveRole } = useAuth();

  const getRoleBadge = () => {
    switch (activeRole) {
      case 'HAKEEM':
        return { label: '👨‍⚕️ Hakeem OPD', bg: theme.colors.primaryDark, color: '#fff' };
      case 'STAFF':
        return { label: '🏥 Staff Queue', bg: theme.colors.info, color: '#fff' };
      case 'PATIENT':
        return { label: '🧑‍🦱 Patient Portal', bg: theme.colors.accent, color: '#fff' };
      default:
        return null;
    }
  };

  const badge = getRoleBadge();

  return (
    <View style={styles.container}>
      <View style={styles.topRow}>
        <View style={styles.titleContainer}>
          {showBack && (
            <TouchableOpacity onPress={onBack} style={styles.backButton}>
              <Text style={styles.backButtonText}>←</Text>
            </TouchableOpacity>
          )}
          <View>
            <Text style={styles.brandTitle}>🌿 ZAYVORA MATAB</Text>
            <Text style={styles.subtitle}>{subtitle || 'Clinical Unani & Systems Mobile OS'}</Text>
          </View>
        </View>

        <View style={styles.actions}>
          {badge && (
            <TouchableOpacity 
              style={[styles.roleBadge, { backgroundColor: badge.bg }]}
              onPress={() => setActiveRole(null)}
            >
              <Text style={[styles.roleBadgeText, { color: badge.color }]}>{badge.label}</Text>
            </TouchableOpacity>
          )}
          {activeRole && (
            <TouchableOpacity onPress={logout} style={styles.logoutBtn}>
              <Text style={styles.logoutText}>Switch</Text>
            </TouchableOpacity>
          )}
        </View>
      </View>
      {title && <Text style={styles.pageTitle}>{title}</Text>}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    backgroundColor: theme.colors.primary,
    paddingTop: 45,
    paddingBottom: 14,
    paddingHorizontal: theme.spacing.lg,
    borderBottomLeftRadius: 18,
    borderBottomRightRadius: 18,
    elevation: 4,
    shadowColor: '#000',
    shadowOpacity: 0.15,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 3 },
  },
  topRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  titleContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  backButton: {
    paddingRight: 8,
  },
  backButtonText: {
    color: '#fff',
    fontSize: 22,
    fontWeight: 'bold',
  },
  brandTitle: {
    color: '#ffffff',
    fontSize: 16,
    fontWeight: '800',
    letterSpacing: 0.8,
  },
  subtitle: {
    color: theme.colors.primaryLight,
    fontSize: 11,
    fontWeight: '500',
  },
  actions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  roleBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
  },
  roleBadgeText: {
    fontSize: 11,
    fontWeight: '700',
  },
  logoutBtn: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    backgroundColor: 'rgba(255, 255, 255, 0.18)',
    borderRadius: 6,
  },
  logoutText: {
    color: '#ffffff',
    fontSize: 11,
    fontWeight: '600',
  },
  pageTitle: {
    color: '#ffffff',
    fontSize: 18,
    fontWeight: '700',
    marginTop: 8,
  }
});
