# SilentSense — Frontend UI/UX Specification
### For: React Native Developer
### Version: 1.0 — Hackathon MVP

---

## 0. Read This First

This doc tells you everything you need to build the frontend. The backend is a FastAPI server
exposing REST endpoints. You poll `GET /api/v1/state/latest` every 2 seconds. That's the entire
data contract. Everything else is pure UI work.

The app must look **exceptional** in a live demo in front of judges. Every design decision below
optimizes for that moment: impressive on a phone screen being held up to a room.

---

## 1. Design Direction

### Concept: "Night Sense"

Dark-first, high-contrast, clinical precision. Think medical monitoring meets accessibility tool.
The visual language should communicate: *this is serious software that actually helps people.*

Not playful. Not pastel. Not another health-app teal gradient.

**Vibe references:** Bloomberg Terminal meets Apple Health Dark Mode meets a pro audio interface.

### Why Dark Mode

- Deaf and hard-of-hearing users often use their phone in low-light environments
- High contrast text is essential for accessibility (the core user need)
- Urgency colors (red, amber, green, purple) pop dramatically on dark backgrounds
- Demo looks dramatically better on a phone screen held up in a room

### Aesthetic Keywords

Precision. Urgency. Calm intelligence. Real-time. Trustworthy.

---

## 2. Color System

```
Background layers:
  --bg-base:        #0A0A0F   ← near-black, slight blue tint
  --bg-surface:     #111118   ← card backgrounds
  --bg-elevated:    #1A1A24   ← modals, overlays
  --bg-subtle:      #22222E   ← subtle dividers, inactive states

Text:
  --text-primary:   #F0F0F8   ← main readable text
  --text-secondary: #8888AA   ← labels, metadata, timestamps
  --text-tertiary:  #44445A   ← placeholder, disabled

Urgency (THE most important colors — use them consistently):
  --urgency-low:      #22C55E   ← green
  --urgency-medium:   #F59E0B   ← amber
  --urgency-high:     #EF4444   ← red
  --urgency-critical: #A855F7   ← purple (high contrast, alarming)

  Low glow:      rgba(34, 197, 94, 0.15)
  Medium glow:   rgba(245, 158, 11, 0.15)
  High glow:     rgba(239, 68, 68, 0.15)
  Critical glow: rgba(168, 85, 247, 0.15)

Accent:
  --accent:       #6366F1   ← indigo, used for interactive elements only
  --accent-dim:   rgba(99, 102, 241, 0.2)

Borders:
  --border-subtle:  rgba(255,255,255,0.06)
  --border-active:  rgba(255,255,255,0.12)
```

---

## 3. Typography

```
Display font:    "DM Mono" or "Space Mono" — for timestamps and technical readouts
Body font:       "DM Sans" — clean, readable, modern
Explanation:     "DM Sans Medium" at 18–22sp — the most important text on screen

Never use: Inter, Roboto, SF Pro default weights

Font sizes:
  --text-xs:    11sp   (timestamps, labels)
  --text-sm:    13sp   (secondary info)
  --text-base:  15sp   (body, timeline items)
  --text-lg:    18sp   (explanation text)
  --text-xl:    22sp   (section headers)
  --text-2xl:   28sp   (urgency label)
  --text-3xl:   36sp   (big status display)
```

---

## 4. Screen Architecture

The app has **3 screens** and **1 modal**. That's it.

```
┌─────────────────┐
│   Home Screen   │  ← Main demo screen. Most time spent here.
└────────┬────────┘
         │ tap scenario card
         ▼
┌─────────────────┐
│  Live Monitor   │  ← The "wow" screen. Runs during demo.
└────────┬────────┘
         │ tap event item
         ▼
┌─────────────────┐     ┌──────────────────┐
│ Event Detail    │     │  Compare Modal   │  ← Side-by-side raw vs contextual
└─────────────────┘     └──────────────────┘
```

---

## 5. Screen 1 — Home Screen

### Purpose
Let the user pick a scenario and start the demo. This is what judges see first.

### Layout

