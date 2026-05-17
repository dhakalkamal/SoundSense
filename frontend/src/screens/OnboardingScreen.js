import React, { useState, useRef, useEffect } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, TextInput,
  ScrollView, Animated, SafeAreaView, StatusBar,
  KeyboardAvoidingView, Platform, Dimensions,
} from 'react-native';
import { Feather } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import FloatingOrbs from '../components/FloatingOrbs';

const { width: SW } = Dimensions.get('window');

// ─── Palette ──────────────────────────────────────────────────────────────────
const C = {
  bgBase:     '#F0FDFA',   // teal-50
  white:      '#FFFFFF',
  navy:       '#042F2E',   // teal-950
  navyMid:    '#134E4A',   // teal-900
  blue:       '#0F766E',   // teal-700
  blueSoft:   '#0D9488',   // teal-600
  blueDim:    'rgba(15,118,110,0.08)',
  blueBorder: 'rgba(15,118,110,0.28)',
  green:      '#16A34A',
  greenDim:   '#DCFCE7',
  greenBorder:'#86EFAC',
  text:       '#0F172A',
  textSub:    '#475569',
  textHint:   '#94A3B8',
  border:     'rgba(4,47,46,0.10)',
  shadow:     '#042F2E',
};

// ─── Animated waveform ────────────────────────────────────────────────────────
function AnimatedWaveform({ size = 'large' }) {
  const bars = [0.45, 0.75, 1, 0.85, 0.6, 0.9, 0.5];
  const anims = useRef(bars.map(() => new Animated.Value(0.4))).current;

  useEffect(() => {
    const loops = anims.map((a, i) =>
      Animated.loop(
        Animated.sequence([
          Animated.delay(i * 80),
          Animated.timing(a, { toValue: 1,   duration: 500, useNativeDriver: true }),
          Animated.timing(a, { toValue: 0.3, duration: 500, useNativeDriver: true }),
        ])
      )
    );
    loops.forEach((l) => l.start());
    return () => loops.forEach((l) => l.stop());
  }, []);

  const isLarge = size === 'large';
  const barW    = isLarge ? 7 : 4;
  const maxH    = isLarge ? 52 : 22;
  const color   = isLarge ? '#22C55E' : '#FFFFFF';

  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: isLarge ? 5 : 3 }}>
      {bars.map((h, i) => (
        <Animated.View
          key={i}
          style={{
            width: barW, height: maxH * h, borderRadius: barW / 2,
            backgroundColor: color, transform: [{ scaleY: anims[i] }],
          }}
        />
      ))}
    </View>
  );
}

// ─── Progress bar ─────────────────────────────────────────────────────────────
function ProgressBar({ step, total }) {
  const pct = ((step + 1) / total) * 100;
  return (
    <View style={pb.track}>
      <View style={[pb.fill, { width: `${pct}%` }]} />
    </View>
  );
}
const pb = StyleSheet.create({
  track: { height: 4, backgroundColor: 'rgba(255,255,255,0.18)', borderRadius: 2, marginHorizontal: 20, marginBottom: 20 },
  fill:  { height: 4, backgroundColor: '#FFFFFF', borderRadius: 2 },
});

// ─── Chip selector ────────────────────────────────────────────────────────────
function ChipGroup({ options, value, onChange, multi = false }) {
  const toggle = (opt) => {
    if (multi) {
      const arr = Array.isArray(value) ? value : [];
      onChange(arr.includes(opt) ? arr.filter((v) => v !== opt) : [...arr, opt]);
    } else {
      onChange(value === opt ? null : opt);
    }
  };
  const sel = (opt) => multi ? (Array.isArray(value) && value.includes(opt)) : value === opt;
  return (
    <View style={ch.row}>
      {options.map((opt) => (
        <TouchableOpacity key={opt} style={[ch.chip, sel(opt) && ch.chipOn]} onPress={() => toggle(opt)} activeOpacity={0.75}>
          {sel(opt) && <Feather name="check" size={12} color={C.blue} style={{ marginRight: 4 }} />}
          <Text style={[ch.text, sel(opt) && ch.textOn]}>{opt}</Text>
        </TouchableOpacity>
      ))}
    </View>
  );
}
const ch = StyleSheet.create({
  row:    { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginTop: 10 },
  chip:   { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 11, borderRadius: 24, borderWidth: 1.5, borderColor: C.border, backgroundColor: C.white },
  chipOn: { backgroundColor: C.blueDim, borderColor: C.blue },
  text:   { fontFamily: 'Domine_400Regular', color: C.textSub, fontSize: 14 },
  textOn: { fontFamily: 'Domine_700Bold', color: C.blue },
});

