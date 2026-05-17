import React, { useState, useEffect, useRef } from 'react';
import {
  View, Text, StyleSheet, FlatList, TouchableOpacity,
  Animated, SafeAreaView, StatusBar, Modal, Linking,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Feather } from '@expo/vector-icons';
import FloatingOrbs from '../components/FloatingOrbs';
import { BASE_URL } from '../config';
import { useAudioStream } from '../hooks/useAudioStream';

// ─── Tailwind palette (only what we need) ─────────────────────────────────────
const TW = {
  teal950:   '#042F2E',
  teal900:   '#134E4A',
  teal800:   '#115E59',
  teal700:   '#0F766E',
  teal600:   '#0D9488',
  teal100:   '#CCFBF1',
  teal50:    '#F0FDFA',

  slate900: '#0F172A',
  slate700: '#334155',
  slate600: '#475569',
  slate500: '#64748B',
  slate400: '#94A3B8',
  slate300: '#CBD5E1',
  slate200: '#E2E8F0',
  slate100: '#F1F5F9',
  slate50:  '#F8FAFC',

  green600: '#16A34A',
  green100: '#DCFCE7',
  green300: '#86EFAC',

  amber600: '#D97706',
  amber100: '#FEF3C7',
  amber300: '#FCD34D',

  red600:   '#DC2626',
  red100:   '#FEE2E2',
  red300:   '#FCA5A5',

  violet600: '#7C3AED',
  violet100: '#EDE9FE',
  violet300: '#C4B5FD',

  white: '#FFFFFF',
};

// ─── Urgency config ───────────────────────────────────────────────────────────
const URGENCY = {
  low:      { color: TW.green600,  dim: TW.green100,  border: TW.green300,  label: 'LOW',      barColors: ['#15803D', TW.green600]  },
  medium:   { color: TW.amber600,  dim: TW.amber100,  border: TW.amber300,  label: 'MEDIUM',   barColors: ['#B45309', TW.amber600]  },
  high:     { color: TW.red600,    dim: TW.red100,    border: TW.red300,    label: 'HIGH',     barColors: ['#B91C1C', TW.red600]    },
  critical: { color: TW.violet600, dim: TW.violet100, border: TW.violet300, label: 'CRITICAL', barColors: ['#5B21B6', TW.violet600] },
};

// ─── Feather icon map ─────────────────────────────────────────────────────────
const ICON_MAP = {
  baby:      'alert-circle',
  alarm:     'bell',
  footsteps: 'activity',
  water:     'droplet',
  glass:     'zap',
  birds:     'sun',
  doorbell:  'home',
  voice:     'mic',
};

// ─── Raw label → icon key ─────────────────────────────────────────────────────
const LABEL_ICON_MAP = {
  child_crying:  'baby',
  alarm_beep:    'alarm',
  alarm:         'alarm',
  footsteps:     'footsteps',
  door_open:     'footsteps',
  water_running: 'water',
  glass_break:   'glass',
  birds:         'birds',
  doorbell:      'doorbell',
  raised_voices: 'voice',
};

function labelToTitle(label) {
  return label.split('_').map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ') + ' Detected';
}

function formatElapsed(elapsed_s) {
  if (elapsed_s < 60)   return 'Just now';
  if (elapsed_s < 3600) return `${Math.floor(elapsed_s / 60)} min ago`;
  return `${Math.floor(elapsed_s / 3600)} hr ago`;
}

function SoundIcon({ iconKey, size = 20 }) {
  // Monochromatic — all icons use the same slate-400 grey
  return <Feather name={ICON_MAP[iconKey] ?? 'volume-2'} size={size} color={TW.slate400} />;
}