```
┌─────────────────────────────────┐
│  ████  SilentSense         [⚙]  │  ← Header, logo left, settings icon right
│        Sound · Context · Care   │  ← Tagline in text-secondary
├─────────────────────────────────┤
│                                 │
│  ┌───────────────────────────┐  │
│  │  [👣]  Someone Enters     │  │  ← Scenario card
│  │  Footsteps + door opening │  │
│  │  45s · Peak: MEDIUM       │  │
│  └───────────────────────────┘  │
│                                 │
│  ┌───────────────────────────┐  │
│  │  [🔔]  Alarm Escalation   │  │
│  │  Repeated beeping alarm   │  │
│  │  35s · Peak: HIGH         │  │  ← Red accent on "HIGH"
│  └───────────────────────────┘  │
│                                 │
│  ┌───────────────────────────┐  │
│  │  [💧]  Water Forgotten    │  │
│  │  Running tap, 2 minutes   │  │
│  │  120s · Peak: MEDIUM      │  │
│  └───────────────────────────┘  │
│                                 │
│  ┌───────────────────────────┐  │
│  │  [🐦]  Quiet Background   │  │
│  │  Birds only, calm space   │  │
│  │  30s · Peak: LOW          │  │
│  └───────────────────────────┘  │
│                                 │
│  ┌───────────────────────────┐  │
│  │  [👶]  Child Alert        │  │
│  │  Sudden child crying      │  │
│  │  20s · Peak: CRITICAL     │  │  ← Purple accent on "CRITICAL"
│  └───────────────────────────┘  │
│                                 │
│  ┌───────────────────────────┐  │
│  │  [💥]  Glass Break        │  │
│  │  Sudden sharp impact      │  │
│  │  15s · Peak: CRITICAL     │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘
```

### Scenario Card Design

```
Background:    --bg-surface
Border:        1px --border-subtle
Border-radius: 16px
Padding:       16px 20px
Margin:        8px 16px

Left section:
  - Icon: 40x40 container, --bg-elevated, border-radius 12px
  - Emoji or custom icon centered inside

Middle section (flex: 1):
  - Title: --text-primary, DM Sans Medium, 16sp
  - Description: --text-secondary, 13sp, 1 line

Right section:
  - Duration: "45s" in DM Mono, --text-tertiary, 11sp
  - Peak urgency badge (see badge spec below)

On press:
  - Scale animation: 0.97 spring
  - Navigate to Live Monitor screen
  - POST /scenario/start immediately
```

### Urgency Badge (used everywhere)

```
Low:      green text + green bg at 15% opacity, "LOW"
Medium:   amber text + amber bg at 15% opacity, "MEDIUM"  
High:     red text + red bg at 15% opacity, "HIGH"
Critical: purple text + purple bg at 15% opacity, "CRITICAL"

Font: DM Mono, 10sp, letter-spacing: 1.5px
Padding: 3px 8px, border-radius: 6px
```

### Header

```
Logo mark: a simple waveform icon (3 bars of different heights)
           colored with urgency-low green — suggests sound + calm
App name:  "SilentSense" — DM Sans SemiBold, 20sp, --text-primary
Tagline:   "Sound · Context · Care" — DM Mono, 11sp, --text-secondary
Settings:  gear icon, top right, navigates to (optional) config screen
```

---

## 6. Screen 2 — Live Monitor (THE Demo Screen)

This is where the hackathon is won or lost. Every element must be deliberate.

### Layout (top to bottom)