// ─── Toggle ───────────────────────────────────────────────────────────────────
function Toggle({ label, sub, value, onChange }) {
  return (
    <TouchableOpacity style={tg.row} onPress={() => onChange(!value)} activeOpacity={0.8}>
      <View style={tg.texts}>
        <Text style={tg.label}>{label}</Text>
        {sub ? <Text style={tg.sub}>{sub}</Text> : null}
      </View>
      <View style={[tg.track, value && tg.on]}>
        <View style={[tg.thumb, value && tg.thumbOn]} />
      </View>
    </TouchableOpacity>
  );
}
const tg = StyleSheet.create({
  row:     { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', backgroundColor: C.white, borderRadius: 16, padding: 16, marginBottom: 10, borderWidth: 1, borderColor: C.border, shadowColor: C.shadow, shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.05, shadowRadius: 6, elevation: 2 },
  texts:   { flex: 1, marginRight: 16 },
  label:   { fontFamily: 'Domine_700Bold', color: C.text, fontSize: 15 },
  sub:     { fontFamily: 'Domine_400Regular', color: C.textSub, fontSize: 12, marginTop: 3, lineHeight: 17 },
  track:   { width: 52, height: 30, borderRadius: 15, backgroundColor: '#E2E8F0', justifyContent: 'center', padding: 3 },
  on:      { backgroundColor: C.blue },
  thumb:   { width: 24, height: 24, borderRadius: 12, backgroundColor: C.white, shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.18, shadowRadius: 2, elevation: 2 },
  thumbOn: { alignSelf: 'flex-end' },
});

// ─── Input field ──────────────────────────────────────────────────────────────
function Field({ label, placeholder, value, onChange, keyboardType = 'default' }) {
  const [focused, setFocused] = useState(false);
  return (
    <View style={{ marginBottom: 14 }}>
      <Text style={inp.label}>{label}</Text>
      <TextInput
        style={[inp.input, focused && inp.focused]}
        placeholder={placeholder}
        placeholderTextColor={C.textHint}
        value={value}
        onChangeText={onChange}
        keyboardType={keyboardType}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
      />
    </View>
  );
}
const inp = StyleSheet.create({
  label:   { fontFamily: 'Domine_700Bold', color: C.text, fontSize: 13, marginBottom: 7 },
  input:   { fontFamily: 'Domine_400Regular', backgroundColor: C.white, borderRadius: 14, paddingHorizontal: 16, paddingVertical: 15, color: C.text, fontSize: 15, borderWidth: 1.5, borderColor: C.border, shadowColor: C.shadow, shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.05, shadowRadius: 6, elevation: 1 },
  focused: { borderColor: C.blue },
});

// ─── Section label ─────────────────────────────────────────────────────────────
const SL = ({ t }) => (
  <Text style={{ fontFamily: 'Domine_700Bold', color: C.textHint, fontSize: 10, letterSpacing: 1.5, marginTop: 22, marginBottom: 8 }}>{t}</Text>
);

// ════════════════════════════════════════════════════════════════════════════
// LANDING
// ════════════════════════════════════════════════════════════════════════════
const FEATURES = [
  { icon: 'volume-2', text: "Detects sounds you can't hear" },
  { icon: 'cpu',      text: 'AI explains what\'s happening' },
  { icon: 'shield',   text: 'Alerts your emergency contact' },
];

function StageLanding({ onStart }) {
  const fadeIn  = useRef(new Animated.Value(0)).current;
  const slideUp = useRef(new Animated.Value(30)).current;

  useEffect(() => {
    Animated.parallel([
      Animated.timing(fadeIn,  { toValue: 1, duration: 700, useNativeDriver: true }),
      Animated.timing(slideUp, { toValue: 0, duration: 600, useNativeDriver: true }),
    ]).start();
  }, []);

  return (
    <LinearGradient colors={['#021A19', C.navy, C.navyMid]} style={{ flex: 1 }} start={{ x: 0.2, y: 0 }} end={{ x: 0.8, y: 1 }}>
      <StatusBar barStyle="light-content" />
      {/* Ambient floating orbs */}
      <FloatingOrbs lightMode={false} />
      <SafeAreaView style={{ flex: 1 }}>
        <Animated.View style={{ flex: 1, opacity: fadeIn, transform: [{ translateY: slideUp }] }}>

          <View style={land.logoArea}>
            <View style={land.logoCircle}>
              <AnimatedWaveform size="large" />
            </View>
            <Text style={land.appName}>Sound Sense</Text>
            <Text style={land.tagline}>Sound · Context · Care</Text>
          </View>

          <View style={land.headlineArea}>
            <Text style={land.headline}>Your ears{'\n'}in every room.</Text>
            <Text style={land.headlineSub}>
              Built for deaf and hard-of-hearing people living independently.
            </Text>
          </View>

          <View style={land.features}>
            {FEATURES.map((f) => (
              <View key={f.text} style={land.featureRow}>
                <View style={land.featureIconWrap}>
                  <Feather name={f.icon} size={20} color="rgba(255,255,255,0.80)" />
                </View>
                <Text style={land.featureText}>{f.text}</Text>
              </View>
            ))}
          </View>

          <View style={land.cta}>
            <TouchableOpacity style={land.startBtn} onPress={onStart} activeOpacity={0.88}>
              <Text style={land.startText}>Get Started</Text>
              <Feather name="arrow-right" size={20} color={C.navy} />
            </TouchableOpacity>
            <Text style={land.note}>Takes about 2 minutes · Can be changed anytime</Text>
          </View>

        </Animated.View>
      </SafeAreaView>
    </LinearGradient>
  );
}

const land = StyleSheet.create({
  logoArea:      { alignItems: 'center', marginTop: 44, marginBottom: 28 },
  logoCircle:    { width: 110, height: 110, borderRadius: 32, backgroundColor: 'rgba(255,255,255,0.07)', borderWidth: 1.5, borderColor: 'rgba(255,255,255,0.13)', alignItems: 'center', justifyContent: 'center', marginBottom: 18 },
  appName:       { fontFamily: 'Domine_700Bold', color: '#FFFFFF', fontSize: 32, letterSpacing: 0.3 },
  tagline:       { fontFamily: 'Domine_400Regular', color: 'rgba(255,255,255,0.45)', fontSize: 12, letterSpacing: 2, marginTop: 4 },
  headlineArea:  { paddingHorizontal: 28, marginBottom: 28 },
  headline:      { fontFamily: 'Domine_700Bold', color: '#FFFFFF', fontSize: 38, lineHeight: 48, letterSpacing: -0.3 },
  headlineSub:   { fontFamily: 'Domine_400Regular', color: 'rgba(255,255,255,0.58)', fontSize: 15, lineHeight: 22, marginTop: 10 },
  features:      { paddingHorizontal: 28, gap: 12, marginBottom: 32 },
  featureRow:    { flexDirection: 'row', alignItems: 'center', gap: 14 },
  featureIconWrap:{ width: 44, height: 44, borderRadius: 12, backgroundColor: 'rgba(255,255,255,0.09)', alignItems: 'center', justifyContent: 'center' },
  featureText:   { fontFamily: 'Domine_400Regular', color: 'rgba(255,255,255,0.82)', fontSize: 15, flex: 1 },
  cta:           { paddingHorizontal: 24, marginTop: 'auto' },
  startBtn:      { backgroundColor: '#FFFFFF', borderRadius: 18, paddingVertical: 18, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, shadowColor: '#000', shadowOffset: { width: 0, height: 8 }, shadowOpacity: 0.25, shadowRadius: 20, elevation: 10, marginBottom: 14 },
  startText:     { fontFamily: 'Domine_700Bold', color: C.navy, fontSize: 18, letterSpacing: 0.3 },
  note:          { fontFamily: 'Domine_400Regular', color: 'rgba(255,255,255,0.32)', fontSize: 12, textAlign: 'center', marginBottom: 20 },
});

// ════════════════════════════════════════════════════════════════════════════
// STEP 1 — Environment
// ════════════════════════════════════════════════════════════════════════════
function StepEnvironment({ data, onChange }) {
  return (
    <ScrollView style={{ flex: 1 }} showsVerticalScrollIndicator={false} contentContainerStyle={st.scroll}>
      <View style={st.card}>
        <SL t="WHERE DO YOU LIVE?" />
        <ChipGroup options={['I live alone', 'With family', 'With housemates', 'Shared care home']} value={data.livingSituation} onChange={(v) => onChange('livingSituation', v)} />
        <SL t="HOME TYPE" />
        <ChipGroup options={['Apartment', 'House', 'Studio flat', 'Shared living', 'Other']} value={data.homeType} onChange={(v) => onChange('homeType', v)} />
      </View>
      <View style={st.card}>
        <SL t="SMART HOME DEVICES — SELECT ALL THAT APPLY" />
        <ChipGroup options={['Amazon Echo', 'Google Home', 'Apple HomeKit', 'Smart lights', 'None']} value={data.smartDevices} onChange={(v) => onChange('smartDevices', v)} multi />
      </View>
      <View style={st.card}>
        <SL t="IS A CAREGIVER NEARBY?" />
        <ChipGroup options={['Yes, very close', 'Sometimes', "No — I'm independent"]} value={data.caregiverNearby} onChange={(v) => onChange('caregiverNearby', v)} />
      </View>
      <View style={{ height: 16 }} />
    </ScrollView>
  );
}

// ════════════════════════════════════════════════════════════════════════════
// STEP 2 — Emergency Contact
// ════════════════════════════════════════════════════════════════════════════
function StepEmergency({ data, onChange, onSkip }) {
  return (
    <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
      <ScrollView style={{ flex: 1 }} showsVerticalScrollIndicator={false} contentContainerStyle={st.scroll}>
        <View style={st.shieldCard}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 10 }}>
            <Feather name="shield" size={18} color="#FFFFFF" />
            <Text style={st.shieldTitle}>Your Safety Net</Text>
          </View>
          <Text style={st.shieldText}>
            If Sound Sense detects something critical — a glass break, alarm, or fall — we can contact this person on your behalf, even if you can't hear your phone.
          </Text>
        </View>
        <View style={st.card}>
          <Field label="Full Name" placeholder="e.g. Sarah Johnson" value={data.contactName} onChange={(v) => onChange('contactName', v)} />
          <Field label="Phone Number" placeholder="+44 7700 000000" value={data.contactPhone} onChange={(v) => onChange('contactPhone', v)} keyboardType="phone-pad" />
          <SL t="RELATIONSHIP" />
          <ChipGroup options={['Parent', 'Sibling', 'Partner', 'Friend', 'Caregiver', 'Neighbor']} value={data.contactRelation} onChange={(v) => onChange('contactRelation', v)} />
        </View>
        <TouchableOpacity onPress={onSkip} style={st.skipBtn}>
          <Text style={st.skipText}>Skip for now — I'll add this in Settings</Text>
        </TouchableOpacity>
        <View style={{ height: 16 }} />
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

// ════════════════════════════════════════════════════════════════════════════
// STEP 3 — Alert Preferences
// ════════════════════════════════════════════════════════════════════════════
function StepAlerts({ data, onChange }) {
  return (
    <ScrollView style={{ flex: 1 }} showsVerticalScrollIndicator={false} contentContainerStyle={st.scroll}>
      <View style={st.card}>
        <SL t="HAPTIC INTENSITY" />
        <ChipGroup options={['Subtle', 'Standard', 'Strong', 'Rhythmic burst']} value={data.hapticPattern} onChange={(v) => onChange('hapticPattern', v)} />
        <SL t="SCREEN FLASH ON CRITICAL ALERTS" />
        <ChipGroup options={['None', 'Subtle flash', 'Strong flash']} value={data.screenFlash} onChange={(v) => onChange('screenFlash', v)} />
        <SL t="DO YOU WEAR A SMARTWATCH?" />
        <ChipGroup options={['Apple Watch', 'Android Wear / WearOS', 'No watch']} value={data.smartwatch} onChange={(v) => onChange('smartwatch', v)} />
      </View>
      <View style={st.card}>
        <Toggle label="Share Guardian Dashboard" sub="Your emergency contact can see live alerts on their phone" value={data.shareGuardian} onChange={(v) => onChange('shareGuardian', v)} />
        <Toggle label="Heavy Sleeper Mode" sub="Escalate faster at night — contact alerted sooner if no response" value={data.heavySleeper} onChange={(v) => onChange('heavySleeper', v)} />
        <Toggle label="Photosensitivity" sub="Disable all screen flash effects for light sensitivity" value={data.photosensitive} onChange={(v) => onChange('photosensitive', v)} />
      </View>
      <View style={{ height: 16 }} />
    </ScrollView>
  );
}

// ════════════════════════════════════════════════════════════════════════════
// DONE
// ════════════════════════════════════════════════════════════════════════════
const SUMMARY_ICONS = { home: 'home', shield: 'shield', bell: 'bell' };

function StageDone({ profile, onEnter }) {
  const scale = useRef(new Animated.Value(0.6)).current;
  const fade  = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.parallel([
      Animated.spring(scale, { toValue: 1, friction: 5, useNativeDriver: true }),
      Animated.timing(fade,  { toValue: 1, duration: 500, useNativeDriver: true }),
    ]).start();
  }, []);

  const hasContact = !!profile?.emergency?.contactName;
  const living     = profile?.env?.livingSituation ?? 'your space';

  return (
    <LinearGradient colors={['#021A19', C.navy, C.navyMid]} style={{ flex: 1 }} start={{ x: 0.2, y: 0 }} end={{ x: 0.8, y: 1 }}>
      <StatusBar barStyle="light-content" />
      <FloatingOrbs lightMode={false} />
      <SafeAreaView style={{ flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 28 }}>
        <Animated.View style={{ opacity: fade, alignItems: 'center', width: '100%' }}>

          <Animated.View style={[done.circle, { transform: [{ scale }] }]}>
            <Feather name="check" size={42} color="#FFFFFF" />
          </Animated.View>

          <Text style={done.title}>You're all set!</Text>
          <Text style={done.sub}>Sound Sense is ready to protect you.</Text>

          <View style={done.summaryBox}>
            {[
              { icon: 'home',   text: `${living} detected as your environment` },
              { icon: 'shield', text: hasContact ? `${profile.emergency.contactName} set as emergency contact` : 'No emergency contact — add one in Settings' },
              { icon: 'bell',   text: `${profile?.alerts?.hapticPattern ?? 'Standard'} haptics · ${profile?.alerts?.screenFlash ?? 'Subtle flash'}` },
            ].map((row, i) => (
              <View key={i}>
                {i > 0 && <View style={done.divider} />}
                <View style={done.summaryRow}>
                  <Feather name={row.icon} size={18} color="rgba(255,255,255,0.55)" />
                  <Text style={done.summaryText}>{row.text}</Text>
                </View>
              </View>
            ))}
          </View>

          <TouchableOpacity style={done.btn} onPress={onEnter} activeOpacity={0.88}>
            <Text style={done.btnText}>Enter Sound Sense</Text>
            <Feather name="arrow-right" size={20} color={C.navy} />
          </TouchableOpacity>

        </Animated.View>
      </SafeAreaView>
    </LinearGradient>
  );
}