// ─── Notifications ────────────────────────────────────────────────────────────
const INITIAL_NOTIFICATIONS = [
  { id:'1', urgency:'critical', iconKey:'baby',      title:'Child Crying Detected',  context:'Sudden, sustained child crying detected — this may need your immediate attention.',             rawLabel:'child_crying',          time:'Just now',  read:false },
  { id:'2', urgency:'high',     iconKey:'alarm',     title:'Alarm Sounding',          context:'Alarm beep repeated 3 times in 30 seconds — urgent action may be required.',                    rawLabel:'alarm_beep',            time:'1 min ago', read:false },
  { id:'3', urgency:'medium',   iconKey:'footsteps', title:'Someone Entered',         context:'Footsteps followed by a door opening — someone may have just entered the space.',                rawLabel:'footsteps · door_open', time:'4 min ago', read:false },
  { id:'4', urgency:'medium',   iconKey:'water',     title:'Water Left Running',      context:'Tap has been running for over 2 minutes — you may have left the water on.',                      rawLabel:'water_running',         time:'12 min ago',read:true  },
  { id:'5', urgency:'critical', iconKey:'glass',     title:'Glass Break Detected',    context:'A sharp sudden impact sound — a glass or window may have broken nearby.',                        rawLabel:'glass_break',           time:'18 min ago',read:true  },
  { id:'6', urgency:'low',      iconKey:'birds',     title:'Calm Environment',        context:'Background birdsong only — your environment is currently quiet and safe.',                        rawLabel:'birds',                 time:'30 min ago',read:true  },
  { id:'7', urgency:'medium',   iconKey:'doorbell',  title:'Doorbell Rang',           context:'Doorbell sound detected — someone may be waiting at your door.',                                 rawLabel:'doorbell',              time:'1 hr ago',  read:true  },
];