```
┌─────────────────────────────────────┐
│  ←  Someone Enters          [STOP]  │  ← Nav bar
├─────────────────────────────────────┤
│                                     │
│  ╔═══════════════════════════════╗  │
│  ║  MEDIUM                       ║  │  ← SITUATION CARD (dominant element)
│  ║                               ║  │
│  ║  Footsteps were detected      ║  │
│  ║  just before the door opened  ║  │
│  ║  — someone may have entered.  ║  │
│  ║                               ║  │
│  ║  [👣 footsteps] [🚪 door]     ║  │  ← Event chips that triggered this
│  ║                               ║  │
│  ║  ████████████░░░░  11s ago    ║  │  ← Time since flag changed
│  ╚═══════════════════════════════╝  │
│                                     │
├─────────────────────────────────────┤
│  COMPARE                    [INFO]  │  ← Section header + info icon
│                                     │
│  ┌───────────────┬─────────────────┐│
│  │ WITHOUT       │ WITH            ││  ← Side-by-side comparison
│  │ silentsense   │ silentsense     ││
│  │               │                 ││
│  │ · birds       │ 🟡 Someone may  ││
│  │ · footsteps   │   have entered  ││
│  │ · door_open   │                 ││
│  └───────────────┴─────────────────┘│
│                                     │
├─────────────────────────────────────┤
│  SOUND TIMELINE                     │  ← Section header
│                                     │
│  [birds]      0.81  ──── 2.0s       │  ← Timeline items
│  [footsteps]  0.88  ──── 8.0s       │
│  [door_open]  0.91  ──── 11.0s  ←   │  ← Arrow = triggered current flag
│                                     │
└─────────────────────────────────────┘
```

---

### 6A. Situation Card (Most Important Element)

This card takes ~40% of screen height. It must be visually dominant.

```
Container:
  Background:    urgency glow color (e.g., rgba(245,158,11,0.08) for medium)
  Border:        1.5px solid urgency color at 60% opacity
  Border-radius: 20px
  Padding:       24px
  Margin:        16px
  Shadow:        0 0 40px urgency glow color

Top row:
  Left:  Urgency badge ("MEDIUM") — large, 12sp DM Mono, letter-spacing 2px
  Right: Elapsed time since flag changed "11s ago" — DM Mono, 11sp, --text-secondary

Explanation text:
  Font:     DM Sans Medium, 20sp
  Color:    --text-primary
  Line-height: 1.5
  Margin-top: 16px
  This is the LARGEST readable text on screen

Trigger chips (below explanation):
  Small rounded pills showing which labels triggered this situation
  e.g., [👣 footsteps] [🚪 door_open]
  Background: --bg-elevated
  Font: DM Mono, 11sp
  Margin-top: 16px

Progress bar:
  Shows how long current flag has been active
  Color: urgency color
  Thin, 3px height, rounded ends
  Margin-top: 16px

Transition animation (CRITICAL):
  When flag CHANGES (flag_changed_at timestamp changes):
  1. Old card fades out + slides up: 200ms ease-in
  2. New card fades in + slides up from below: 300ms spring
  3. Urgency color of entire screen background subtly shifts
  Do NOT just swap text in place. The card transition IS the "wow moment."
```

### Urgency → Card Background Ambient

The entire screen background should subtly shift based on current urgency:

```
Low:      #0A0A0F (base, no change)
Medium:   Very subtle amber tint on bg: rgba(245,158,11,0.03)
High:     Subtle red tint: rgba(239,68,68,0.05)
Critical: Subtle purple tint + screen edge glow: rgba(168,85,247,0.08)
          Add: pulsing border animation on situation card (0.5s ease-in-out, infinite)
```

---

### 6B. Compare Panel

This is the **judge-facing differentiator panel.** It visually proves the value of the product.

```
Container:
  Background:  --bg-surface
  Border:      1px --border-subtle
  Border-radius: 16px
  Padding:     16px
  Margin:      0 16px

Two columns, equal width, divided by a subtle vertical line:

LEFT column — "Without SilentSense":
  Header: "WITHOUT" — DM Mono, 10sp, --text-tertiary, letter-spacing 1.5px
  Content: scrolling list of raw labels
    · birds
    · footsteps
    · door_open
  Each label: DM Mono, 13sp, --text-secondary, bullet point prefix
  No colors. No context. Just labels. This should look DELIBERATELY dull.

RIGHT column — "With SilentSense":
  Header: "WITH" — DM Mono, 10sp, --urgency-medium (or current urgency color), letter-spacing 1.5px
  Content: current explanation in full
  Urgency dot: colored circle before the explanation
  Font: DM Sans, 14sp, --text-primary
  This should look alive and meaningful next to the left column.

The contrast between these two columns IS the product demonstration.
```

---

### 6C. Sound Timeline