const done = StyleSheet.create({
  circle:     { width: 90, height: 90, borderRadius: 45, backgroundColor: C.green, alignItems: 'center', justifyContent: 'center', marginBottom: 24, shadowColor: C.green, shadowOffset: { width: 0, height: 8 }, shadowOpacity: 0.45, shadowRadius: 20, elevation: 10 },
  title:      { fontFamily: 'Domine_700Bold', color: '#FFFFFF', fontSize: 32, marginBottom: 8 },
  sub:        { fontFamily: 'Domine_400Regular', color: 'rgba(255,255,255,0.55)', fontSize: 15, marginBottom: 32, textAlign: 'center' },
  summaryBox: { backgroundColor: 'rgba(255,255,255,0.07)', borderRadius: 18, borderWidth: 1, borderColor: 'rgba(255,255,255,0.11)', width: '100%', padding: 6, marginBottom: 32 },
  summaryRow: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14 },
  summaryText:{ fontFamily: 'Domine_400Regular', color: 'rgba(255,255,255,0.78)', fontSize: 14, flex: 1, lineHeight: 20 },
  divider:    { height: 1, backgroundColor: 'rgba(255,255,255,0.08)', marginHorizontal: 14 },
  btn:        { backgroundColor: '#FFFFFF', borderRadius: 18, paddingVertical: 18, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, width: '100%', shadowColor: '#000', shadowOffset: { width: 0, height: 8 }, shadowOpacity: 0.25, shadowRadius: 20, elevation: 10 },
  btnText:    { fontFamily: 'Domine_700Bold', color: C.navy, fontSize: 18, letterSpacing: 0.3 },
});

