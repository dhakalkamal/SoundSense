import React, { useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  KeyboardAvoidingView, Platform, Alert, ActivityIndicator,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Feather } from '@expo/vector-icons';
import FloatingOrbs from '../components/FloatingOrbs';

const DUMMY_USERS = [
  { email: 'user@soundsense.com', password: 'password123', name: 'Alex' },
  { email: 'demo@soundsense.com', password: 'demo1234',    name: 'Demo User' },
];

export default function LoginScreen({ navigation }) {
  const [email, setEmail]               = useState('');
  const [password, setPassword]         = useState('');
  const [loading, setLoading]           = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const handleLogin = () => {
    if (!email.trim() || !password.trim()) {
      Alert.alert('Missing Fields', 'Please enter your email and password.');
      return;
    }
    setLoading(true);
    setTimeout(() => {
      const user = DUMMY_USERS.find(
        (u) => u.email === email.trim().toLowerCase() && u.password === password
      );
      setLoading(false);
      if (user) {
        navigation.replace('Home', { userName: user.name });
      } else {
        Alert.alert('Login Failed', 'Invalid email or password.\n\nTry:\nuser@soundsense.com / password123');
      }
    }, 1000);
  };

  return (
    // Deep teal — premium medical feel (Bupa / One Medical aesthetic)
    <LinearGradient
      colors={['#021A19', '#042F2E', '#134E4A']}
      style={styles.gradient}
      start={{ x: 0.2, y: 0 }}
      end={{ x: 0.8, y: 1 }}
    >
      {/* Ambient background animation */}
      <FloatingOrbs lightMode={false} />

      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <View style={styles.inner}>

          {/* ── Logo ─────────────────────────────────────────── */}
          <View style={styles.logoArea}>
            <View style={styles.logoCircle}>
              <Feather name="headphones" size={38} color="#FFFFFF" />
            </View>

            <Text style={styles.appName}>SoundSense</Text>
            <Text style={styles.tagline}>Hear the world differently</Text>
          </View>

          {/* ── Form card ────────────────────────────────────── */}
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Welcome back</Text>
            <Text style={styles.cardSub}>Sign in to continue</Text>

            {/* Email */}
            <Text style={styles.label}>Email</Text>
            <View style={styles.inputRow}>
              <Feather name="mail" size={15} color="#64748B" style={styles.inputIcon} />
              <TextInput
                style={styles.input}
                placeholder="you@soundsense.com"
                placeholderTextColor="#475569"
                value={email}
                onChangeText={setEmail}
                keyboardType="email-address"
                autoCapitalize="none"
              />
            </View>

            {/* Password */}
            <Text style={styles.label}>Password</Text>
            <View style={styles.inputRow}>
              <Feather name="lock" size={15} color="#64748B" style={styles.inputIcon} />
              <TextInput
                style={[styles.input, { flex: 1 }]}
                placeholder="Enter your password"
                placeholderTextColor="#475569"
                value={password}
                onChangeText={setPassword}
                secureTextEntry={!showPassword}
              />
              <TouchableOpacity style={styles.eyeBtn} onPress={() => setShowPassword(!showPassword)}>
                <Feather name={showPassword ? 'eye-off' : 'eye'} size={17} color="#64748B" />
              </TouchableOpacity>
            </View>

            <TouchableOpacity style={styles.forgotBtn}>
              <Text style={styles.forgotText}>Forgot password?</Text>
            </TouchableOpacity>

            {/* Sign in */}
            <TouchableOpacity
              style={[styles.signInBtn, loading && { opacity: 0.65 }]}
              onPress={handleLogin}
              disabled={loading}
              activeOpacity={0.85}
            >
              <LinearGradient
                colors={['#0F766E', '#0D9488']}
                style={styles.signInGradient}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 0 }}
              >
                {loading ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <>
                    <Text style={styles.signInText}>Sign In</Text>
                    <Feather name="arrow-right" size={16} color="#fff" />
                  </>
                )}
              </LinearGradient>
            </TouchableOpacity>

            {/* Demo hint */}
            <View style={styles.demo}>
              <Feather name="info" size={11} color="#475569" />
              <Text style={styles.demoText}>
                Demo: user@soundsense.com · password123
              </Text>
            </View>
          </View>

        </View>
      </KeyboardAvoidingView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  gradient: { flex: 1 },
  flex:     { flex: 1 },
  inner: {
    flex: 1, justifyContent: 'center', paddingHorizontal: 24,
  },

  // Logo
  logoArea: { alignItems: 'center', marginBottom: 30 },
  logoCircle: {
    width: 84, height: 84, borderRadius: 42,
    backgroundColor: 'rgba(15,118,110,0.25)',
    borderWidth: 1.5, borderColor: 'rgba(45,212,191,0.25)',
    alignItems: 'center', justifyContent: 'center',
    marginBottom: 14,
  },
  appName: {
    fontFamily: 'Domine_700Bold',
    fontSize: 30, color: '#F1F5F9', letterSpacing: 0.5,
  },
  tagline: {
    fontFamily: 'Domine_400Regular',
    fontSize: 13, color: '#94A3B8', marginTop: 5, letterSpacing: 0.5,
  },

  // Form card
  card: {
    backgroundColor: 'rgba(15,23,42,0.75)',
    borderRadius: 22,
    padding: 22,
    borderWidth: 1,
    borderColor: 'rgba(45,212,191,0.12)',
  },
  cardTitle: {
    fontFamily: 'Domine_700Bold',
    fontSize: 20, color: '#F1F5F9', marginBottom: 3,
  },
  cardSub: {
    fontFamily: 'Domine_400Regular',
    fontSize: 13, color: '#64748B', marginBottom: 18,
  },

  label: {
    fontFamily: 'Domine_700Bold',
    color: '#94A3B8', fontSize: 11,
    letterSpacing: 0.9, textTransform: 'uppercase',
    marginBottom: 7, marginTop: 14,
  },
  inputRow: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: 'rgba(15,23,42,0.80)',
    borderRadius: 11, borderWidth: 1,
    borderColor: 'rgba(15,118,110,0.20)',
    paddingHorizontal: 12,
  },
  inputIcon: { marginRight: 9 },
  input: {
    flex: 1, paddingVertical: 13,
    fontFamily: 'Domine_400Regular',
    color: '#F1F5F9', fontSize: 14,
  },
  eyeBtn: { paddingLeft: 10, paddingVertical: 12 },

  forgotBtn: { alignSelf: 'flex-end', marginTop: 9 },
  forgotText: {
    fontFamily: 'Domine_400Regular',
    color: '#2DD4BF', fontSize: 13,
  },

  signInBtn: {
    borderRadius: 13, marginTop: 20, overflow: 'hidden',
    shadowColor: '#0F766E', shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.40, shadowRadius: 10, elevation: 7,
  },
  signInGradient: {
    flexDirection: 'row', alignItems: 'center',
    justifyContent: 'center', gap: 9, paddingVertical: 14,
  },
  signInText: {
    fontFamily: 'Domine_700Bold',
    color: '#fff', fontSize: 15, letterSpacing: 0.4,
  },

  demo: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    marginTop: 16,
    backgroundColor: 'rgba(15,23,42,0.50)',
    borderRadius: 10, padding: 11,
    borderWidth: 1, borderColor: 'rgba(15,118,110,0.12)',
  },
  demoText: {
    fontFamily: 'Domine_400Regular',
    color: '#475569', fontSize: 12,
  },
});