```
Container:
  Below compare panel
  Header: "SOUND TIMELINE" — DM Mono, 10sp, --text-tertiary, letter-spacing 1.5px
  Scrollable list (newest at top or bottom — choose top for demo clarity)

Timeline Item:
  Layout: [LABEL CHIP] [CONFIDENCE BAR] [TIMESTAMP]

  Label chip:
    Rounded pill, --bg-elevated background
    Label text: DM Mono, 12sp, --text-primary
    Class-specific color accent (see class colors below)
    Width: fixed 110px

  Confidence bar:
    Thin horizontal bar, 60px wide, 3px height
    Fill: class color at confidence% opacity
    e.g., 0.88 confidence = bar filled 88%
    Border-radius: 2px

  Timestamp:
    "8.0s" — DM Mono, 11sp, --text-tertiary
    Right-aligned

  Special: item that TRIGGERED current flag
    Highlighted with a small arrow "←" and urgency color text
    Subtle left border: 2px urgency color

  Animation:
    New items slide in from right, 250ms spring
    Older items shift down smoothly

Sound class colors (for chips + bars):
  footsteps:    #60A5FA  (blue)
  door_open:    #34D399  (emerald)
  door_knock:   #34D399  (emerald, same family)
  doorbell:     #34D399  (emerald, same family)
  alarm_beep:   #EF4444  (red)
  water_running:#38BDF8  (sky blue)
  birds:        #86EFAC  (light green)
  glass_break:  #F97316  (orange)
  raised_voices:#FB923C  (amber-orange)
  child_crying: #A855F7  (purple)
```

---

### 6D. Navigation Bar (Live Monitor)

```
Left:  ← back arrow + scenario name ("Someone Enters")
Right: [STOP] button
       Background: rgba(239,68,68,0.15)
       Text: #EF4444, DM Mono, 12sp
       Border: 1px rgba(239,68,68,0.3)
       Border-radius: 8px
       On press: POST /scenario/stop → navigate back to Home

Scenario progress bar (below nav bar):
  Thin 2px bar spanning full width
  Shows scenario elapsed / total duration
  Color: --accent (indigo)
  Animates forward in real time
```

---

## 7. Screen 3 — Event Detail (Optional but Nice)

Tap any timeline item to see full details. Keep it simple.

```
Bottom sheet modal (slides up 60% of screen):

Header: [CLASS ICON] door_open
        "Detected at 11.0s"

Body:
  Confidence:    [████████████████░░] 91%
  Label:         door_open
  Raw AudioSet:  "Door, Slam, Creak"  ← from backend if available
  Timestamp:     11.0s into scenario

  "This event contributed to:"
  [ARRIVAL_DETECTED]  ← urgency badge, tappable

Dismiss: swipe down or tap outside
```

---

## 8. Compare Modal (For Demo Highlight Moment)

A dedicated full-screen comparison triggered by the [INFO] button on Live Monitor.
Use this to pause and show judges the split view clearly.

```
Full screen overlay, --bg-base background

Header: "What SilentSense Does Differently"
        Close [×] top right

Left half:
  Title: "Raw Detection Only"
  Subtitle: "What a basic classifier gives you"

  Card (dull, gray):
    alarm_beep — detected
    alarm_beep — detected
    alarm_beep — detected
    (just a log of identical entries)

Right half (or below on narrow screens):
  Title: "SilentSense Context"
  Subtitle: "What you actually need to know"

  Card (urgency colored):
    🔴 HIGH
    "An alarm has sounded 3 times in
    30 seconds — this may need your
    immediate attention."

Bottom: [← Back to Live Monitor]
```

---

## 9. Polling & State Management

```javascript
// Poll every 2 seconds while scenario is running
const POLL_INTERVAL = 2000;

// What to watch for state changes:
// - situation.flag_changed_at → if changed, animate card transition
// - situation.flag → determines colors, urgency, card content
// - timeline → append new items, don't re-render whole list
// - scenario_running → if null, stop polling, show "Scenario Complete" state

// State you need in your store:
{
  scenarioRunning: string | null,
  scenarioElapsedS: number | null,
  situation: {
    flag: string,
    urgency: 'low' | 'medium' | 'high' | 'critical',
    explanation: string | null,
    flagChangedAt: number | null,
    previousFlag: string | null,
  },
  timeline: SoundEvent[],
  rawLabelsOnly: string[],      // for compare panel left column
  activeDurations: Record<string, number | null>,
  counts30s: Record<string, number>,
}
```