// ════════════════════════════════════════════════════════════════════════════
// WHO IS THIS FOR?
// ════════════════════════════════════════════════════════════════════════════
const USER_TYPES = [
  { key: 'self',    icon: 'user',   title: 'Myself',             desc: 'I am deaf or hard-of-hearing' },
  { key: 'elderly', icon: 'users',  title: 'An elderly person',  desc: 'I am a caregiver setting this up for them' },
  { key: 'child',   icon: 'user',   title: 'My child',           desc: 'I am a parent or guardian' },
];

const RELATIONS = {
  elderly: ['Son / Daughter', 'Professional Caregiver', 'Neighbor', 'Friend', 'Other'],
  child:   ['Parent', 'Guardian', 'Carer'],
};

const CONTEXT_INFO = {
  self: {
    icon: 'smile', color: C.blue, colorDim: '#EFF6FF', colorBorder: C.blueBorder,
    title: "Welcome — let's get you set up",
    body:  "You're setting this up for yourself as an independent adult. We'll ask about your home and how you'd like to be alerted. No hearing level, no medical info needed.",
  },
  elderly: {
    icon: 'heart', color: '#7C3AED', colorDim: '#F5F3FF', colorBorder: '#C4B5FD',
    title: 'Setting up on their behalf',
    body:  "You're configuring Sound Sense for someone else. Your relationship helps us personalise the language and escalation rules throughout the app.",
  },
  child: {
    icon: 'lock', color: '#D97706', colorDim: '#FFFBEB', colorBorder: '#FCD34D',
    title: 'Parent / Guardian setup',
    body:  "You'll be able to set a PIN after setup to prevent profile settings from being changed without your permission.",
  },
};

