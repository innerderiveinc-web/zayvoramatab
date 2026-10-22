# 📱 ZAYVORA MATAB OS — Mobile App (React Native / Expo)

A cross-platform mobile application suite built with **React Native & Expo** designed for bedside Unani clinical practice, clinic queue management, and patient care continuity.

---

## 🌟 3-in-1 Unified Mobile Experience

### 1. 👨‍⚕️ Hakeem Bedside OPD Companion
- **1-Click Nabz Presets**: Rapid recording of classical Unani pulse qualities (`دموی`, `صفراوی`, `بلغمی`, `سوداوی`).
- **1-Click Quick Complaints**: Immediate selection of common clinical presentations (Dyspepsia, Arthritis, Migraine, Asthma).
- **21 Governed Master Protocols (P-01 to P-21)**: Auto-loads 3-phase Af'aal cascade (`Tanqiya ➔ Tahleel ➔ Taqwiyat`).
- **Clinical Safety Firewall**: In-app Schedule E(1) Mudabbar verification & Herb-Drug interaction alerts.
- **1-Click Direct WhatsApp Rx**: Formats full bilingual Urdu/English prescriptions and opens WhatsApp with one tap.

### 2. 🏥 Front Desk & Dispensary Staff
- **Live OPD Token Queue**: Instant view of tokens (`T-01`, `T-02`, etc.) with statuses (`WAITING`, `IN_CONSULTATION`, `DISPENSED`).
- **Fast Walk-in Registration**: Issue new token in under 5 seconds with mobile number.
- **FEFO Stock Monitor**: First-Expiry-First-Out batch verification and re-order alerts.

### 3. 🧑‍🦱 Patient Health Companion
- **Active Prescriptions**: Timed dosage instructions and vehicle/anupan (e.g. Arq Badiyan, lukewarm water).
- **Ilaj bil Ghiza & Parhez**: Clear dietary guidelines and strict avoidance rules.
- **Direct Clinic Access**: 1-click WhatsApp or Phone dialer to contact the clinic.

---

## 🚀 Quick Start Guide

### 1. Prerequisites
Ensure Node.js is installed.

### 2. Start the Mobile Dev Server
```bash
cd apps/mobile
npm install
npm start
```

### 3. Preview on Mobile Device (iOS / Android)
1. Install **Expo Go** from Google Play Store or Apple App Store.
2. Ensure your phone and development computer are connected to the **same Wi-Fi network**.
3. Scan the QR code displayed in the terminal with the Expo Go app (Android) or the Camera app (iOS).

### 4. Connect to Backend Server
On the app's login screen, tap **⚙️ Server IP** and set it to your computer's local network IP:
```text
http://192.168.1.XX:8080
```
*(Offline mock mode is automatically available if disconnected from the server).*

---

## 🔑 Demo Login Credentials
- **Hakeem (Doctor)**: `hakeem` / `matab123` (Prescription PIN: `1234`)
- **Staff (Reception)**: `reception` / `matab123`
- **Patient**: Enter any MRN or Name (e.g., `ZMD-2026-001` or `Mohammad Zubair`)
