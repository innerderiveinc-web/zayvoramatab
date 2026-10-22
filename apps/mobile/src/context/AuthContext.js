import React, { createContext, useState, useContext } from 'react';
import { MatabApi, setServerUrl } from '../services/api';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [currentUser, setCurrentUser] = useState(null);
  const [activeRole, setActiveRole] = useState(null); // 'HAKEEM' | 'STAFF' | 'PATIENT'
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [serverHost, setServerHost] = useState('http://localhost:8080');

  const updateServerHost = (newHost) => {
    setServerHost(newHost);
    setServerUrl(newHost);
  };

  const loginAsRole = async (roleType, username, password) => {
    if (roleType === 'PATIENT') {
      // Patient direct login with MRN or phone
      setActiveRole('PATIENT');
      setSelectedPatient({
        id: 'pat-001',
        full_name: username || 'Mohammad Zubair',
        mrn: 'ZMD-2026-001',
        phone: '+919876543210',
        mizaj: 'Balghami',
        prescriptions: [
          {
            id: 'rx-001',
            date: '2026-10-22',
            protocol: 'P-03: Dyspepsia & IBS Gastric Cascade',
            usul: 'Tadeel-e-Mizaj-e-Meda wa Taqwiyat-e-Hazm',
            items: [
              { name: 'Jawarish Kamuni', dose: '5g BD', vehicle: 'Water after meals' },
              { name: 'Habb-e-Kabid Naushadri', dose: '2 hab BD', vehicle: 'Arq Badiyan (50ml)' }
            ],
            diet: 'Moong dal khichdi, pomegranate juice, warm cumin water. Avoid oily/spicy foods and cold drinks.',
            parhez: 'Avoid sleeping immediately after meals; walk 100 paces after dinner.'
          }
        ]
      });
      return true;
    }

    try {
      const res = await MatabApi.login(username, password);
      setCurrentUser(res.user);
      setActiveRole(roleType);
      return true;
    } catch (e) {
      alert(e.message || 'Login failed. Please check credentials.');
      return false;
    }
  };

  const logout = () => {
    setCurrentUser(null);
    setActiveRole(null);
    setSelectedPatient(null);
  };

  return (
    <AuthContext.Provider value={{
      currentUser,
      activeRole,
      setActiveRole,
      selectedPatient,
      setSelectedPatient,
      serverHost,
      updateServerHost,
      loginAsRole,
      logout
    }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