function StageWho({ onContinue }) {
  const [userType,     setUserType]     = useState(null);
  const [relationship, setRelationship] = useState(null);
  const contextAnim = useRef(new Animated.Value(0)).current;
  const relAnim     = useRef(new Animated.Value(0)).current;

  const selectType = (key) => {
    if (key === userType) return;
    setUserType(key);
    setRelationship(null);
    Animated.sequence([
      Animated.timing(contextAnim, { toValue: 0, duration: 100, useNativeDriver: true }),
      Animated.timing(contextAnim, { toValue: 1, duration: 300, useNativeDriver: true }),
    ]).start();
    if (key !== 'self') {
      Animated.timing(relAnim, { toValue: 0, duration: 80, useNativeDriver: true }).start(() =>
        Animated.spring(relAnim, { toValue: 1, friction: 7, useNativeDriver: true }).start()
      );
    } else {
      relAnim.setValue(0);
    }
  };

  const canContinue = userType === 'self' || (userType !== null && relationship !== null);
  const ctx = userType ? CONTEXT_INFO[userType] : null;

  return (
    <SafeAreaView style={who.root}>
      <StatusBar barStyle="dark-content" backgroundColor={C.bgBase} />

      <View style={who.header}>
        <Text style={who.title}>Who is this for?</Text>
        <Text style={who.sub}>
          Your answer determines the entire setup flow.{'\n'}Two taps maximum — no medical info required.
        </Text>
      </View>

      <ScrollView contentContainerStyle={who.scroll} showsVerticalScrollIndicator={false}>

        {USER_TYPES.map((u) => {
          const active = userType === u.key;
          return (
            <TouchableOpacity key={u.key} style={[who.typeCard, active && who.typeCardOn]} onPress={() => selectType(u.key)} activeOpacity={0.82}>
              <View style={[who.typeIconWrap, active && who.typeIconOn]}>
                <Feather name={u.icon} size={22} color={active ? C.blue : C.textSub} />
              </View>
              <View style={who.typeText}>
                <Text style={[who.typeTitle, active && who.typeTitleOn]}>{u.title}</Text>
                <Text style={who.typeDesc}>{u.desc}</Text>
              </View>
              <View style={[who.radioDot, active && who.radioDotOn]}>
                {active && <View style={who.radioDotInner} />}
              </View>
            </TouchableOpacity>
          );
        })}

        {ctx && (
          <Animated.View style={[
            who.contextBox,
            { borderColor: ctx.colorBorder, backgroundColor: ctx.colorDim },
            { opacity: contextAnim, transform: [{ translateY: contextAnim.interpolate({ inputRange: [0, 1], outputRange: [10, 0] }) }] },
          ]}>
            <Feather name={ctx.icon} size={20} color={ctx.color} style={{ marginTop: 1 }} />
            <View style={{ flex: 1 }}>
              <Text style={[who.contextTitle, { color: ctx.color }]}>{ctx.title}</Text>
              <Text style={who.contextBody}>{ctx.body}</Text>
            </View>
          </Animated.View>
        )}

        {(userType === 'elderly' || userType === 'child') && (
          <Animated.View style={[
            who.relBox,
            { opacity: relAnim, transform: [{ scale: relAnim.interpolate({ inputRange: [0, 1], outputRange: [0.95, 1] }) }] },
          ]}>
            <Text style={who.relLabel}>YOUR RELATIONSHIP TO THEM</Text>
            <View style={who.relChips}>
              {RELATIONS[userType].map((r) => {
                const sel = relationship === r;
                return (
                  <TouchableOpacity key={r} style={[who.relChip, sel && who.relChipOn]} onPress={() => setRelationship(r)} activeOpacity={0.75}>
                    {sel && <Feather name="check" size={12} color={C.blue} style={{ marginRight: 4 }} />}
                    <Text style={[who.relChipText, sel && who.relChipTextOn]}>{r}</Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          </Animated.View>
        )}

        <View style={{ height: 16 }} />
      </ScrollView>

      <View style={who.footer}>
        <TouchableOpacity
          style={[who.continueBtn, !canContinue && who.continueBtnOff]}
          onPress={() => canContinue && onContinue({ userType, relationship })}
          activeOpacity={canContinue ? 0.88 : 1}
        >
          <Text style={[who.continueText, !canContinue && who.continueTextOff]}>Continue</Text>
          <Feather name="arrow-right" size={17} color={canContinue ? 'rgba(255,255,255,0.70)' : '#94A3B8'} />
        </TouchableOpacity>
        {!canContinue && (
          <Text style={who.hint}>
            {!userType ? "Select who you're setting this up for" : 'Select your relationship to continue'}
          </Text>
        )}
      </View>
    </SafeAreaView>
  );
}

const who = StyleSheet.create({
  root:   { flex: 1, backgroundColor: C.bgBase },
  header: { paddingHorizontal: 24, paddingTop: 28, paddingBottom: 20 },
  title:  { fontFamily: 'Domine_700Bold', color: C.navy, fontSize: 28, letterSpacing: -0.2, marginBottom: 8 },
  sub:    { fontFamily: 'Domine_400Regular', color: C.textSub, fontSize: 14, lineHeight: 21 },
  scroll: { paddingHorizontal: 16, paddingBottom: 8 },

  typeCard:    { flexDirection: 'row', alignItems: 'center', backgroundColor: C.white, borderRadius: 18, padding: 18, marginBottom: 12, borderWidth: 2, borderColor: C.border, shadowColor: C.shadow, shadowOffset: { width: 0, height: 3 }, shadowOpacity: 0.07, shadowRadius: 8, elevation: 2, gap: 14 },
  typeCardOn:  { borderColor: C.blue, backgroundColor: '#CCFBF1' },
  typeIconWrap:{ width: 54, height: 54, borderRadius: 15, backgroundColor: C.bgBase, alignItems: 'center', justifyContent: 'center' },
  typeIconOn:  { backgroundColor: C.blueDim },
  typeText:    { flex: 1 },
  typeTitle:   { fontFamily: 'Domine_700Bold', color: C.text, fontSize: 17, marginBottom: 3 },
  typeTitleOn: { color: C.blue },
  typeDesc:    { fontFamily: 'Domine_400Regular', color: C.textSub, fontSize: 13, lineHeight: 18 },

  radioDot:      { width: 22, height: 22, borderRadius: 11, borderWidth: 2, borderColor: C.border, alignItems: 'center', justifyContent: 'center' },
  radioDotOn:    { borderColor: C.blue },
  radioDotInner: { width: 11, height: 11, borderRadius: 6, backgroundColor: C.blue },

  contextBox:   { flexDirection: 'row', gap: 12, borderRadius: 16, borderWidth: 1.5, padding: 16, marginBottom: 14, alignItems: 'flex-start' },
  contextTitle: { fontFamily: 'Domine_700Bold', fontSize: 14, marginBottom: 5 },
  contextBody:  { fontFamily: 'Domine_400Regular', color: C.textSub, fontSize: 13, lineHeight: 19 },

  relBox:       { backgroundColor: C.white, borderRadius: 18, padding: 18, marginBottom: 12, borderWidth: 1, borderColor: C.border, shadowColor: C.shadow, shadowOffset: { width: 0, height: 3 }, shadowOpacity: 0.07, shadowRadius: 8, elevation: 2 },
  relLabel:     { fontFamily: 'Domine_700Bold', color: C.textHint, fontSize: 10, letterSpacing: 1.5, marginBottom: 12 },
  relChips:     { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  relChip:      { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 11, borderRadius: 24, borderWidth: 1.5, borderColor: C.border, backgroundColor: C.bgBase },
  relChipOn:    { backgroundColor: C.blueDim, borderColor: C.blue },
  relChipText:  { fontFamily: 'Domine_400Regular', color: C.textSub, fontSize: 14 },
  relChipTextOn:{ fontFamily: 'Domine_700Bold', color: C.blue },

  footer:         { paddingHorizontal: 16, paddingBottom: 16, paddingTop: 8 },
  continueBtn:    { backgroundColor: C.navy, borderRadius: 18, paddingVertical: 18, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, shadowColor: C.navy, shadowOffset: { width: 0, height: 6 }, shadowOpacity: 0.28, shadowRadius: 14, elevation: 8 },
  continueBtnOff: { backgroundColor: '#CBD5E1', shadowOpacity: 0 },
  continueText:   { fontFamily: 'Domine_700Bold', color: '#FFFFFF', fontSize: 17, letterSpacing: 0.3 },
  continueTextOff:{ color: '#94A3B8' },
  hint:           { fontFamily: 'Domine_400Regular', color: C.textHint, fontSize: 12, textAlign: 'center', marginTop: 10 },
});

// ─── Step header config ───────────────────────────────────────────────────────
const STEP_META = [
  { icon: 'home',   title: 'Your World',   desc: 'Tell us about your space'         },
  { icon: 'shield', title: 'Safety Net',   desc: 'Who to contact in an emergency'   },
  { icon: 'bell',   title: 'How to Alert', desc: 'Vibration, flash & smartwatch'    },
];

// ════════════════════════════════════════════════════════════════════════════
// ROOT
// ════════════════════════════════════════════════════════════════════════════
export default function OnboardingScreen({ onComplete }) {
  const [stage,   setStage]   = useState('landing');
  const [step,    setStep]    = useState(0);
  const [whoData, setWhoData] = useState(null);
  const fadeAnim              = useRef(new Animated.Value(1)).current;
  const [profile, setProfile] = useState(null);

  const [env,       setEnv]       = useState({ livingSituation: null, homeType: null, smartDevices: [], caregiverNearby: null });
  const [emergency, setEmergency] = useState({ contactName: '', contactPhone: '', contactRelation: null });
  const [alerts,    setAlerts]    = useState({ hapticPattern: 'Standard', screenFlash: 'Subtle flash', smartwatch: 'No watch', shareGuardian: false, heavySleeper: false, photosensitive: false });

  const upEnv  = (k, v) => setEnv((p)       => ({ ...p, [k]: v }));
  const upEmer = (k, v) => setEmergency((p) => ({ ...p, [k]: v }));
  const upAler = (k, v) => setAlerts((p)    => ({ ...p, [k]: v }));

  const navigate = (cb) => {
    fadeAnim.setValue(0);
    cb();
    Animated.timing(fadeAnim, { toValue: 1, duration: 280, useNativeDriver: true }).start();
  };

  const goNext = () => {
    if (step < 2) {
      navigate(() => setStep((s) => s + 1));
    } else {
      const p = { who: whoData, env, emergency, alerts };
      setProfile(p);
      setStage('done');
    }
  };

  const goBack        = () => { if (step > 0) navigate(() => setStep((s) => s - 1)); else setStage('who'); };
  const skipEmergency = () => navigate(() => setStep((s) => s + 1));

  if (stage === 'landing') return <StageLanding onStart={() => setStage('who')} />;
  if (stage === 'who')     return <StageWho onContinue={(d) => { setWhoData(d); setStep(0); setStage('steps'); fadeAnim.setValue(1); }} />;
  if (stage === 'done')    return <StageDone profile={profile} onEnter={() => onComplete(profile)} />;

  const meta = STEP_META[step];

  return (
    <SafeAreaView style={st.root}>
      <StatusBar barStyle="light-content" backgroundColor={C.navy} />

      <View style={st.header}>
        <View style={st.headerRow}>
          <TouchableOpacity style={st.backBtn} onPress={goBack}>
            <Feather name="arrow-left" size={18} color="#FFFFFF" />
          </TouchableOpacity>
          <View style={st.stepPill}>
            <Text style={st.stepPillText}>Step {step + 1} of 3</Text>
          </View>
          <TouchableOpacity style={st.continueBtn} onPress={goNext} activeOpacity={0.85}>
            <Text style={st.continueBtnText}>{step < 2 ? 'Continue' : 'Done'}</Text>
            <Feather name={step < 2 ? 'arrow-right' : 'check'} size={14} color="rgba(255,255,255,0.80)" />
          </TouchableOpacity>
        </View>

        <ProgressBar step={step} total={3} />

        <View style={st.headerBody}>
          <View style={st.headerIconWrap}>
            <Feather name={meta.icon} size={26} color="#FFFFFF" />
          </View>
          <Text style={st.headerTitle}>{meta.title}</Text>
          <Text style={st.headerDesc}>{meta.desc}</Text>
        </View>
      </View>

      <Animated.View style={[st.content, { opacity: fadeAnim }]}>
        {step === 0 && <StepEnvironment data={env}       onChange={upEnv} />}
        {step === 1 && <StepEmergency   data={emergency} onChange={upEmer} onSkip={skipEmergency} />}
        {step === 2 && <StepAlerts      data={alerts}    onChange={upAler} />}
      </Animated.View>
    </SafeAreaView>
  );
}

// ─── Shared step styles ───────────────────────────────────────────────────────
const st = StyleSheet.create({
  root:    { flex: 1, backgroundColor: C.bgBase },
  header:  { backgroundColor: C.navy, borderBottomLeftRadius: 28, borderBottomRightRadius: 28, paddingBottom: 24 },
  headerRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingTop: 14, paddingBottom: 16 },

  backBtn:      { width: 40, height: 40, borderRadius: 12, backgroundColor: 'rgba(255,255,255,0.10)', alignItems: 'center', justifyContent: 'center' },
  stepPill:     { backgroundColor: 'rgba(255,255,255,0.14)', borderRadius: 20, paddingHorizontal: 14, paddingVertical: 6 },
  stepPillText: { fontFamily: 'Domine_700Bold', color: '#FFFFFF', fontSize: 13, letterSpacing: 0.3 },

  headerBody:    { alignItems: 'center', paddingHorizontal: 20 },
  headerIconWrap:{ width: 52, height: 52, borderRadius: 16, backgroundColor: 'rgba(255,255,255,0.10)', alignItems: 'center', justifyContent: 'center', marginBottom: 10 },
  headerTitle:   { fontFamily: 'Domine_700Bold', color: '#FFFFFF', fontSize: 24, letterSpacing: 0.2 },
  headerDesc:    { fontFamily: 'Domine_400Regular', color: 'rgba(255,255,255,0.52)', fontSize: 13, marginTop: 4 },

  continueBtn:      { flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: 'rgba(255,255,255,0.16)', borderRadius: 20, paddingHorizontal: 14, paddingVertical: 8, borderWidth: 1, borderColor: 'rgba(255,255,255,0.22)' },
  continueBtnText:  { fontFamily: 'Domine_700Bold', color: '#FFFFFF', fontSize: 14 },

  content: { flex: 1, overflow: 'hidden' },
  scroll:  { paddingHorizontal: 16, paddingTop: 20, paddingBottom: 110 },

  card:       { backgroundColor: C.white, borderRadius: 20, padding: 18, marginBottom: 14, borderWidth: 1, borderColor: C.border, shadowColor: C.shadow, shadowOffset: { width: 0, height: 3 }, shadowOpacity: 0.07, shadowRadius: 10, elevation: 3 },
  shieldCard: { backgroundColor: C.navy, borderRadius: 20, padding: 20, marginBottom: 14 },
  shieldTitle:{ fontFamily: 'Domine_700Bold', color: '#FFFFFF', fontSize: 17, marginBottom: 4 },
  shieldText: { fontFamily: 'Domine_400Regular', color: 'rgba(255,255,255,0.68)', fontSize: 14, lineHeight: 21 },

  skipBtn:  { alignSelf: 'center', paddingVertical: 10 },
  skipText: { fontFamily: 'Domine_400Regular', color: C.textHint, fontSize: 13, textDecorationLine: 'underline' },

  footer: { position: 'absolute', bottom: 0, left: 0, right: 0, paddingHorizontal: 16, paddingTop: 10, paddingBottom: 28, backgroundColor: C.bgBase },
});
