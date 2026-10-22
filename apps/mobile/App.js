import React from 'react';
import { StyleSheet, View } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { AuthProvider, useAuth } from './src/context/AuthContext';
import { LoginScreen } from './src/screens/LoginScreen';
import { HakeemConsultationScreen } from './src/screens/HakeemConsultationScreen';
import { StaffQueueScreen } from './src/screens/StaffQueueScreen';
import { PatientPortalScreen } from './src/screens/PatientPortalScreen';
import { theme } from './src/theme';

function MainNavigator() {
  const { activeRole } = useAuth();

  return (
    <View style={styles.container}>
      <StatusBar style="light" backgroundColor={theme.colors.primaryDark} />
      {activeRole === 'HAKEEM' && <HakeemConsultationScreen />}
      {activeRole === 'STAFF' && <StaffQueueScreen />}
      {activeRole === 'PATIENT' && <PatientPortalScreen />}
      {!activeRole && <LoginScreen />}
    </View>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <MainNavigator />
    </AuthProvider>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.background,
  },
});