---

## 10. Animations — Priority List

Do these in order. Stop when you run out of time.

**Must have (demo-breaking if missing):**
1. Situation card transition when flag changes (fade out old, slide in new)
2. Urgency color shift on card border and background glow
3. Timeline items sliding in as new events arrive

**Should have (makes demo significantly better):**
4. Critical urgency: pulsing border animation on situation card
5. Scenario progress bar advancing in real time
6. Scenario card press animation (scale spring)

**Nice to have (only if time allows):**
7. Screen background ambient color shift per urgency
8. Confidence bar fill animation on new timeline items
9. Staggered load animation on home screen scenario cards

---

## 11. Scenario Complete State

When `scenario_running` returns `null`, show this on the Live Monitor:

```
Replace situation card with:

  ┌─────────────────────────────┐
  │  ✓  Scenario Complete       │
  │                             │
  │  3 situations detected      │
  │  Peak urgency: HIGH         │
  │                             │
  │  [Run Again]  [Choose New]  │
  └─────────────────────────────┘

"Run Again" → POST /scenario/start with same scenario name
"Choose New" → navigate back to Home
```

---

## 12. API Integration Reference

```
Base URL: http://[BACKEND_IP]:8000/api/v1

Endpoints you will call:

GET  /scenario/list          → populate Home Screen scenario cards
POST /scenario/start         → { "scenario": "someone_enters" }
POST /scenario/stop          → no body
GET  /state/latest           → poll every 2s (main data source)
GET  /health                 → check if backend is reachable on app load
```

**On app load:**
1. Call `GET /health` — if fails, show "Backend not connected" banner
2. Call `GET /scenario/list` — populate home screen
3. Show home screen

**On scenario start:**
1. POST `/scenario/start`
2. Navigate to Live Monitor
3. Begin polling `/state/latest` every 2s
4. Start scenario progress bar timer

**On scenario stop:**
1. POST `/scenario/stop`
2. Stop polling
3. Navigate back to Home

---

## 13. Error & Edge Case States

```
Backend unreachable:
  Show persistent top banner: "⚠ Backend offline" in amber
  Still show UI, just with empty/placeholder state

Explanation is null (LLM not responded yet):
  Show skeleton placeholder in explanation area
  "Reading environment..." in --text-tertiary

No events yet (scenario just started):
  Situation card shows: flag = NONE
  Explanation area: "Listening..." with subtle animated dots
  Timeline: empty with "No events yet" placeholder

Unknown flag from backend:
  Treat as NONE, log warning, don't crash
```

---

## 14. What NOT to Build

- No user accounts or login
- No settings screen (or keep it to just backend URL config)
- No notification system (the UI itself is the notification)
- No audio recording or microphone access
- No charts or graphs (the timeline IS the visualization)
- No onboarding flow for the demo
- No dark/light mode toggle (dark only)

---

## 15. Demo Flow Checklist

This is the exact sequence to rehearse before the demo:

1. Open app → Home Screen with 6 scenario cards visible
2. Tap "Someone Enters" → Live Monitor loads, progress bar starts
3. t=2s: birds detected, timeline shows first item, card shows "CALM_AMBIENT / low / green"
4. t=8s: footsteps appear in timeline
5. t=11s: door_open appears → **CARD TRANSITIONS** to ARRIVAL_DETECTED / medium / amber
6. Point at compare panel: "raw labels say door_open. SilentSense says someone may have entered."
7. Tap [STOP] → back to Home
8. Tap "Alarm Escalation" → show alarm_beep appearing 3 times → card goes HIGH / red
9. Optional: tap "Child Alert" → show CRITICAL / purple with pulsing border

**The card transition at step 5 is your demo money shot. Make it beautiful.**