async function postFeedback(id, label, verdict) {
  try {
    await fetch(`${BASE_URL}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ notification_id: id, label, verdict }),
    });
  } catch (_) {}
}

// ─── Waveform brand mark ──────────────────────────────────────────────────────
function WaveformMark() {
  return (
    <View style={wf.wrap}>
      {[7, 14, 9, 18, 11, 16, 8].map((h, i) => (
        <View key={i} style={[wf.bar, { height: h }]} />
      ))}
    </View>
  );
}
const wf = StyleSheet.create({
  wrap: { flexDirection: 'row', alignItems: 'flex-end', gap: 2.5 },
  bar:  { width: 3, borderRadius: 2, backgroundColor: '#4ADE80' },
});

// ─── Mic status indicator — non-interactive, lives in header ─────────────────
// Status → colour:  requesting=amber  listening=green  disconnected=slate  denied=red
const MIC_STATUS_COLOR = {
  requesting:   '#D97706', // amber-600
  listening:    '#16A34A', // green-600
  disconnected: '#94A3B8', // slate-400
  denied:       '#DC2626', // red-600
};

function MicStatus({ streamStatus }) {
  const pulseAnim = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    if (streamStatus === 'listening' || streamStatus === 'requesting') {
      const loop = Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, { toValue: 0.25, duration: 750, useNativeDriver: true }),
          Animated.timing(pulseAnim, { toValue: 1,    duration: 750, useNativeDriver: true }),
        ]),
      );
      loop.start();
      return () => loop.stop();
    }
    pulseAnim.setValue(1);
  }, [streamStatus]);

  const color = MIC_STATUS_COLOR[streamStatus] ?? MIC_STATUS_COLOR.disconnected;
  const icon  = streamStatus === 'denied' ? 'mic-off' : 'mic';

  return (
    <View style={ms.wrap}>
      <Animated.View style={[ms.dot, { backgroundColor: color, opacity: pulseAnim }]} />
      <Feather name={icon} size={11} color={color} />
    </View>
  );
}
const ms = StyleSheet.create({
  wrap: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 6, paddingVertical: 6 },
  dot:  { width: 6, height: 6, borderRadius: 3 },
});

// ─── Urgency pill — small coloured badge, kept coloured for quick triage ──────
function UrgencyPill({ urgency }) {
  const u = URGENCY[urgency];
  return (
    <View style={[pill.wrap, { backgroundColor: u.dim, borderColor: u.border }]}>
      <View style={[pill.dot, { backgroundColor: u.color }]} />
      <Text style={[pill.text, { color: u.color }]}>{u.label}</Text>
    </View>
  );
}
const pill = StyleSheet.create({
  wrap: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 9, paddingVertical: 5, borderRadius: 20, borderWidth: 1 },
  dot:  { width: 5, height: 5, borderRadius: 3 },
  text: { fontFamily: 'Domine_700Bold', fontSize: 9, letterSpacing: 1.3 },
});

// ─── Feedback row ─────────────────────────────────────────────────────────────
function FeedbackRow({ notifId, rawLabel, value, onChange }) {
  const BTNS = [
    { key: 'correct', label: 'Correct',  icon: 'check',       color: TW.green600, dim: TW.green100 },
    { key: 'wrong',   label: 'Wrong',    icon: 'x',           color: TW.red600,   dim: TW.red100   },
    { key: 'unsure',  label: 'Not Sure', icon: 'help-circle', color: TW.amber600, dim: TW.amber100 },
  ];
  const handle = (k) => { onChange(notifId, k); postFeedback(notifId, rawLabel, k); };
  return (
    <View style={fb.row}>
      {value ? (
        <View style={fb.sent}>
          <Feather name="check-circle" size={13} color={TW.indig600} />
          <Text style={fb.sentText}>Feedback sent — model will learn</Text>
        </View>
      ) : (
        BTNS.map((btn) => (
          <TouchableOpacity
            key={btn.key}
            style={[fb.btn, { borderColor: btn.color + '44' }, value === btn.key && { backgroundColor: btn.dim, borderColor: btn.color }]}
            onPress={() => handle(btn.key)}
            activeOpacity={0.75}
          >
            <Feather name={btn.icon} size={11} color={btn.color} />
            <Text style={[fb.btnText, { color: btn.color }]}>{btn.label}</Text>
          </TouchableOpacity>
        ))
      )}
    </View>
  );
}
const fb = StyleSheet.create({
  row: { flexDirection: 'row', gap: 7, marginTop: 13, paddingTop: 13, borderTopWidth: 1, borderTopColor: 'rgba(15,118,110,0.09)' },
  btn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 5, paddingVertical: 8, borderRadius: 10, borderWidth: 1.2 },
  btnText: { fontFamily: 'Domine_700Bold', fontSize: 11 },
  sent: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 8 },
  sentText: { fontFamily: 'Domine_400Regular', color: TW.slate500, fontSize: 12 },
});

// ─── Notification card ────────────────────────────────────────────────────────
function NotifCard({ item, feedback, onRead, onFeedback, fadeAnim, flashAnim }) {
  const u = URGENCY[item.urgency];
  const isUnread = !item.read;
  const flashOpacity = flashAnim ? flashAnim.interpolate({ inputRange: [0, 1], outputRange: [0, 0.18] }) : null;
  return (
    <Animated.View style={{ opacity: fadeAnim }}>
      <TouchableOpacity activeOpacity={isUnread ? 0.85 : 1} onPress={() => isUnread && onRead(item.id)}>
        <View style={[
          styles.card,
          isUnread
            ? { borderColor: u.border, backgroundColor: TW.slate50 }
            : { borderColor: 'rgba(15,118,110,0.09)', backgroundColor: TW.white },
        ]}>
          {/* Flash overlay for new alerts */}
          {flashOpacity && (
            <Animated.View
              style={[StyleSheet.absoluteFill, { backgroundColor: u.color, opacity: flashOpacity, borderRadius: 18 }]}
              pointerEvents="none"
            />
          )}
          {/* Left urgency bar — coloured gradient */}
          <LinearGradient colors={u.barColors} style={styles.urgencyBar} start={{ x: 0, y: 0 }} end={{ x: 0, y: 1 }} />

          <View style={styles.cardInner}>
            <View style={styles.cardHead}>
              {/* Monochromatic icon circle */}
              <View style={styles.iconWrap}>
                <SoundIcon iconKey={item.iconKey} size={20} />
              </View>
              <View style={styles.cardHeadText}>
                <Text style={styles.cardTitle}>{item.title}</Text>
                <View style={styles.metaRow}>
                  <Feather name="tag" size={9} color={TW.slate400} />
                  <Text style={styles.rawLabel}>{item.rawLabel}</Text>
                  <Text style={styles.sep}>·</Text>
                  <Feather name="clock" size={9} color={TW.slate400} />
                  <Text style={styles.cardTime}>{item.time}</Text>
                </View>
              </View>
              <UrgencyPill urgency={item.urgency} />
            </View>

            <Text style={styles.cardContext}>{item.context}</Text>

            <FeedbackRow
              notifId={item.id}
              rawLabel={item.rawLabel}
              value={feedback}
              onChange={onFeedback}
            />
          </View>
        </View>
      </TouchableOpacity>
    </Animated.View>
  );
}

// ─── Emergency Flash Card ─────────────────────────────────────────────────────
function EmergencyFlashCard({ data, anim, onDismiss }) {
  if (!data) return null;
  return (
    <Modal transparent animationType="none" visible statusBarTranslucent>
      <Animated.View style={[efc.overlay, { opacity: anim }]}>
        <View style={efc.card}>
          <View style={efc.iconCircle}>
            <Feather name="phone-call" size={30} color="#fff" />
          </View>
          <Text style={efc.sentLabel}>EMERGENCY MESSAGE SENT</Text>
          <Text style={efc.alertTitle}>{data.alertTitle}</Text>
          <Text style={efc.message}>
            You did not acknowledge this alert.{'\n'}An emergency message has been sent to:
          </Text>
          <Text style={efc.contactName}>{data.contactName}</Text>
          {!!data.contactPhone && (
            <Text style={efc.contactPhone}>{data.contactPhone}</Text>
          )}
          <TouchableOpacity style={efc.dismissBtn} onPress={onDismiss} activeOpacity={0.8}>
            <Feather name="check" size={15} color="#fff" style={{ marginRight: 8 }} />
            <Text style={efc.dismissText}>I'm Safe — Dismiss</Text>
          </TouchableOpacity>
        </View>
      </Animated.View>
    </Modal>
  );
}
const efc = StyleSheet.create({
  overlay: {
    flex: 1, backgroundColor: 'rgba(7,15,12,0.82)',
    alignItems: 'center', justifyContent: 'center', padding: 24,
  },
  card: {
    width: '100%', backgroundColor: '#fff',
    borderRadius: 24, alignItems: 'center',
    paddingHorizontal: 28, paddingTop: 36, paddingBottom: 32,
    borderWidth: 2, borderColor: TW.red300,
    shadowColor: TW.red600, shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.35, shadowRadius: 20, elevation: 16,
  },
  iconCircle: {
    width: 68, height: 68, borderRadius: 34,
    backgroundColor: TW.red600,
    alignItems: 'center', justifyContent: 'center',
    marginBottom: 18,
    shadowColor: TW.red600, shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.45, shadowRadius: 10, elevation: 8,
  },
  sentLabel: {
    fontFamily: 'Domine_700Bold', fontSize: 11, letterSpacing: 2.2,
    color: TW.red600, marginBottom: 10,
  },
  alertTitle: {
    fontFamily: 'Domine_700Bold', fontSize: 18, color: TW.slate900,
    textAlign: 'center', marginBottom: 14, lineHeight: 26,
  },
  message: {
    fontFamily: 'Domine_400Regular', fontSize: 14, color: TW.slate600,
    textAlign: 'center', lineHeight: 22, marginBottom: 16,
  },
  contactName: {
    fontFamily: 'Domine_700Bold', fontSize: 20, color: TW.teal700,
    textAlign: 'center', marginBottom: 4,
  },
  contactPhone: {
    fontFamily: 'Domine_400Regular', fontSize: 14, color: TW.slate500,
    textAlign: 'center', marginBottom: 20, letterSpacing: 0.5,
  },
  dismissBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    marginTop: 20, backgroundColor: TW.teal700,
    borderRadius: 14, paddingVertical: 14, paddingHorizontal: 32,
    width: '100%',
  },
  dismissText: {
    fontFamily: 'Domine_700Bold', fontSize: 15, color: '#fff', letterSpacing: 0.4,
  },
});

// ─── Main ─────────────────────────────────────────────────────────────────────
export default function HomeScreen({ profile, onLogout }) {
  const [notifications, setNotifications] = useState(INITIAL_NOTIFICATIONS);
  const [feedbacks, setFeedbacks]         = useState({});
  const [toast, setToast]                 = useState(null);
  const [scenarioRunning, setScenarioRunning] = useState(null);
  const [emergencyFlash, setEmergencyFlash]   = useState(null);
  const toastAnim = useRef(new Animated.Value(0)).current;
  const emergencyFlashAnim = useRef(new Animated.Value(0)).current;
  const fadeAnims = useRef(
    INITIAL_NOTIFICATIONS.reduce((acc, n) => { acc[n.id] = new Animated.Value(1); return acc; }, {})
  ).current;
  const flashAnims = useRef(
    INITIAL_NOTIFICATIONS.reduce((acc, n) => { acc[n.id] = new Animated.Value(0); return acc; }, {})
  ).current;
  const seenTimestamps   = useRef(new Set());
  const emergencyTimers  = useRef({});

  const unread   = notifications.filter((n) => !n.read).length;
  const critical = notifications.filter((n) => n.urgency === 'critical').length;

  // Ref used to gate REST polling when the WebSocket is healthy.
  // Updated synchronously from isWsActive state (see effect below).
  const isWsActiveRef = useRef(false);

  // ── Shared state-snapshot processor ───────────────────────────────────────
  // Called by both the WebSocket onSnapshot callback and the REST pollState
  // fallback. Identical logic; both paths produce the same notification shape.
  function processStateData(data) {
    setScenarioRunning(data.scenario_running ?? null);

    const timeline  = data.timeline  ?? [];
    const situation = data.situation ?? null;

    const newNotifs = [];
    timeline.forEach((item) => {
      const key = String(item.timestamp);
      if (seenTimestamps.current.has(key)) return;
      seenTimestamps.current.add(key);

      const id      = key;
      const urgency = situation?.urgency ?? 'low';
      fadeAnims[id] = new Animated.Value(0);
      newNotifs.push({
        id,
        urgency,
        iconKey: LABEL_ICON_MAP[item.label] ?? 'voice',
        title:   labelToTitle(situation?.flag ?? item.label),
        context: situation?.explanation ?? `Detected: ${item.label.replace(/_/g, ' ')}`,
        rawLabel: item.label,
        time:    formatElapsed(item.elapsed_s),
        read:    false,
      });
    });

    if (newNotifs.length === 0) return;

    setNotifications((prev) => [...newNotifs.slice().reverse(), ...prev]);
    newNotifs.forEach((n) => {
      Animated.timing(fadeAnims[n.id], { toValue: 1, duration: 450, useNativeDriver: true }).start();
      flashAnims[n.id] = new Animated.Value(0);
      Animated.loop(
        Animated.sequence([
          Animated.timing(flashAnims[n.id], { toValue: 1, duration: 250, useNativeDriver: true }),
          Animated.timing(flashAnims[n.id], { toValue: 0, duration: 250, useNativeDriver: true }),
        ]),
        { iterations: 5 }
      ).start();

      // Start 30-second emergency timer for high / critical alerts
      if (n.urgency === 'high' || n.urgency === 'critical') {
        emergencyTimers.current[n.id] = setTimeout(() => {
          delete emergencyTimers.current[n.id];
          setNotifications((prev) => {
            const still = prev.find((x) => x.id === n.id);
            if (still && !still.read) {
              emergencyFlashAnim.setValue(0);
              setEmergencyFlash({
                alertTitle:   n.title,
                contactName:  profile?.emergency?.contactName  || 'Emergency Contact',
                contactPhone: profile?.emergency?.contactPhone || '',
              });
              Animated.timing(emergencyFlashAnim, { toValue: 1, duration: 350, useNativeDriver: true }).start();
            }
            return prev;
          });
        }, 30000);
      }
    });
    const latest = newNotifs[newNotifs.length - 1];
    setToast(latest.title);
    Animated.sequence([
      Animated.timing(toastAnim, { toValue: 1, duration: 280, useNativeDriver: true }),
      Animated.delay(2800),
      Animated.timing(toastAnim, { toValue: 0, duration: 280, useNativeDriver: true }),
    ]).start(() => setToast(null));
  }

  // ── WebSocket + mic capture (primary path) ────────────────────────────────
  const { streamStatus, isWsActive } = useAudioStream({
    onSnapshot: processStateData,
  });

  // Keep the ref in sync so pollState() can gate without a stale closure.
  useEffect(() => {
    isWsActiveRef.current = isWsActive;
  }, [isWsActive]);

  // ── REST polling (fallback when WebSocket is not connected) ───────────────
  // pollState() is a no-op while isWsActiveRef.current is true, so it safely
  // runs on its interval regardless of WS state — no interval management needed.
  // Error handling: mirrors the original catch(_){} / !res.ok return pattern.
  useEffect(() => {
    async function pollState() {
      if (isWsActiveRef.current) return; // WS is healthy — skip REST fetch
      try {
        const res = await fetch(`${BASE_URL}/state/latest`);
        if (!res.ok) return;
        processStateData(await res.json());
      } catch (_) {}
    }

    pollState();
    const interval = setInterval(pollState, 2000);
    return () => {
      clearInterval(interval);
      Object.values(emergencyTimers.current).forEach(clearTimeout);
    };
  }, []);

  const markRead = (id) => {
    if (emergencyTimers.current[id]) {
      clearTimeout(emergencyTimers.current[id]);
      delete emergencyTimers.current[id];
    }
    setNotifications((p) => p.map((n) => n.id === id ? { ...n, read: true } : n));
  };
  const markAllRead = () => {
    Object.keys(emergencyTimers.current).forEach((id) => {
      clearTimeout(emergencyTimers.current[id]);
      delete emergencyTimers.current[id];
    });
    setNotifications((p) => p.map((n) => ({ ...n, read: true })));
  };
  const setFeedback = (id, v) => setFeedbacks((p) => ({ ...p, [id]: v }));

  return (
    <SafeAreaView style={styles.root}>
      <StatusBar barStyle="light-content" backgroundColor={TW.teal950} />

      {/* ── Contained dark header band (no bleed into content) ─ */}
      <View style={styles.headerBand}>
        {/* very subtle inner gradient, stays fully within the band */}
        <LinearGradient
          colors={[TW.teal950, TW.teal900]}
          style={StyleSheet.absoluteFill}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
        />

        <View style={styles.header}>
          <View style={styles.headerBrand}>
            <WaveformMark />
            <View style={{ marginLeft: 10 }}>
              <Text style={styles.appName}>Sound Sense</Text>
              <Text style={styles.tagline}>Sound · Context · Care</Text>
            </View>
          </View>

          {/* Mic status — non-interactive, colour-coded for listener state */}
          <MicStatus streamStatus={streamStatus} />

          {/* Logout — clearly visible white outline on dark band */}
          <TouchableOpacity style={styles.logoutBtn} onPress={onLogout} activeOpacity={0.8}>
            <Feather name="log-out" size={14} color="#FFFFFF" />
            <Text style={styles.logoutText}>Logout</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* ── Content area with very subtle light orbs ───────── */}
      <FloatingOrbs lightMode />

      {/* ── Mic permission denied — in-screen explainer ────── */}
      {streamStatus === 'denied' && (
        <TouchableOpacity style={styles.permissionBanner} onPress={() => Linking.openSettings()} activeOpacity={0.8}>
          <Feather name="mic-off" size={14} color={TW.red600} />
          <Text style={styles.permissionBannerText}>
            Microphone access needed.{' '}
            <Text style={styles.permissionBannerLink}>Open Settings</Text>
          </Text>
        </TouchableOpacity>
      )}

      {/* ── Scenario running banner ─────────────────────────── */}
      {scenarioRunning ? (
        <View style={styles.scenarioBanner}>
          <View style={styles.scenarioDot} />
          <Text style={styles.scenarioBannerText}>
            Scenario active:{' '}
            <Text style={styles.scenarioBannerName}>{scenarioRunning.replace(/_/g, ' ')}</Text>
          </Text>
        </View>
      ) : null}

      {/* ── Profile banner ──────────────────────────────────── */}
      {profile?.emergency?.contactName ? (
        <View style={styles.profileBanner}>
          <Feather name="shield" size={14} color={TW.teal700} />
          <Text style={styles.profileBannerText}>
            Emergency contact:{' '}
            <Text style={styles.profileBannerName}>{profile.emergency.contactName}</Text>
          </Text>
        </View>
      ) : null}

      {/* ── Stats strip ─────────────────────────────────────── */}
      <View style={styles.statsStrip}>
        <View style={styles.statItem}>
          <Feather name="layers" size={13} color={TW.slate400} style={{ marginBottom: 4 }} />
          <Text style={[styles.statVal, { color: TW.teal700 }]}>{notifications.length}</Text>
          <Text style={styles.statLbl}>TOTAL</Text>
        </View>
        <View style={styles.statDiv} />
        <View style={styles.statItem}>
          <Feather name="bell" size={13} color={TW.slate400} style={{ marginBottom: 4 }} />
          <Text style={[styles.statVal, { color: TW.amber600 }]}>{unread}</Text>
          <Text style={styles.statLbl}>UNREAD</Text>
        </View>
        <View style={styles.statDiv} />
        <View style={styles.statItem}>
          <Feather name="alert-triangle" size={13} color={TW.slate400} style={{ marginBottom: 4 }} />
          <Text style={[styles.statVal, { color: TW.violet600 }]}>{critical}</Text>
          <Text style={styles.statLbl}>CRITICAL</Text>
        </View>
        <View style={styles.statDiv} />
        <View style={styles.statItem}>
          <View style={styles.liveDotWrap}>
            <View style={styles.liveDot} />
          </View>
          <Text style={[styles.statVal, { color: TW.green600, fontSize: 13 }]}>LIVE</Text>
          <Text style={styles.statLbl}>STATUS</Text>
        </View>
      </View>

      {/* ── Section header ──────────────────────────────────── */}
      <View style={styles.sectionRow}>
        <View style={styles.sectionLeft}>
          <Text style={styles.sectionTitle}>Alerts</Text>
          {unread > 0 && (
            <View style={styles.unreadBubble}>
              <Text style={styles.unreadBubbleText}>{unread}</Text>
            </View>
          )}
        </View>
        <View style={styles.sectionRight}>
          <Text style={styles.feedbackHint}>Rate alerts to improve AI</Text>
          {unread > 0 && (
            <TouchableOpacity onPress={markAllRead}>
              <Text style={styles.markAll}>Clear all</Text>
            </TouchableOpacity>
          )}
        </View>
      </View>

      {/* ── List ────────────────────────────────────────────── */}
      <FlatList
        style={{ flex: 1 }}
        data={notifications}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.list}
        showsVerticalScrollIndicator={true}
        indicatorStyle="black"
        renderItem={({ item }) => (
          <NotifCard
            item={item}
            feedback={feedbacks[item.id] ?? null}
            onRead={markRead}
            onFeedback={setFeedback}
            fadeAnim={fadeAnims[item.id] ?? new Animated.Value(1)}
            flashAnim={flashAnims[item.id] ?? null}
          />
        )}
      />

      {/* ── Toast ───────────────────────────────────────────── */}
      {toast && (
        <Animated.View style={[styles.toast, { opacity: toastAnim }]}>
          <View style={[styles.toastStripe, { backgroundColor: TW.red600 }]} />
          <View style={styles.toastBody}>
            <Text style={styles.toastLabel}>NEW ALERT</Text>
            <Text style={styles.toastText} numberOfLines={1}>{toast}</Text>
          </View>
        </Animated.View>
      )}

      {/* ── Emergency Flash Card ────────────────────────────── */}
      <EmergencyFlashCard
        data={emergencyFlash}
        anim={emergencyFlashAnim}
        onDismiss={() => setEmergencyFlash(null)}
      />
    </SafeAreaView>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────
const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: TW.teal50 },

  // Dark header band — self-contained, no gradient bleed
  headerBand: {
    borderBottomLeftRadius: 24,
    borderBottomRightRadius: 24,
    overflow: 'hidden',
    marginBottom: 16,
    shadowColor: TW.teal950,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.22,
    shadowRadius: 12,
    elevation: 6,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 20,
  },
  headerBrand: { flexDirection: 'row', alignItems: 'center' },
  appName: {
    fontFamily: 'Domine_700Bold',
    color: '#FFFFFF',
    fontSize: 20,
    letterSpacing: 0.2,
  },
  tagline: {
    fontFamily: 'Domine_400Regular',
    color: 'rgba(255,255,255,0.48)',
    fontSize: 10,
    letterSpacing: 1.4,
    marginTop: 2,
  },

  // Logout — white text/icon on dark band, very easy to see
  logoutBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.28)',
    borderRadius: 11,
    paddingHorizontal: 12,
    paddingVertical: 8,
    backgroundColor: 'rgba(255,255,255,0.10)',
  },
  logoutText: {
    fontFamily: 'Domine_700Bold',
    color: '#FFFFFF',
    fontSize: 13,
  },

  permissionBanner: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    marginHorizontal: 18, marginBottom: 10,
    backgroundColor: TW.red100,
    borderRadius: 12, borderWidth: 1, borderColor: TW.red300,
    paddingHorizontal: 14, paddingVertical: 10,
  },
  permissionBannerText: { fontFamily: 'Domine_400Regular', color: TW.red600, fontSize: 13, flex: 1 },
  permissionBannerLink: { fontFamily: 'Domine_700Bold', textDecorationLine: 'underline' },

  scenarioBanner: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    marginHorizontal: 18, marginBottom: 10,
    backgroundColor: 'rgba(220,252,231,0.90)',
    borderRadius: 12, borderWidth: 1, borderColor: 'rgba(22,163,74,0.25)',
    paddingHorizontal: 14, paddingVertical: 9,
  },
  scenarioDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: TW.green600 },
  scenarioBannerText: { fontFamily: 'Domine_400Regular', color: TW.slate600, fontSize: 13 },
  scenarioBannerName: { fontFamily: 'Domine_700Bold', color: TW.green600, textTransform: 'capitalize' },

  profileBanner: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    marginHorizontal: 18, marginBottom: 14,
    backgroundColor: 'rgba(224,231,255,0.80)',
    borderRadius: 12, borderWidth: 1, borderColor: 'rgba(15,118,110,0.18)',
    paddingHorizontal: 14, paddingVertical: 10,
  },
  profileBannerText: { fontFamily: 'Domine_400Regular', color: TW.slate600, fontSize: 13 },
  profileBannerName: { fontFamily: 'Domine_700Bold', color: TW.teal700 },

  // Stats strip — plain white card, no gradient (gradient already used in header)
  statsStrip: {
    flexDirection: 'row',
    marginHorizontal: 18, marginBottom: 18,
    backgroundColor: TW.white,
    borderRadius: 18,
    borderWidth: 1, borderColor: 'rgba(15,118,110,0.10)',
    shadowColor: TW.teal900,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.07,
    shadowRadius: 8,
    elevation: 3,
  },
  statItem: { flex: 1, alignItems: 'center', paddingVertical: 14 },
  statVal:  { fontFamily: 'Domine_700Bold', fontSize: 19, lineHeight: 23 },
  statLbl:  { fontFamily: 'Domine_400Regular', color: TW.slate400, fontSize: 9, letterSpacing: 1.4, marginTop: 2 },
  statDiv:  { width: 1, backgroundColor: 'rgba(15,118,110,0.10)', marginVertical: 8 },
  liveDotWrap: { marginBottom: 4 },
  liveDot:  { width: 8, height: 8, borderRadius: 4, backgroundColor: TW.green600 },

  sectionRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingHorizontal: 18, marginBottom: 10,
  },
  sectionLeft:  { flexDirection: 'row', alignItems: 'center', gap: 8 },
  sectionRight: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  sectionTitle: { fontFamily: 'Domine_700Bold', color: TW.slate900, fontSize: 18 },
  unreadBubble: {
    backgroundColor: TW.amber600,
    borderRadius: 10, minWidth: 20, height: 20,
    alignItems: 'center', justifyContent: 'center', paddingHorizontal: 6,
  },
  unreadBubbleText: { fontFamily: 'Domine_700Bold', color: '#fff', fontSize: 11 },
  feedbackHint: { fontFamily: 'Domine_400Regular', color: TW.slate400, fontSize: 11 },
  markAll:      { fontFamily: 'Domine_700Bold', color: TW.teal700, fontSize: 12 },

  list: { paddingHorizontal: 16, paddingBottom: 34, gap: 10 },

  card: {
    borderRadius: 18, borderWidth: 1.5, overflow: 'hidden',
    flexDirection: 'row',
    shadowColor: TW.teal900, shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06, shadowRadius: 8, elevation: 2,
  },
  urgencyBar: { width: 4, alignSelf: 'stretch' },
  cardInner:  { flex: 1, padding: 15 },
  cardHead: { flexDirection: 'row', alignItems: 'flex-start', gap: 11, marginBottom: 10 },

  // Monochromatic icon circle — neutral grey background
  iconWrap: {
    width: 44, height: 44, borderRadius: 12,
    backgroundColor: TW.slate100,
    alignItems: 'center', justifyContent: 'center', flexShrink: 0,
    borderWidth: 1, borderColor: TW.slate200,
  },

  cardHeadText: { flex: 1, paddingTop: 1 },
  cardTitle: {
    fontFamily: 'Domine_700Bold',
    color: TW.slate900, fontSize: 15, lineHeight: 20, marginBottom: 4,
  },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  rawLabel: { fontFamily: 'Domine_400Regular', color: TW.slate400, fontSize: 10, letterSpacing: 0.3 },
  sep:      { color: TW.slate400, fontSize: 9 },
  cardTime: { fontFamily: 'Domine_400Regular', color: TW.slate400, fontSize: 10 },
  cardContext: { fontFamily: 'Domine_400Regular', color: TW.slate600, fontSize: 14, lineHeight: 22 },

  toast: {
    position: 'absolute', top: 60, left: 16, right: 16,
    backgroundColor: TW.white,
    borderRadius: 14, flexDirection: 'row', alignItems: 'stretch',
    borderWidth: 1.5, borderColor: TW.red300,
    shadowColor: TW.red600, shadowOffset: { width: 0, height: 5 },
    shadowOpacity: 0.22, shadowRadius: 14, elevation: 12, overflow: 'hidden',
  },
  toastStripe: { width: 5 },
  toastBody:   { flex: 1, paddingVertical: 11, paddingHorizontal: 14 },
  toastLabel: { fontFamily: 'Domine_700Bold', color: TW.red600, fontSize: 9, letterSpacing: 1.8, marginBottom: 2 },
  toastText:  { fontFamily: 'Domine_700Bold', color: TW.slate900, fontSize: 13 },
});
