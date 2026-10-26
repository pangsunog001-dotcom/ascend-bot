# ============================================================
#  ASCEND: ETERNAL PATH 🌸 — Eternal Cultivation RPG
#  Everything in-game is performable in REAL life:
#  martial arts, meditation×breath fusion, chakras, herbal
#  medicine (Jun-Chen-Zuo-Shi), philosophy, history, breathwork
#  (healing / energy / sounding chi).
#  The Creator: Level ∞, all stats ∞, wealth ∞, unbeatable.
#  Self-healing: error recovery, DB auto-rebuild, 24/7 health page.
# ============================================================
import os, sqlite3, random, asyncio, time, html, logging, threading, traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
                          MessageHandler, ContextTypes, filters)
from telegram.constants import ParseMode

BOT_TOKEN   = os.environ.get("BOT_TOKEN", "")
CREATOR_ID  = int(os.environ.get("CREATOR_ID", "0") or 0)
CREATOR_NAME = "The Creator 👑"
CREATOR_LEVEL = 9223372036854775807          # sentinel → displayed as ∞
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ascend.db")
SEASON_LEN = 91 * 86400
PORT = int(os.environ.get("PORT", "8080"))   # health page port (UptimeRobot)
logging.basicConfig(level=logging.WARNING,
                    filename="ascend_errors.log", filemode="a",
                    format="%(asctime)s %(levelname)s %(message)s")

# ---------------- SELF-HEALING DATABASE ----------------
def db_conn():
    c = sqlite3.connect(DB, timeout=30)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=30000")
    return c

def init_db():
    try:
        c = db_conn()
        c.executescript("""
        CREATE TABLE IF NOT EXISTS players(
          id INTEGER PRIMARY KEY, name TEXT, gender TEXT DEFAULT '', race TEXT DEFAULT '',
          sect TEXT DEFAULT '', level INTEGER DEFAULT 1, exp INTEGER DEFAULT 0,
          points INTEGER DEFAULT 0, stamina INTEGER DEFAULT 5, charm INTEGER DEFAULT 5,
          luck INTEGER DEFAULT 5, vitality INTEGER DEFAULT 5, strength INTEGER DEFAULT 5,
          dexterity INTEGER DEFAULT 5, intelligence INTEGER DEFAULT 5, spirit INTEGER DEFAULT 5,
          qi INTEGER DEFAULT 0, coins INTEGER DEFAULT 100, herbs INTEGER DEFAULT 0,
          pills INTEGER DEFAULT 0, hp INTEGER DEFAULT 100, chakra INTEGER DEFAULT 0,
          realm_idx INTEGER DEFAULT 0, location TEXT DEFAULT '', title TEXT DEFAULT '',
          titles TEXT DEFAULT '', spouse TEXT DEFAULT '', guild TEXT DEFAULT '',
          arts TEXT DEFAULT '', last_cultivate INTEGER DEFAULT 0, last_daily INTEGER DEFAULT 0,
          last_boss INTEGER DEFAULT 0, last_guildboss INTEGER DEFAULT 0,
          streak INTEGER DEFAULT 0, season_exp INTEGER DEFAULT 0,
          exp_bonus REAL DEFAULT 1.0, disciple INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS season_stats(
          id INTEGER PRIMARY KEY, name TEXT, season INTEGER DEFAULT 1,
          season_exp INTEGER DEFAULT 0, disciple INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS guilds(
          name TEXT PRIMARY KEY, leader INTEGER, funds INTEGER DEFAULT 0, wins INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS boss(id INTEGER PRIMARY KEY, hp INTEGER, next INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
        """)
        for col, dft in [("herbs","0"),("pills","0"),("season_exp","0"),("exp_bonus","1.0"),
                         ("disciple","0"),("arts","''"),("titles","''"),("last_guildboss","0"),
                         ("streak","0"),("location","''"),("title","''"),("spouse","''"),
                         ("guild","''"),("chakra","0"),("realm_idx","0")]:
            try: c.execute(f"ALTER TABLE players ADD COLUMN {col} DEFAULT {dft}")
            except sqlite3.OperationalError: pass
        c.commit(); c.close()
    except sqlite3.DatabaseError:                 # corrupted → rebuild
        logging.error("DB corrupted — rebuilding.")
        try: os.remove(DB)
        except OSError: pass
        init_db()

init_db()

def get_p(uid):
    try:
        c = db_conn(); c.row_factory = sqlite3.Row
        r = c.execute("SELECT * FROM players WHERE id=?", (uid,)).fetchone()
        c.close(); return dict(r) if r else None
    except sqlite3.DatabaseError:
        init_db(); return get_p(uid)

def ensure_p(uid, name):
    p = get_p(uid)
    if not p:
        c = db_conn()
        c.execute("INSERT OR IGNORE INTO players(id,name) VALUES(?,?)", (uid, name))
        c.commit(); c.close(); p = get_p(uid)
    return p

def set_p(uid, **kw):
    try:
        c = db_conn(); sets = ",".join(f"{k}=?" for k in kw)
        c.execute(f"UPDATE players SET {sets} WHERE id=?", (*kw.values(), uid))
        c.commit(); c.close()
    except sqlite3.DatabaseError:
        init_db()

def season():
    c = db_conn(); r = c.execute("SELECT v FROM meta WHERE k='season_start'").fetchone()
    start = int(r[0]) if r else int(time.time())
    if not r:
        c.execute("INSERT OR REPLACE INTO meta VALUES('season_start',?)", (str(start),)); c.commit()
    c.close()
    return start, ((int(time.time()) - start) // SEASON_LEN) + 1

def exp_up(p, amount, uid):
    amount = int(amount * p.get("exp_bonus", 1.0))
    p["exp"] += amount
    set_p(uid, exp=p["exp"], season_exp=p.get("season_exp", 0) + amount)
    lvl = False
    while p["exp"] >= p["level"] * 100:
        p["exp"] -= p["level"] * 100
        p["level"] += 1; p["points"] += 3; lvl = True
    set_p(uid, level=p["level"], points=p["points"])
    return lvl, amount

REALMS = ["Qi Gatherer","Body Refiner","Foundation Builder","Core Formation","Nascent Soul",
 "Soul Formation","Void Refinement","Immortal Ascension","Saint Realm","Eternal Sovereign"]
def realm(p): return "The Creator ∞" if p["id"] == CREATOR_ID else REALMS[min(p["realm_idx"], len(REALMS)-1)]
def fmt_lvl(p): return "∞" if p["id"] == CREATOR_ID else str(p["level"])

def seed_creator():
    """The Creator: wealth & stats LIMITLESS (sentinel values, re-asserted every boot)."""
    if not CREATOR_ID: return
    c = db_conn()
    c.execute("""INSERT OR REPLACE INTO players
      (id,name,gender,race,sect,level,exp,points,stamina,charm,luck,vitality,strength,
       dexterity,intelligence,spirit,qi,coins,herbs,pills,hp,chakra,realm_idx,
       title,titles,disciple,season_exp)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
      (CREATOR_ID, CREATOR_NAME, "∞", "Creator", "None", CREATOR_LEVEL, 0, 999999,
       9999,9999,9999,9999,9999,9999,9999,9999, 999999999, 999999999, 9999, 9999,
       999999999, 7, len(REALMS)-1, "The Infinite One 👑", "Creator of Ascend ∞", 1, 0))
    _, s = season()
    c.execute("INSERT OR REPLACE INTO season_stats VALUES(?,?,?,?,-1)", (CREATOR_ID, CREATOR_NAME, s, 0))
    c.commit(); c.close()

# ---------------- DATA (all real-life performable) ----------------
RACES = {"Human":("All-rounder",{}),"Elf":("Grace & spirit",{"spirit":3,"dexterity":3}),
 "Dwarf":("Iron body",{"vitality":3,"strength":3}),"Beastkin":("Wild blood",{"strength":2,"stamina":2,"dexterity":2}),
 "Celestial":("Star-touched",{"spirit":2,"intelligence":2,"charm":2}),"Draconian":("Dragon blood",{"strength":3,"vitality":2}),
 "Sylvan":("Forestborn",{"dexterity":3,"luck":2}),"Nephilim":("Fallen light",{"strength":2,"intelligence":2,"spirit":2})}
SECTS = {"Azure Cloud":"Qi growth +10%","Iron Fist":"Martial damage +20%","Jade Alchemist":"Alchemy never fails",
 "Silent Shadow":"Dodge +15%","Golden Lotus":"Healing +25%","Storm Pavilion":"Shorter cooldowns",
 "Earth Sect":"Max HP +30%","Star Observers":"Luck +20%"}
CHAKRAS = ["Root 🔴 — survival","Sacral 🟠 — creativity","Solar 🟡 — will","Heart 🟢 — love",
 "Throat 🔵 — truth","Third Eye 🟣 — insight","Crown ⚪ — unity"]
SEEDS = ["LAM","VAM","RAM","YAM","HAM","OM","(silence)"]
ARTS = {
 "Arnis/Kali/Eskrima":("sinawali double-stick weaving, disarms, flow drills",{"crit":0.10}),
 "Panantukan":("Filipino boxing: hubud, elbow traps, low kicks",{"crit":0.08}),
 "Sikaran":("Filipino kicking art: biyakid spinning heel kick",{"dodge":0.10}),
 "Tai Chi":("slow forms, push hands, rooting — softness overcomes hardness",{"dodge":0.08}),
 "Wing Chun":("centerline theory, chain punches, Siu Nim Tao",{"first":1}),
 "Pencak Silat":("ground flow, harimau tiger stance, blade work",{"dodge":0.10}),
 "Jeet Kune Do":("intercepting fist — simplicity, directness, economy",{"first":1}),
 "Ninjutsu":("taijutsu body movement, awareness, evasion",{"dodge":0.12}),
 "Judo":("kuzushi balance-breaking, throws, osoto-gari",{"dmg2":1}),
 "Shaolin":("horse stance, iron body conditioning, 18 Lohan Hands",{"hp":30}),
 "Krav Maga":("aggressive defense, targeting, threat neutralization",{"crit":0.12})}
BOSSES = [("Forest Warden 🌳",5000),("Iron Corpse ⚰️",8000),("Flame Sovereign 🔥",12000),
 ("Nine-Headed Serpent 🐍",18000),("Heaven Devourer 🌌",30000)]
SHOP = {"Qi Pill":(50,"qi",30),"Vitality Tea":(80,"vitality",1),"Herb Bundle":(40,"herbs",3),
 "Lucky Charm":(120,"luck",1),"Iron Tonic":(100,"strength",1),"Spirit Incense":(110,"spirit",1),
 "Energy Bar":(60,"stamina",1),"Beauty Elixir":(90,"charm",1)}

# 🧘🥋 Meditation × Martial × Breath fusion (all real)
FUSIONS = [
 ("Zhan Zhuang + Reverse Abdominal Breathing (Shaolin)",
  "Stand in horse stance, knees bent, spine straight.",
  "Breathe so the belly pulls IN on inhale, OUT on exhale. 4s in — 4s hold — 6s out.",
  "5 min daily builds leg strength, calm, and breath control — how monks condition for iron shirt."),
 ("Ba Duan Jin Breathing (Eight Brocades Qigong)",
  "Perform the 8 standing brocade movements slowly.",
  "Inhale through the nose as arms rise, exhale as they press down — movement and breath as one.",
  "Search 'Ba Duan Jin' on YouTube — a 10-min morning routine thousands of years old, used in Chinese hospitals."),
 ("Moving Meditation — Tai Chi Form Breathing",
  "Flow through 3 Tai Chi moves: Ward Off, Roll Back, Press.",
  "One full breath cycle per movement. Never hold the breath; let the dantian lead.",
  "Memorize a 24-form tutorial over weeks. Proven for balance, blood pressure, stress."),
 ("Microcosmic Orbit + Golden Bridge (Daoist Neidan)",
  "Sit cross-legged, or stand with arms extended (Golden Bridge).",
  "Guide energy up the spine on inhale, down the front on exhale — circle it. Tongue touches palate.",
  "The core Daoist Neidan practice. 15 min seated, eyes closed."),
 ("Iron Breath + Standing Punch (Conditioning)",
  "Slow punch held at full extension, body tense as stone.",
  "Inhale 50%, tense hard 10s, exhale sharply through the teeth releasing halfway. 3 waves per punch.",
  "Old-school iron palm method. 5 punches per hand. Builds tendon strength."),
 ("Box Breathing + Centerline Guard (Wing Chun focus)",
  "Fighting stance, guard up, shoulders dropped.",
  "Box breathing: 4s in — 4s hold — 4s out — 4s hold.",
  "Used by soldiers and fighters. Practice 4 min; use before exams, speeches, confrontations."),
 ("Fire Breath + Dynamic Kicks (Tummo / Sikaran)",
  "10 fast alternating front kicks, then stand still.",
  "Between sets: sharp forceful nasal exhales pumping the belly (tummo / Wim Hof family).",
  "3 rounds. Warms the body, trains recovery. Skip if dizzy."),
 ("Loving-Kindness + Soft Eyes Flow (Zen)",
  "Slow shadow-boxing at 50% speed, soft gaze.",
  "Natural breath. With each exhale: 'may I be safe, may others be safe.'",
  "10 min. Bushido discipline met with Buddhist compassion — strength with gentleness."),
 ("Sea-to-Summit Breath (Ujjayi)",
  "Face the horizon — sea, sky, or mountain view.",
  "Ocean breath: slow nose inhale with soft throat 'haa', longer exhale. Draw energy from sea to summit.",
  "5–10 min outdoors combines sunlight, breath, visualization in one practice.")]

# 🌬 BREATHWORK ACADEMY — Three Paths of the Breath (all real)
BREATH_HEALING = [
 ("Pursed-Lip Breathing (Respiratory Therapy)",
  "Inhale slowly through the nose for 2 seconds. Purse lips as if whistling, exhale for 4 seconds.",
  "The pursed lips create back-pressure that keeps airways OPEN longer — the #1 technique taught for asthma and COPD worldwide.",
  "Practice 5 min, 2x daily. Use during any shortness of breath: slow, exhale LONGER than you inhale. ⚠️ Keep your rescue inhaler; this complements, never replaces, medicine."),
 ("Diaphragmatic (Belly) Breathing — Recovery Position",
  "Lie down or sit, one hand on chest, one on belly. Breathe so ONLY the belly hand moves. 4s in, 6s out.",
  "Asthmatics over-use chest muscles, which tightens the airways. Belly breathing relaxes the diaphragm and calms the nervous system.",
  "10 min before bed daily — also improves sleep. The foundation every other breath in this game builds on."),
 ("Buteyko Nasal Breathing — Air Hunger Training",
  "Breathe ONLY through the nose. Exhale, pinch nose, hold until the first definite urge to breathe (not panic), then breathe calmly 30s. Repeat 5x.",
  "Buteyko is clinically studied for asthma: nasal breathing warms, humidifies and filters air, and gentle CO₂ tolerance training reduces airway sensitivity.",
  "Once daily, seated, never force. Over weeks most practitioners report calmer, easier breathing. ⚠️ Never hold breath to distress."),
 ("Relaxed-Neck Forward Fold (Asthma Attack Posture)",
  "Sit forward, forearms on knees or a table, neck and shoulders completely loose, long slow exhales.",
  "The classic 'tripod' recovery position respiratory therapists teach — opens the chest and interrupts the panic-breathing loop.",
  "Learn it BEFORE you need it. Pair with pursed-lip breathing. ⚠️ An attack that doesn't ease = emergency services, always."),
 ("Steam & Salt-Water Airway Ritual",
  "Inhale warm steam for 5 min (bowl of hot water, towel over head), then rinse nostrils with mild saline.",
  "Steam moistens airways and loosens mucus; saline rinses clear irritants — traditional, cheap, and used by ENT doctors everywhere.",
  "Evening ritual during allergy/dust season. Real prevention beats crisis."),
]
BREATH_ENERGY = [
 ("Dantian Charge Breath (Qigong)",
  "Hands stacked on the lower dantian (3 fingers below the navel). Breathe deep into that point, 5s in, 5s out, feeling warmth build.",
  "In qigong the dantian is the body's energy battery — this breath is the first thing every qigong student is taught.",
  "3–5 min when tired. Real effect: slow deep breathing raises oxygen efficiency and settles the heart rate — genuine energy."),
 ("Kapalabhati — Skull-Shining Fire (Yoga)",
  "Seated, spine tall. Sharp forceful exhales through the nose by snapping the belly in; inhales are passive. 20 pumps = 1 round. 3 rounds.",
  "The classic pranayama energizer — practitioners feel instantly awake. It also trains the diaphragm like a workout.",
  "Morning only, on an empty-ish stomach. ⚠️ Skip if pregnant, or with uncontrolled blood pressure/heart issues."),
 ("The 4-7-8 Energy Reset",
  "Inhale through the nose 4s, hold 7s, exhale through the mouth with a soft 'whoosh' for 8s. 4 cycles.",
  "Made famous by Dr. Andrew Weil; the long exhale triggers the parasympathetic system — resets stress in minutes.",
  "Use before sleep, before exams, after conflict. One of the most practically useful breaths in the world."),
 ("Breath-of-Fire Walk (Moving Vitality)",
  "Walk briskly; inhale 4 steps, exhale 4 steps, nose only. After 2 min, extend to 6 steps in, 6 out.",
  "Rhythmic walking breath — the bridge between seated practice and real stamina. Tibetan lung-gom and martial marching both use it.",
  "10–15 min daily. Builds real aerobic breath control — your 8,000 steps just became cultivation."),
 ("Rhythmic 5-5 Breathing (HRV Coherence)",
  "Breathe exactly 5s in, 5s out — 6 breaths per minute — for 5 minutes.",
  "6 breaths/min maximizes heart-rate variability, the measurable marker of calm resilience studied in clinics worldwide.",
  "Twice daily. The most scientifically validated breath in this codex — breath as heart medicine."),
]
SOUND_QI = [
 ("🟦 XU (Hsu) — The Liver Sound (Wood)",
  "Sit or stand, hands on the liver area (right ribs). Inhale, then exhale while softly voicing 'Xuuuu' — lips rounded — feeling it vibrate the ribs.",
  "In the Six Healing Sounds (Liu Zi Jue), XU cools and smooths the liver, carrying anger out of the body.",
  "6 soft repetitions, morning. Extended voiced exhales slow the heart and release tension around the ribs."),
 ("🔴 CHUI (Chway) — The Kidney Sound (Water)",
  "Hands on lower back/kidneys. Exhale with a soft 'Chuuueee' — lips pursed — feeling warmth in the lower back.",
  "The kidney sound restores deep vitality and fearlessness in TCM — the kidneys are the 'root of qi.'",
  "6 repetitions. Warm hands on the back genuinely relax the lumbar fascia and breath."),
 ("🟢 HU (Hoo) — The Spleen Sound (Earth)",
  "Hands on the upper abdomen. Exhale a soft, round 'Huuuu' from the belly.",
  "HU settles digestion and worry — the spleen/stomach system in TCM holds overthinking.",
  "6 gentle repetitions after meals. The gut-breath connection is real vagus-nerve science."),
 ("🟡 SI (Ssss) — The Lung Sound (Metal)",
  "Arms rise on inhale, palms press down slowly on exhale while whispering a long 'Sssssss'.",
  "The LUNG sound — most important for respiratory health. Clears and expands the breath itself.",
  "6–12 repetitions. Perfect companion to Healing Breath for asthmatics (gentle, extended exhale)."),
 ("🔺 HA (Haaa) — The Heart Sound (Fire)",
  "Hands overhead then opening down. Exhale with a soft open 'Haaaaa' — releasing heat and agitation.",
  "HA releases excess heat, irritability and joylessness from the heart in the Liu Zi Jue system.",
  "6 repetitions. The open-vowel exhale is the fastest natural downshift of arousal."),
 ("⚪ XI (Shee) — The Triple-Warmer Sound (Harmony)",
  "Hands crossed overhead. Exhale with a light 'Sheeee', feeling the whole torso lengthen.",
  "XI harmonizes the three burners (upper/middle/lower body) — the closing sound that ties all qi together.",
  "6 repetitions to finish the sequence. Then sit silently 1 min and feel the vibration settle."),
 ("🔔 Mantra Vibration — OM as Qi Amplifier",
  "Inhale fully; chant a long 'OOOOMMM' — feel the hum in the chest, face and skull. 3–7 rounds.",
  "Chanting OM is studied for its effect on vagal tone and calm; the vibration itself is the 'sounding chi' — breath made audible, qi made touchable.",
  "Anytime. Works with any sacred word of your tradition — the vibration, not the word, gathers the chi."),
 ("🌊 Sea-to-Summit Sound Bath (Master Practice)",
  "Stand facing the horizon. One full breath cycle with each of the six sounds (XU-CHUI-HU-SI-HA-XI), then one OM, then 1 min of silent ujjayi.",
  "The complete Liu Zi Jue circuit fused with this game's sea-to-summit theme — all six organ systems swept with breath and sound.",
  "10 min, morning, outdoors if possible. The daily full cultivation of the sounding path."),
]

HERBAL_RECIPES = {
 "Golden Qi Formula (Jun-Chen-Zuo-Shi) 🟡":{"req":1,"herbs":3,"reward":{"qi":60},
  "real":("👑 JUN (Emperor) 34%: Turmeric (Jiang Huang) 21g + Moringa Leaf (La Mu) 13g — warms, moves Qi & Blood\n"
   "🫅 CHEN (Minister) 21%: Broccoli Sprout Powder 13g + Cabbage (Gan Lan) 8g — sulforaphane support\n"
   "🤝 ZUO (Assistant) 29%: Ginger (Sheng Jiang) 13g + Garlic (Da Suan) 8g + Onion (Yang Cong) 8g — harmonizes & protects\n"
   "🧭 SHI (Envoy) 16%: Freeze-dried Blueberries 8g + Raspberries 8g — antioxidant guide\n"
   "⚖️ Group ratio ≈ 1.618 : 1 : 1.618 : 1\n"
   "METHOD: dry all at 40–50°C, grind fine, weigh each, blend, store airtight away from light. 1 tsp in warm water daily.")},
 "Phlegm-Expelling Pills 🌬":{"req":3,"herbs":3,"reward":{"pills":2},
  "real":("Dried tangerine peel (Chen Pi) + ginger powder + licorice root (Gan Cao). Grind equal parts,\n"
   "bind with raw honey into 5g pills (the classic imperial 'wan' honey method), shade-dry 2 days.\n"
   "1 pill 2x daily with warm water when phlegmy.")},
 "Fever-Release Formula 🌡":{"req":5,"herbs":2,"reward":{"coins":80},
  "real":("Elderflower + yarrow + peppermint: steep 1 tsp blend in hot water 10 min covered.\n"
   "Drink hot, wrap in blankets, sweat it out (diaphoretic 'release the exterior' method). Rest & hydrate.\n"
   "⚠️ Persistent high fever = see a doctor. This aids mild fevers only.")},
 "Herbal Energy Bars 🍫":{"req":4,"herbs":2,"reward":{"stamina":2},
  "real":("Blend: 1 cup dates + 1/2 cup oats + 1/2 cup mixed nuts + dried fruit + 1 tsp turmeric\n"
   "+ pinch of black pepper (piperine multiplies curcumin absorption ~2000% — the Envoy guides the Emperor!)\n"
   "+ pinch of sea salt. Press into a pan, chill 2 hours, cut into 10 bars.")},
 "Anti-High-BP Formula 🔻":{"req":7,"herbs":4,"reward":{"vitality":2},
  "real":("Celery seed + aged garlic + hibiscus + beetroot powder — all studied for blood pressure.\n"
   "Simmer 1 tsp blend 10 min or 1 tsp powder in water, morning & evening.\n"
   "⚠️ Never stop prescribed medication; work WITH your doctor.")},
 "Anti-Low-BP Formula 🔺":{"req":7,"herbs":4,"reward":{"strength":2},
  "real":("Licorice root (max 2 weeks) + ginger + cinnamon bark + ginseng/eleuthero + pinch of kelp/dulse\n"
   "(sea minerals). Decoct 1 tsp in 2 cups water, drink warm in the morning.\n"
   "⚠️ Fainting = see a doctor.")},
 "Sea-to-Mountain Multimineral Tonic 🌊⛰":{"req":10,"herbs":5,"reward":{"spirit":2,"qi":50},
  "real":("SEA: dried kelp + Irish moss • LOWLAND: moringa + turmeric + ginger\n"
   "MOUNTAIN: nettle leaf + pine needles • ORCHARD: apple peel + berries\n"
   "Simmer kelp+nettle+pine in 3 cups water 20 min, strain, stir in turmeric, berry powder + honey.\n"
   "Wild nutrition — food as medicine, from sea to summit.")}}

PHILOSOPHY = [
 ("🇨🇳 Daoism — Laozi","Wu wei: act without forcing. Water defeats stone by yielding. Flow, and act at the right moment."),
 ("🇨🇳 Confucianism","Ren (benevolence) + Li (propriety): cultivation begins with daily conduct. Learn from everyone."),
 ("🇮🇳 Vedanta","Tat tvam asi — 'You are That.' Self-inquiry: ask 'who am I?' beneath every label."),
 ("🇮🇳 Buddhism","Four Noble Truths & Eightfold Path: suffering ends by training view, speech, effort, mindfulness."),
 ("🇯🇵 Zen — Dogen","Shikantaza: just sitting. Chop wood, carry water — wash the dishes to wash the dishes."),
 ("🇯🇵 Bushido — Musashi","Live each day fully prepared. 'Do nothing which is of no use.' Discipline over talent."),
 ("🇬🇷 Stoicism","Dichotomy of control: suffering comes from wanting the uncontrollable. Pre-imagine hardships each morning."),
 ("🇬🇷 Socratic Method","The unexamined life is not worth living. Wisdom begins by knowing you know nothing."),
 ("🇬🇷 Epicureanism","Pleasure = absence of pain and fear. Simple bread and friendship outweigh luxury and anxiety."),
 ("🇹🇷 Sufism — Rumi","Polish the mirror of the heart through remembrance. 'The wound is where the Light enters you.'"),
 ("🕌 Islamic Philosophy — Al-Ghazali","Purification of the heart (tazkiyah) as the path to knowledge; reason and revelation as two wings."),
 ("🇮🇱 Jewish Wisdom","Tikkun olam: repair the world through action. 'Who is wise? One who learns from every person.'"),
 ("✝️ Christian Monasticism","Lectio divina — slow sacred reading. Desert Fathers' silence. Faith seeking understanding."),
 ("🇳🇬 Yoruba Ifá","Iwa pele — good character is highest. Destiny is chosen before birth and walked with effort."),
 ("🇪🇬 Kemetic Ma'at","Truth, balance, order, justice. The 42 Declarations — a daily moral self-audit."),
 ("🇿🇦 Ubuntu","'A person is a person through other persons.' I am because we are."),
 ("🇵🇭 Kapwa","Shared identity — the self includes the other. Bayanihan spirit; align inner loob with action."),
 ("🇲🇽 Nahuatl Philosophy","Nepantla: living on the threshold between worlds. Root the heart in community."),
 ("🇵🇪 Andean Sumak Kawsay","Buen vivir: wellbeing measured in relationships with Pachamama, community, and time."),
 ("🇰🇷 Hwarang Code","Loyalty, courage, honor, compassion, justice — warrior ethics bound to Seon meditation."),
 ("🇮🇷 Zoroastrianism","Good thoughts, good words, good deeds. A daily battle between truth and lie."),
 ("🇬🇷 Hermeticism","As above, so below. Know thyself and you know the universe."),
 ("🇮🇳 Charvaka","The honest skeptic: this world is real, the body is your instrument, live well without superstition.")]

CULTIVATION_HISTORY = [
 ("🇨🇳 Daoist Neidan (c. 4th c. BC)","Refining jing→qi→shen via breath and the microcosmic orbit — still taught today."),
 ("🇨🇳 Shaolin (495 AD)","Bodhidharma taught sleepy monks the 18 Lohan Hands. Emperors died of mercury elixirs — a warning against shortcuts."),
 ("🇮🇳 Yoga & Tapasya","Patanjali's 8 limbs. Tapas — inner heat of discipline — refines the body. Real pranayama science."),
 ("🇯🇵 Shugendō","Yamabushi trained under waterfalls; the 1000-day Kaihōgyō marathon was completed by only 46 men in 400 years."),
 ("🇵🇭 Babaylan Tradition","Filipino shamans healing with herbs, breath and trance — surviving today in hilot."),
 ("🇮🇩🇲🇾 Ilmu Kebatinan","Javanese inner-power cultivation: fasting, breath, tenaga dalam within pencak silat."),
 ("🇬🇷 Greek Askēsis","Milo of Croton carried a calf daily until it was a bull — the first progressive-overload parable."),
 ("🇪🇬 Asklepion Temples","Healing temples of ritual sleep, diet, sacred bathing — the first wellness centers, c. 3000 BC."),
 ("🇬🇧 Druidic Training","20 years of oral training in memory, poetry, herbal lore, astronomy."),
 ("🇷🇺 Slavic Banya","Volkhvy priest-healers and sweat-lodge purification — still practiced today."),
 ("🇲🇽🇵🇪 Mexica & Inca","Temazcal sweat lodges purified warriors; tlamatinime taught temperance."),
 ("🇨🇳 Modern Qi Science","Qigong in hospitals; breath practices validated by HRV research. Ancients meet the lab."),
 ("🌍 Your Lineage","Every technique in this game traces to real lineages. You continue a 5,000-year human project.")]

QUIZ = [("Which country birthed Daoism?","China"),("Ma'at is from which civilization?","Egypt"),
 ("Patanjali codified which practice?","Yoga"),("Shaolin temple is in which country?","China"),
 ("'Know thyself' was carved at which temple?","Delphi"),("Ubuntu philosophy comes from?","Africa"),
 ("Musashi wrote which book?","The Book of Five Rings"),("The microcosmic orbit belongs to?","Daoist Neidan"),
 ("Hibiscus tea traditionally helps with?","Blood pressure"),("Turmeric's active compound is?","Curcumin")]

WISDOM = ["The best fighter is never angry. — Laozi","You have power over your mind, not outside events. — Marcus Aurelius",
 "The wound is the place where the Light enters you. — Rumi","He who conquers himself is the mightiest warrior. — Confucius",
 "A journey of a thousand li begins with a single step. — Laozi","Know thyself. — Delphi","I am because we are. — Ubuntu",
 "Do nothing which is of no use. — Musashi","What you seek is seeking you. — Rumi"]

REAL_LIFE_GUIDE = ("🏋️ *Real-Life Body Refinement Guide*\n"
 "🌅 DAILY: 10 min meditation (/meditate teaches methods) • 20 min sunlight • 2–3L water • 8,000+ steps\n"
 "🌬 BREATH: asthma/hard breathing? → /breathe daily • low energy? → /energybreath • deepest qi? → /soundqi (Six Healing Sounds)\n"
 "💪 STRENGTH 3x/week: horse stance 2min×3, push-ups, squats, pull-ups — +1 rep each session\n"
 "🥋 MARTIAL ARTS: drill your /arts for real — sinawali with broomsticks, Siu Nim Tao slow, Tai Chi 24-form\n"
 "🧘 CHAKRAS: 7-week program, one chakra/week — breathe into it, visualize its color, chant its seed syllable (LAM/VAM/RAM/YAM/HAM/OM/silence)\n"
 "🌿 HERBALISM: start with the Golden Qi Formula (/herbacademy) — kitchen ingredients only\n"
 "🥗 EAT: whole foods, 80% full (hara hachi bu) • 😴 SLEEP 7–9h — the body refines itself in sleep\n"
 "⚖️ GOLDEN RULE: 1% daily improvement compounds into a transformed human in 1 year.")

def kb_grid(options, prefix, cols=2):
    rows = [[InlineKeyboardButton(o[:24], callback_data=f"{prefix}_{i}")] for o in options]
    return InlineKeyboardMarkup([rows[i:i+cols] for i in range(0, len(rows), cols)])

# ---------------- SELF-HEALING ERROR WRAPPER ----------------
def heal(fn):
    """Catches ANY error, logs it, tells the user gently — bot keeps running 24/7."""
    async def wrap(update, ctx):
        try:
            return await fn(update, ctx)
        except Exception:
            logging.error(traceback.format_exc())
            try:
                if update and update.effective_message:
                    await update.effective_message.reply_text(
                        "🌫 The qi wavered for a moment… the heavens stabilized. Please try again.")
            except Exception: pass
    return wrap

async def err_handler(update, ctx):
    logging.error("Unhandled: " + traceback.format_exc())
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text("🌫 A ripple in the path… try again.")
    except Exception: pass

# ---------------- CORE COMMANDS ----------------
@heal
async def start(update, ctx):
    u = update.effective_user; p = ensure_p(u.id, u.first_name)
    if p["gender"]:
        await update.effective_message.reply_text(
            f"🌸 *Welcome back, {u.first_name}!*\n{realm(p)} • Lv.{fmt_lvl(p)} • 💰{p['coins']} • 🌿{p['herbs']} • 💊{p['pills']}\n\n/help — all commands • /reallife — real training",
            parse_mode=ParseMode.MARKDOWN); return
    await update.effective_message.reply_text(
        "🌸 *ASCEND: ETERNAL PATH* 🌸\nA slice-of-life cultivation world — no ending, play for eternity.\nEverything here is real-life learnable: martial arts, breath, herbs, wisdom.\n\n*Choose your essence:*",
        reply_markup=kb_grid(["Male","Female","Spirit"], "gender", 3), parse_mode=ParseMode.MARKDOWN)

@heal
async def gender_cb(update, ctx):
    q = update.callback_query; await q.answer()
    set_p(q.from_user.id, gender=q.data.split("_")[1])
    await q.edit_message_text(f"Essence: *{q.data.split('_')[1]}*\nNow choose your *bloodline:*",
        reply_markup=kb_grid(list(RACES), "race"), parse_mode=ParseMode.MARKDOWN)

@heal
async def race_cb(update, ctx):
    q = update.callback_query; await q.answer()
    r = q.data.split("_")[1]; set_p(q.from_user.id, race=r)
    await q.edit_message_text(f"Bloodline: *{r}* — {RACES[r][0]}\n(+stat bonus at sect choice)\nNow choose your *sect:*",
        reply_markup=kb_grid(list(SECTS), "sect"), parse_mode=ParseMode.MARKDOWN)

@heal
async def sect_cb(update, ctx):
    q = update.callback_query; await q.answer()
    u = q.from_user; p = ensure_p(u.id, u.first_name)
    s = q.data.split("_")[1]
    kw = {stat: p[stat] + amt for stat, amt in RACES[p["race"]][1].items()}
    set_p(u.id, sect=s, **kw)
    await q.edit_message_text(
        f"✨ *Character Created!* {p['gender']} • {p['race']} • {s} Sect\n"
        f"Sect perk: {SECTS[s]}\n\nBegin: /cultivate /meditate /breathe /forage /arts /herbacademy /reallife\n/help for everything.",
        parse_mode=ParseMode.MARKDOWN)

@heal
async def help_cmd(update, ctx):
    await update.effective_message.reply_text(
"🌸 *ASCEND — ALL COMMANDS*\n"
"👤 /profile /stats /up <stat> <n>\n"
"⚡ /cultivate /meditate /fusion <n> /daily\n"
"🌬 /breathwork /breathe /energybreath /soundqi — three real breath paths\n"
"🌳 /forage /alchemy /shop /quiz /memory\n"
"🥋 /arts /train <n> /myarts — REAL martial arts\n"
"🌿 /herbacademy /formulas /brewherb <n> — REAL herbal medicine\n"
"📚 /philosophy <n> /codex <n> /wisdom /history\n"
"🏋️ /reallife — real body refinement plan\n"
"⚔️ /duel @user /boss /guildboss /trial /challengecreator\n"
"🏯 /guild create|join|leave|info|donate <amt> /guildwar\n"
"💍 /propose @user /divorce /hug /gift /chat <msg>\n"
"🏆 /top global|country|region|city /setlocation /halloffame /season_info\n"
"👑 /creator /disciples /event /settitle <title>", parse_mode=ParseMode.MARKDOWN)

@heal
async def profile(update, ctx):
    u = update.effective_user; p = ensure_p(u.id, u.first_name); _, s = season()
    if p["id"] == CREATOR_ID:
        await update.effective_message.reply_text(
 "👑 *THE CREATOR*\n∞ • Creator • The Creator ∞\n"
 "Level: ∞ • EXP: ∞/∞ • 💰 Coins: ∞\n"
 "🌿 Herbs: ∞ • 💊 Pills: ∞ • ⚡ Qi: ∞ • ❤️ HP: ∞\n"
 "Chakra 7/7: Crown ⚪ — unity (all chakras: ∞)\n"
 "STAMINA ∞ • CHARM ∞ • LUCK ∞ • VITALITY ∞\n"
 "STRENGTH ∞ • DEXTERITY ∞ • INTELLIGENCE ∞ • SPIRIT ∞\n"
 "💍 Beyond bonds • 🏯 Above guilds • 📍 Everywhere and nowhere\n"
 "🎖 The Infinite One 👑\n"
 "*No mortal — not even a disciple — can compare.*", parse_mode=ParseMode.MARKDOWN); return
    await update.effective_message.reply_text(
 f"👤 *{u.first_name}* {p['title']}\n{p['gender']} {p['race']} • {p['sect']} Sect • {realm(p)}\n"
 f"Lv.{fmt_lvl(p)} • EXP {p['exp']}/{p['level']*100} • 💰{p['coins']}\n"
 f"🌿{p['herbs']} 💊{p['pills']} • Qi {p['qi']} • HP {p['hp']}\n"
 f"Chakra {p['chakra']}/7: {CHAKRAS[min(p['chakra'],6)]}\n"
 f"💍 {p['spouse'] or 'Single'} • 🏯 {p['guild'] or 'None'}\n"
 f"📍 {p['location'] or 'Unset (/setlocation)'}\n"
 f"Season {s} EXP: {p['season_exp']} • Streak 🔥{p['streak']}"
 + ("\n👑 *DISCIPLE OF THE CREATOR*" if p["disciple"] else ""), parse_mode=ParseMode.MARKDOWN)

@heal
async def stats_cmd(update, ctx):
    p = ensure_p(update.effective_user.id, update.effective_user.first_name)
    if p["id"] == CREATOR_ID:
        await update.effective_message.reply_text(
            "📊 *THE CREATOR'S STATS*\nAll stats: ∞ — beyond measurement.\nPoints: ∞ (nothing left to buy — he owns everything).",
            parse_mode=ParseMode.MARKDOWN); return
    bars = "\n".join(f"{k}: {v}" for k, v in
        [("Stamina",p["stamina"]),("Charm",p["charm"]),("Luck",p["luck"]),("Vitality",p["vitality"]),
         ("Strength",p["strength"]),("Dexterity",p["dexterity"]),("Intelligence",p["intelligence"]),("Spirit",p["spirit"])])
    await update.effective_message.reply_text(f"📊 *Stats* — Points: {p['points']}\n{bars}\n"
        + (f"Spend with /up <stat> <n>" if p["points"] else "Level up to earn points (+3 each)."), parse_mode=ParseMode.MARKDOWN)

STAT_KEYS = ["stamina","charm","luck","vitality","strength","dexterity","intelligence","spirit"]
@heal
async def up_cmd(update, ctx):
    u = update.effective_user; p = ensure_p(u.id, u.first_name)
    if p["id"] == CREATOR_ID:
        await update.effective_message.reply_text("👑 The Creator's stats are already ∞ — there is nothing left to raise."); return
    if not ctx.args or ctx.args[0] not in STAT_KEYS:
        await update.effective_message.reply_text(f"Usage: /up <{'|'.join(STAT_KEYS)}> <amount>"); return
    n = int(ctx.args[1]) if len(ctx.args) > 1 and ctx.args[1].isdigit() else 1
    n = min(n, p["points"])
    if n <= 0: await update.effective_message.reply_text("No points available."); return
    set_p(u.id, points=p["points"]-n, **{ctx.args[0]: p[ctx.args[0]]+n})
    await update.effective_message.reply_text(f"⬆️ {ctx.args[0]} +{n}! Points left: {p['points']-n}")

@heal
async def cultivate(update, ctx):
    u = update.effective_user; p = ensure_p(u.id, u.first_name)
    now = int(time.time()); cd = 300 if p["sect"] == "Storm Pavilion" else 600
    rem = cd - (now - p["last_cultivate"])
    if rem > 0: await update.effective_message.reply_text(f"🧘 Qi still circulating… {rem//60}m {rem%60}s."); return
    gain = 10 + p["level"]*2 + p["spirit"] + p["qi"]//10
    if p["sect"] == "Azure Cloud": gain = int(gain*1.1)
    if random.random() < p["luck"]/200: gain *= 2
    lvl, _ = exp_up(p, gain//2, u.id)
    set_p(u.id, qi=p["qi"]+gain, last_cultivate=now)
    msg = f"⚡ You gather *{gain} Qi!* (total {p['qi']+gain})"
    if p["chakra"] < 7 and p["qi"] >= (p["chakra"]+1)*100:
        set_p(u.id, chakra=p["chakra"]+1)
        msg += (f"\n🔆 *CHAKRA OPENED:* {CHAKRAS[p['chakra']]}\n"
                f"Real practice: breathe into that center daily, chant '{SEEDS[p['chakra']]}' — see /reallife.")
    if lvl: msg += f"\n🎉 *LEVEL UP!* Lv.{fmt_lvl(p)} — +3 points (/up)"
    await update.effective_message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

@heal
async def meditate(update, ctx):
    u = update.effective_user; p = ensure_p(u.id, u.first_name)
    title, posture, breath, real = random.choice(FUSIONS)
    qi = 15 + p["spirit"]*2 + p["level"]
    lvl, _ = exp_up(p, 30, u.id); set_p(u.id, qi=p["qi"]+qi)
    msg = (f"🧘🥋 *Meditation–Martial Fusion*\n*{title}*\n\n🥋 {posture}\n🌬 {breath}\n\n"
           f"💡 *Do this for real today:* {real}\n\n⚡ +{qi} Qi • +30 EXP")
    if p["chakra"] < 7 and p["qi"] >= (p["chakra"]+1)*100:
        set_p(u.id, chakra=p["chakra"]+1); msg += f"\n🔆 *CHAKRA OPENED:* {CHAKRAS[p['chakra']]}"
    if lvl: msg += "\n🎉 LEVEL UP!"
    await update.effective_message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

@heal
async def fusion(update, ctx):
    if ctx.args and ctx.args[0].isdigit():
        i = int(ctx.args[0]) - 1
        if 0 <= i < len(FUSIONS):
            t, po, br, rl = FUSIONS[i]
            p = ensure_p(update.effective_user.id, update.effective_user.first_name)
            lvl, _ = exp_up(p, 10, update.effective_user.id)
            await update.effective_message.reply_text(
                f"🧘🥋 *{t}*\n\n🥋 Posture: {po}\n🌬 Breath: {br}\n💡 Real-life: {rl}\n(+10 EXP)",
                parse_mode=ParseMode.MARKDOWN); return
    await update.effective_message.reply_text(
        "🧘🥋 *Fusion Codex — Meditation × Martial × Breath*\n" +
        "\n".join(f"{i+1}. {t}" for i,(t,_,_,_) in enumerate(FUSIONS)) +
        "\n\n/meditate — random session • /fusion <number> — deep dive", parse_mode=ParseMode.MARKDOWN)

# ---------------- 🌬 BREATHWORK ACADEMY ----------------
@heal
async def breathe(update, ctx):
    """Healing breath for asthma & difficult breathing — real respiratory therapy."""
    u = update.effective_user; p = ensure_p(u.id, u.first_name)
    title, how, why, real = random.choice(BREATH_HEALING)
    qi = 10 + p["spirit"]  # gentle gains — healing, not power
    lvl, _ = exp_up(p, 30, u.id)
    set_p(u.id, qi=p["qi"]+qi)
    await update.effective_message.reply_text(
        f"🫁 *Healing Breath — for difficult breathing & asthma*\n\n*{title}*\n\n🌬 {how}\n\n💡 Why it works: {why}\n\n🏥 *Real-life:* {real}\n\n⚡ +{qi} Qi • +30 EXP\n(Breathing easier IS cultivation — the gentlest path is still a path.)"
        + ("\n🎉 LEVEL UP!" if lvl else ""), parse_mode=ParseMode.MARKDOWN)

@heal
async def energybreath(update, ctx):
    """Energy breathing — vitality & stamina techniques."""
    u = update.effective_user; p = ensure_p(u.id, u.first_name)
    title, how, why, real = random.choice(BREATH_ENERGY)
    qi = 15 + p["spirit"]*2 + p["level"]
    lvl, _ = exp_up(p, 35, u.id)
    set_p(u.id, qi=p["qi"]+qi, stamina=p["stamina"] + (1 if random.random() < 0.2 else 0))
    await update.effective_message.reply_text(
        f"⚡🌬 *Energy Breath*\n\n*{title}*\n\n🌬 {how}\n\n💡 Why it works: {why}\n\n🏋️ *Real-life:* {real}\n\n⚡ +{qi} Qi • +35 EXP"
        + ("\n🎉 LEVEL UP!" if lvl else ""), parse_mode=ParseMode.MARKDOWN)

@heal
async def soundqi(update, ctx):
    """Sounding chi — Six Healing Sounds & vibrational cultivation."""
    u = update.effective_user; p = ensure_p(u.id, u.first_name)
    title, how, why, real = random.choice(SOUND_QI)
    qi = 20 + p["spirit"]*2 + p["level"]  # strongest qi gain — sound cultivates spirit
    lvl, _ = exp_up(p, 40, u.id)
    set_p(u.id, qi=p["qi"]+qi)
    msg = (f"🔔 *Sounding Chi*\n\n*{title}*\n\n🌬 {how}\n\n💡 Lineage: {why}\n\n🎵 *Real-life:* {real}\n\n⚡ +{qi} Qi • +40 EXP")
    if p["chakra"] < 7 and p["qi"] >= (p["chakra"]+1)*100:
        set_p(u.id, chakra=p["chakra"]+1)
        msg += f"\n🔆 *CHAKRA OPENED:* {CHAKRAS[p['chakra']]}\nSound + breath is the classic chakra opener — chant its seed syllable too!"
    if lvl: msg += "\n🎉 LEVEL UP!"
    await update.effective_message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

@heal
async def breathwork(update, ctx):
    """Index of all three breath paths."""
    await update.effective_message.reply_text(
        "🌬 *BREATHWORK ACADEMY — Three Paths of the Breath*\n\n"
        "🫁 /breathe — *Healing Breath:* real respiratory-therapy techniques for asthma & hard breathing (pursed-lip, belly breathing, Buteyko, recovery posture)\n\n"
        "⚡ /energybreath — *Energy Breath:* vitality & stamina (dantian charging, kapalabhati, 4-7-8, walking breath, HRV coherence)\n\n"
        "🔔 /soundqi — *Sounding Chi:* gather qi through vibration — the Daoist Six Healing Sounds + OM (strongest Qi gain in the game)\n\n"
        "⚠️ Asthma note inside /breathe: these techniques are real pulmonary rehabilitation, but they support — never replace — your inhaler and doctor.",
        parse_mode=ParseMode.MARKDOWN)

@heal
async def daily(update, ctx):
    u = update.effective_user; p = ensure_p(u.id, u.first_name)
    today = int(time.time()) // 86400
    if p["last_daily"] // 86400 == today:
        await update.effective_message.reply_text("🌅 Already claimed. Real-life reminder: sleep 7–9h tonight — that IS cultivation."); return
    streak = p["streak"] + 1 if today - p["last_daily"]//86400 == 1 else 1
    coins = (50 + min(streak,30)*10) * (2 if p["sect"] == "Golden Lotus" else 1)
    lvl, _ = exp_up(p, 50, u.id)
    set_p(u.id, last_daily=int(time.time()), coins=p["coins"]+coins, streak=streak)
    await update.effective_message.reply_text(
        f"🌅 *Daily cultivation!* +{coins}💰 • Streak 🔥{streak}\n💡 Real-life: today — walk 8k steps, eat to 80% full, 10 min breathwork." + ("\n🎉 LEVEL UP!" if lvl else ""))

@heal
async def forage(update, ctx):
    u = update.effective_user; p = ensure_p(u.id, u.first_name)
    n = 1 + random.randint(0, 2 + p["luck"]//5)
    zone = random.choice(["seashore 🌊 (kelp, Irish moss)","lowland fields 🌾 (moringa, turmeric)",
                          "mountain slopes ⛰ (nettle, pine)","orchard valleys 🍒 (berries, apple peel)"])
    lvl, _ = exp_up(p, 15, u.id); set_p(u.id, herbs=p["herbs"]+n)
    await update.effective_message.reply_text(
        f"🌿 You forage the {zone}: +{n} herbs!\n💡 Every herb here is a REAL plant — see /herbacademy to use them in life.")

@heal
async def alchemy(update, ctx):
    u = update.effective_user; p = ensure_p(u.id, u.first_name)
    if p["herbs"] < 2: await update.effective_message.reply_text("Need 2 🌿 — /forage first!"); return
    set_p(u.id, herbs=p["herbs"]-2)
    fail = (random.random() > 0.7 + p["intelligence"]/200) and p["sect"] != "Jade Alchemist"
    if fail:
        lvl, _ = exp_up(p, 20, u.id)
        await update.effective_message.reply_text("💥 The cauldron explodes! Herbs lost — but you *learned*. +20 EXP" + ("\n🎉 LEVEL UP!" if lvl else ""))
    else:
        lvl, _ = exp_up(p, 40, u.id); set_p(u.id, pills=p["pills"]+1)
        await update.effective_message.reply_text("⚗️ *Success!* +1 💊 pill. Real pill-making methods: /herbacademy" + ("\n🎉 LEVEL UP!" if lvl else ""))

@heal
async def shop(update, ctx):
    p = get_p(update.effective_user.id)
    await update.effective_message.reply_text(f"🛒 *Shop* — your coins: {p['coins']}",
        reply_markup=kb_grid([f"{n} — {c}💰" for n,(c,_,_) in SHOP.items()], "buyn", 2),
        parse_mode=ParseMode.MARKDOWN)

@heal
async def buy_cb(update, ctx):
    q = update.callback_query; await q.answer()
    p = ensure_p(q.from_user.id, q.from_user.first_name)
    idx = int(q.data.split("_")[1]); n = list(SHOP)[idx]; c, k, v = SHOP[n]
    if p["coins"] < c: await q.answer("Not enough coins!", show_alert=True); return
    set_p(q.from_user.id, coins=p["coins"]-c, **{k: p[k]+v})
    await q.answer(f"Bought {n}! {k} +{v}", show_alert=True)

@heal
async def quiz(update, ctx):
    q, a = random.choice(QUIZ)
    ctx.chat_data["quiz"] = (a, update.effective_user.id)
    await update.effective_message.reply_text(f"🧠 *Quiz:* {q}\nFirst correct answer wins 30 EXP — type it!")

@heal
async def quiz_answer(update, ctx):
    if "quiz" not in ctx.chat_data: return
    a, uid = ctx.chat_data["quiz"]
    if update.effective_user.id == uid: return
    if a.lower() in (update.effective_message.text or "").lower():
        p = ensure_p(update.effective_user.id, update.effective_user.first_name)
        lvl, _ = exp_up(p, 30, update.effective_user.id)
        del ctx.chat_data["quiz"]
        await update.effective_message.reply_text(f"✅ Correct, {update.effective_user.first_name}! +30 EXP" + ("\n🎉 LEVEL UP!" if lvl else ""))

@heal
async def memory(update, ctx):
    u = update.effective_user; ensure_p(u.id, u.first_name)
    seq = "".join(random.choice("🔺🟦⭐🌙🔥") for _ in range(5))
    ctx.chat_data[f"mem{u.id}"] = seq
    await update.effective_message.reply_text(f"🧠 Memorize — 8 seconds:\n{seq}")
    await asyncio.sleep(8)
    ctx.chat_data[f"memask{u.id}"] = True
    await update.effective_message.reply_text(f"{u.first_name} — now type the sequence!")

@heal
async def mem_answer(update, ctx):
    uid = update.effective_user.id
    if not ctx.chat_data.get(f"memask{uid}"): return
    seq = ctx.chat_data.pop(f"mem{uid}"); ctx.chat_data.pop(f"memask{uid}")
    p = ensure_p(uid, update.effective_user.first_name)
    if (update.effective_message.text or "").strip() == seq:
        lvl, _ = exp_up(p, 40, uid)
        await update.effective_message.reply_text("🧠 *Perfect memory!* +40 EXP" + ("\n🎉 LEVEL UP!" if lvl else ""))
    else:
        await update.effective_message.reply_text(f"❌ It was: {seq} — /memory to retry!")

def atk_power(p):
    base = p["strength"]*3 + p["dexterity"]*2 + p["level"]*5
    mult, first, dodge = 1.0, 0, 0.05
    if p["sect"] == "Iron Fist": mult *= 1.2
    for a in (p["arts"] or "").split("|"):
        if a in ARTS:
            for k, v in ARTS[a][1].items():
                if k == "dmg2": mult = 2
                elif k == "dodge": dodge += v
                elif k == "first": first = 1
    if p["sect"] == "Silent Shadow": dodge += 0.15
    return int(base*mult + random.randint(0,20) * (2 if p["sect"] == "Storm Pavilion" else 1)), dodge, first

@heal
async def duel(update, ctx):
    u = update.effective_user; p = ensure_p(u.id, u.first_name)
    if not ctx.args or not ctx.args[0].startswith("@"):
        await update.effective_message.reply_text("Usage: /duel @user"); return
    try: t = await ctx.bot.get_chat(ctx.args[0])
    except Exception: await update.effective_message.reply_text("User not found."); return
    tp = get_p(t.id)
    if not tp: await update.effective_message.reply_text("That cultivator hasn't started yet."); return
    if t.id == CREATOR_ID:
        lvl, _ = exp_up(p, 100, u.id); set_p(u.id, points=p["points"]+1)
        await update.effective_message.reply_text(
            "👑 *You challenge The Creator…*\nTime stops with a single glance. You lose — but he grants +100 EXP and +1 point for your courage.\n*No mortal — not even a disciple — can harm The Creator.*", parse_mode=ParseMode.MARKDOWN); return
    d1, dod1, f1 = atk_power(p); d2, dod2, f2 = atk_power(tp)
    hp1, hp2 = p["hp"] + p["vitality"]*10 + (30 if p["sect"]=="Earth Sect" else 0), tp["hp"] + tp["vitality"]*10
    turn_p = not (f2 and (not f1 or random.random() < 0.5))
    for _ in range(30):
        dmg, defd = (d1, dod2) if turn_p else (d2, dod1)
        if random.random() >= defd:
            if turn_p: hp2 -= dmg
            else: hp1 -= dmg
        turn_p = not turn_p
        if hp1 <= 0 or hp2 <= 0: break
    win = hp2 <= 0
    if win:
        lvl, _ = exp_up(p, 80, u.id); set_p(u.id, coins=p["coins"]+100)
        winner, line = u.first_name, "+80 EXP +100💰"
        if p["guild"]:
            c = db_conn(); c.execute("UPDATE guilds SET wins=wins+1 WHERE name=?", (p["guild"],)); c.commit(); c.close()
    else:
        exp_up(tp, 80, t.id); set_p(t.id, coins=tp["coins"]+100)
        winner, line = t.first_name, "…your opponent grows stronger."
    await update.effective_message.reply_text(f"⚔️ *{u.first_name} vs {t.first_name}*\n🏆 *{winner} WINS!*\n{line}", parse_mode=ParseMode.MARKDOWN)

@heal
async def boss(update, ctx):
    u = update.effective_user; p = ensure_p(u.id, u.first_name)
    now = int(time.time())
    if now - p["last_boss"] < 600: await update.effective_message.reply_text(f"Recovering… {600-(now-p['last_boss'])}s."); return
    dmg, _, _ = atk_power(p)
    c = db_conn(); r = c.execute("SELECT hp, next FROM boss WHERE id=1").fetchone()
    if not r:
        c.execute("INSERT INTO boss VALUES(1,?,0)", (BOSSES[0][1],)); c.commit()
        r = (BOSSES[0][1], 0)
    hp, idx = r[0], r[1]; bname, bmax = BOSSES[idx % len(BOSSES)]
    if p["sect"] == "Iron Fist": dmg *= 2
    hp -= dmg
    lvl, _ = exp_up(p, 60, u.id); set_p(u.id, last_boss=now, coins=p["coins"]+30)
    msg = f"⚔️ You strike *{bname}* for {dmg}! Boss HP: {max(hp,0)}\n+60 EXP +30💰"
    if hp <= 0:
        nidx = idx + 1; nhp = BOSSES[nidx % len(BOSSES)][1]
        c.execute("UPDATE boss SET hp=?, next=? WHERE id=1", (nhp, nidx)); c.commit()
        msg += f"\n☠️ *{bname} SLAIN* by {u.first_name}! Next boss: *{BOSSES[nidx % len(BOSSES)][0]}*"
    else:
        c.execute("UPDATE boss SET hp=? WHERE id=1", (hp,)); c.commit()
    c.close()
    await update.effective_message.reply_text(msg + ("\n🎉 LEVEL UP!" if lvl else ""), parse_mode=ParseMode.MARKDOWN)

@heal
async def guildboss(update, ctx):
    u = update.effective_user; p = ensure_p(u.id, u.first_name)
    if not p["guild"]: await update.effective_message.reply_text("Join a guild first! /guild join <name>"); return
    if int(time.time()) - p["last_guildboss"] < 1800: await update.effective_message.reply_text("Guild boss cooldown — return later."); return
    dmg, _, _ = atk_power(p); dmg = int(dmg*1.25)
    lvl, _ = exp_up(p, 80, u.id); set_p(u.id, coins=p["coins"]+60, last_guildboss=int(time.time()))
    await update.effective_message.reply_text(f"🏯⚔️ Guild synergy! Strike for {dmg}. +80 EXP +60💰 for *{p['guild']}*!" + ("\n🎉 LEVEL UP!" if lvl else ""), parse_mode=ParseMode.MARKDOWN)

@heal
async def guildwar(update, ctx):
    await update.effective_message.reply_text(
        "🏯⚔️ *Guild War*\nDuel rival guild members with /duel @user — every duel win adds +1 war point to your guild this season.\n/guild info shows your wins.", parse_mode=ParseMode.MARKDOWN)

@heal
async def guild(update, ctx):
    u = update.effective_user; p = ensure_p(u.id, u.first_name)
    if not ctx.args:
        await update.effective_message.reply_text("Usage: /guild create <name> • join <name> • leave • info • donate <amt>"); return
    sub = ctx.args[0].lower(); c = db_conn()
    if sub == "create" and len(ctx.args) > 1:
        name = " ".join(ctx.args[1:])
        if p["coins"] < 500: c.close(); await update.effective_message.reply_text("Founding costs 500💰."); return
        try: c.execute("INSERT INTO guilds VALUES(?,?,0,0)", (name, u.id)); c.commit()
        except sqlite3.IntegrityError: c.close(); await update.effective_message.reply_text("That name exists."); return
        c.close(); set_p(u.id, coins=p["coins"]-500, guild=name)
        await update.effective_message.reply_text(f"🏯 Guild *{name}* founded — you are its leader!", parse_mode=ParseMode.MARKDOWN)
    elif sub == "join" and len(ctx.args) > 1:
        name = " ".join(ctx.args[1:])
        if not c.execute("SELECT 1 FROM guilds WHERE name=?", (name,)).fetchone():
            c.close(); await update.effective_message.reply_text("No such guild."); return
        c.close(); set_p(u.id, guild=name)
        await update.effective_message.reply_text(f"🏯 You joined *{name}*!", parse_mode=ParseMode.MARKDOWN)
    elif sub == "leave": c.close(); set_p(u.id, guild=""); await update.effective_message.reply_text("You left your guild.")
    elif sub == "donate" and len(ctx.args) > 1 and ctx.args[1].isdigit():
        amt = min(int(ctx.args[1]), p["coins"]); c.close()
        if p["guild"]:
            c = db_conn(); c.execute("UPDATE guilds SET funds=funds+? WHERE name=?", (amt, p["guild"])); c.commit(); c.close()
            set_p(u.id, coins=p["coins"]-amt); await update.effective_message.reply_text(f"💰 Donated {amt} to {p['guild']}.")
        else: await update.effective_message.reply_text("You're in no guild.")
    elif sub == "info":
        r = c.execute("SELECT funds, wins FROM guilds WHERE name=?", (p["guild"],)).fetchone() if p["guild"] else None
        c.close()
        await update.effective_message.reply_text(f"🏯 {p['guild'] or 'No guild'}" + (f"\nFunds: {r[0]}💰 • War wins: {r[1]}" if r else ""))
    else: c.close(); await update.effective_message.reply_text("Unknown subcommand.")

@heal
async def trial(update, ctx):
    u = update.effective_user; p = ensure_p(u.id, u.first_name)
    if not p["disciple"] and u.id != CREATOR_ID:
        await update.effective_message.reply_text("🌑 Only *Disciples of the Creator* may face The Creator's Shadow.\nBecome the season champion to be chosen.", parse_mode=ParseMode.MARKDOWN); return
    dmg, _, _ = atk_power(p); lvl, _ = exp_up(p, 200, u.id); set_p(u.id, coins=p["coins"]+200)
    await update.effective_message.reply_text(
        f"🌑👑 *The Creator's Shadow* (1,000,000 HP)\nYou deal {dmg} — a drop in the infinite… yet The Shadow acknowledges you.\n+200 EXP +200💰", parse_mode=ParseMode.MARKDOWN)

@heal
async def challengecreator(update, ctx):
    u = update.effective_user; p = ensure_p(u.id, u.first_name)
    lvl, _ = exp_up(p, 100, u.id); set_p(u.id, points=p["points"]+1)
    await update.effective_message.reply_text(
        "👑 *You challenge The Creator…*\nThe heavens part. A glance stops your heart-qi — defeated before you move.\nBut he smiles: *\"Courage is its own cultivation.\"*\n+100 EXP, +1 point. No mortal can harm The Creator.", parse_mode=ParseMode.MARKDOWN)

@heal
async def creator(update, ctx):
    await update.effective_message.reply_text(
        f"👑 *{CREATOR_NAME}*\nLevel: ∞ • Realm: The Creator ∞ • HP: ∞\n"
        f"💰 Coins: ∞ • 🌿 Herbs: ∞ • 💊 Pills: ∞ • ⚡ Qi: ∞ — all wealth and resources limitless.\n"
        f"Above Eternal Sovereign. Eternally #1 in every ranking.\n"
        f"Creator of Ascend: Eternal Path — cultivator of cultivators.\n/challengecreator if you dare.", parse_mode=ParseMode.MARKDOWN)

@heal
async def disciples(update, ctx):
    c = db_conn()
    rows = c.execute("SELECT name, season, season_exp FROM season_stats WHERE disciple=1 ORDER BY season DESC").fetchall(); c.close()
    await update.effective_message.reply_text("👑 *Lineage of Disciples*\n" +
        ("\n".join(f"Season {r[1]}: {r[0]} ({r[2]} EXP)" for r in rows) or "None yet — become the season champion!"),
        parse_mode=ParseMode.MARKDOWN)

@heal
async def event_cmd(update, ctx):
    await update.effective_message.reply_text(
        "🌌 *World Events* — The Creator occasionally descends and doubles rewards:\n⚔️ Boss x2 • ⚡ Cultivate x2 • 🎮 Games x2 • 🌅 Daily x2 • ⚗️ Alchemy never fails.\nWatch the broadcasts!")

@heal
async def propose(update, ctx):
    u = update.effective_user; p = ensure_p(u.id, u.first_name)
    if not ctx.args or not ctx.args[0].startswith("@"): await update.effective_message.reply_text("Usage: /propose @user"); return
    try: t = await ctx.bot.get_chat(ctx.args[0])
    except Exception: await update.effective_message.reply_text("User not found."); return
    ensure_p(t.id, t.first_name)
    set_p(u.id, spouse=t.first_name); set_p(t.id, spouse=u.first_name)
    await update.effective_message.reply_text(f"💍 {u.first_name} proposed… and {t.first_name} accepted! Bonds of the eternal path!")

@heal
async def divorce(update, ctx):
    set_p(update.effective_user.id, spouse="")
    await update.effective_message.reply_text("💔 Paths separate. The eternal road continues alone.")

@heal
async def hug(update, ctx):
    await update.effective_message.reply_text(f"🤗 {update.effective_user.first_name} hugs everyone with warm qi! (+charm in spirit)")

@heal
async def gift(update, ctx):
    u = update.effective_user; p = ensure_p(u.id, u.first_name)
    if p["coins"] >= 20: set_p(u.id, coins=p["coins"]-20)
    await update.effective_message.reply_text(f"🎁 {u.first_name} scatters herbs and coins to the world!")

@heal
async def chat(update, ctx):
    if not ctx.args: await update.effective_message.reply_text("Usage: /chat <message>"); return
    txt = f"💬 {html.escape(update.effective_user.first_name)}: {html.escape(' '.join(ctx.args)[:300])}"
    c = db_conn(); ids = [r[0] for r in c.execute("SELECT id FROM players").fetchall()]; c.close()
    sent = 0
    for pid in ids:
        if pid == update.effective_user.id: continue
        try: await ctx.bot.send_message(pid, txt); sent += 1
        except Exception: pass
    await update.effective_message.reply_text(f"📡 Broadcast to {sent} cultivators.")

@heal
async def setlocation(update, ctx):
    if not ctx.args: await update.effective_message.reply_text("Usage: /setlocation Country | Region | City\nExample: /setlocation Philippines | Cebu | Cebu City"); return
    loc = " | ".join(ctx.args); set_p(update.effective_user.id, location=loc)
    await update.effective_message.reply_text(f"📍 Location set: {loc}\nYou now appear in /top country|region|city!")

@heal
async def top(update, ctx):
    scope = ctx.args[0].lower() if ctx.args else "global"
    p = ensure_p(update.effective_user.id, update.effective_user.first_name)
    c = db_conn(); rows = c.execute("SELECT id,name,level,location FROM players").fetchall(); c.close()
    rows = [r for r in rows if r[0] != CREATOR_ID]
    if scope in ("country","region","city") and p["location"]:
        parts = [x.strip() for x in p["location"].split("|")]
        idx = {"country":0,"region":1,"city":2}[scope]
        key = parts[idx] if len(parts) > idx else ""
        rows = [r for r in rows if key and key.lower() in (r[3] or "").lower()]
    rows.sort(key=lambda r: -r[2])
    lines = "\n".join(f"{i+1}. {n} — Lv.{l}" for i,(i_,n,l,_) in enumerate(rows[:10])) or "No cultivators yet."
    await update.effective_message.reply_text(f"🏆 *Leaderboard* ({scope})\n👑 1. The Creator — Lv.∞\n{lines}", parse_mode=ParseMode.MARKDOWN)

@heal
async def halloffame(update, ctx):
    c = db_conn()
    rows = c.execute("SELECT name, season FROM season_stats WHERE disciple=1 ORDER BY season DESC").fetchall(); c.close()
    await update.effective_message.reply_text("🏛 *Hall of Fame & Champions*\n" +
        ("\n".join(f"👑 Season {r[1]} Champion & Disciple: {r[0]}" for r in rows) or "The first season continues…"))

@heal
async def season_info(update, ctx):
    start, s = season()
    days = SEASON_LEN - ((int(time.time()) - start) % SEASON_LEN)
    await update.effective_message.reply_text(f"🌌 *Season {s}*\nEnds in ~{days//86400} days.\nTop mortal becomes the Creator's *Disciple*: +5 all stats, +1 Spirit, +5,000💰, permanent +10% EXP.")

@heal
async def settitle(update, ctx):
    u = update.effective_user; p = ensure_p(u.id, u.first_name)
    owned = [t for t in (p["titles"] or "").split("|") if t]
    if not ctx.args:
        await update.effective_message.reply_text("Owned titles: " + (", ".join(owned) or "none yet — earn them!") + "\nUsage: /settitle <title>"); return
    t = " ".join(ctx.args)
    if t in owned: set_p(u.id, title=t); await update.effective_message.reply_text(f"🎖 Title equipped: {t}")
    else: await update.effective_message.reply_text("You don't own that title.")

@heal
async def wisdom(update, ctx):
    p = ensure_p(update.effective_user.id, update.effective_user.first_name)
    lvl, _ = exp_up(p, 10, update.effective_user.id)
    await update.effective_message.reply_text(f"📜 {random.choice(WISDOM)}\n(+10 EXP)")

@heal
async def history(update, ctx):
    await update.effective_message.reply_text("🕰 *World History of Cultivation*\n" + "\n".join(
        ["c. 3000 BC — Egyptian Asklepion healing temples","c. 500 BC — Laozi writes the Dao De Jing",
         "495 AD — Shaolin temple founded","c. 700 AD — Shugendō ascetics form in Japan",
         "1520 — Babaylan traditions survive colonization in the Pacific",
         "1882 — Rizal & the Propaganda Movement awaken the Philippines",
         "1943 — Resistance fighters train Arnis & guerrilla arts",
         "1954 — Judo enters the Olympics","1970s — Jeet Kune Do spreads worldwide",
         "2000s — Qigong & mindfulness enter hospitals","Today — You begin your eternal path."]))

# ---------------- MARTIAL ARTS ACADEMY (real) ----------------
@heal
async def arts(update, ctx):
    p = get_p(update.effective_user.id)
    await update.effective_message.reply_text(
        f"🥋 *Martial Arts Academy* — REAL techniques, REAL practice\n🌿{p['herbs']} 💰{p['coins']}",
        reply_markup=kb_grid(list(ARTS), "art"), parse_mode=ParseMode.MARKDOWN)

@heal
async def art_cb(update, ctx):
    q = update.callback_query; await q.answer()
    name = list(ARTS)[int(q.data.split("_")[1])]
    techs, perks = ARTS[name]
    await q.edit_message_text(
        f"🥋 *{name}*\n\n📖 Real techniques: {techs}\n\n💡 *Real-life path:* search '{name} tutorial' on YouTube, drill 10 min daily, join a school when possible.\n\n⚔️ Mastery perk: {perks}\n/train {list(ARTS).index(name)+1} to train it (1 🌿, +50 EXP).",
        parse_mode=ParseMode.MARKDOWN)

@heal
async def train(update, ctx):
    u = update.effective_user; p = ensure_p(u.id, u.first_name)
    if not ctx.args or not ctx.args[0].isdigit(): await update.effective_message.reply_text(f"Usage: /train <1-{len(ARTS)}> — see /arts"); return
    i = int(ctx.args[0]) - 1
    if i < 0 or i >= len(ARTS): await update.effective_message.reply_text("No such art."); return
    if p["herbs"] < 1: await update.effective_message.reply_text("Training costs 1 🌿 (recovery tea!). /forage"); return
    name = list(ARTS)[i]
    owned = [a for a in (p["arts"] or "").split("|") if a]
    if name not in owned: owned.append(name)
    set_p(u.id, herbs=p["herbs"]-1, arts="|".join(owned))
    lvl, _ = exp_up(p, 50, u.id)
    await update.effective_message.reply_text(
        f"🥋 You train *{name}*!\nReal practice today: {ARTS[name][0]}\n+50 EXP" + ("\n🎉 LEVEL UP!" if lvl else ""), parse_mode=ParseMode.MARKDOWN)

@heal
async def myarts(update, ctx):
    p = get_p(update.effective_user.id)
    owned = [a for a in (p["arts"] or "").split("|") if a in ARTS]
    await update.effective_message.reply_text("🥋 Your arts:\n" + ("\n".join(f"• {a}" for a in owned) or "None yet — /arts to enroll!") + "\n\nWeekly plan: /reallife")

# ---------------- HERBALISM ACADEMY (real) ----------------
@heal
async def herbacademy(update, ctx):
    p = get_p(update.effective_user.id)
    await update.effective_message.reply_text(
        f"🌿 *Herbalism Academy — Medicine of the Earth*\nReal imperial formulas (Jun-Chen-Zuo-Shi), sea to summit.\n🌿{p['herbs']} 💊{p['pills']} 💰{p['coins']}\n\n/formulas — list • /brewherb <n> — craft",
        reply_markup=kb_grid(list(HERBAL_RECIPES), "herb", 1), parse_mode=ParseMode.MARKDOWN)

@heal
async def herb_cb(update, ctx):
    q = update.callback_query; await q.answer()
    p = get_p(q.from_user.id)
    name = list(HERBAL_RECIPES)[int(q.data.split("_")[1])]
    r = HERBAL_RECIPES[name]
    if p["level"] < r["req"]: await q.answer(f"Requires level {r['req']}.", show_alert=True); return
    await q.edit_message_text(
        f"🌿 *{name}* (Lv.{r['req']}+)\n\n📜 *Real-life formula & method:*\n{r['real']}\n\n⚗️ Craft in-game: /brewherb {list(HERBAL_RECIPES).index(name)+1} (needs {r['herbs']} 🌿) → reward: {r['reward']}",
        parse_mode=ParseMode.MARKDOWN)

@heal
async def brewherb(update, ctx):
    u = update.effective_user; p = ensure_p(u.id, u.first_name)
    if not ctx.args or not ctx.args[0].isdigit(): await update.effective_message.reply_text("Usage: /brewherb <number> — /herbacademy"); return
    i = int(ctx.args[0]) - 1
    if i < 0 or i >= len(HERBAL_RECIPES): await update.effective_message.reply_text("No such formula."); return
    name = list(HERBAL_RECIPES)[i]; r = HERBAL_RECIPES[name]
    if p["level"] < r["req"]: await update.effective_message.reply_text(f"Requires level {r['req']}."); return
    if p["herbs"] < r["herbs"]: await update.effective_message.reply_text(f"Needs {r['herbs']} 🌿 — you have {p['herbs']}. /forage!"); return
    set_p(u.id, herbs=p["herbs"]-r["herbs"])
    kw = {k: p[k]+v for k, v in r["reward"].items()}
    lvl, _ = exp_up(p, 40 + r["req"]*10, u.id); set_p(u.id, **kw)
    await update.effective_message.reply_text(
        f"🌿⚗️ You craft *{name.split('(')[0].strip()}*!\n\n📜 Real method:\n{r['real']}\n\n🎁 {r['reward']}" + ("\n🎉 LEVEL UP!" if lvl else ""), parse_mode=ParseMode.MARKDOWN)

@heal
async def formulas(update, ctx):
    await update.effective_message.reply_text("🌿 *Herbal Formula Codex*\n" + "\n".join(
        f"{i+1}. {n.split('(')[0].strip()} — Lv.{r['req']}+ ({r['herbs']}🌿)"
        for i,(n,r) in enumerate(HERBAL_RECIPES)) + "\n\n/herbacademy • /brewherb <num>", parse_mode=ParseMode.MARKDOWN)

# ---------------- PHILOSOPHY / CODEX / REAL LIFE ----------------
@heal
async def philosophy(update, ctx):
    if ctx.args and ctx.args[0].isdigit():
        i = int(ctx.args[0]) - 1
        if 0 <= i < len(PHILOSOPHY):
            n, t = PHILOSOPHY[i]
            p = ensure_p(update.effective_user.id, update.effective_user.first_name)
            lvl, _ = exp_up(p, 10, update.effective_user.id)
            await update.effective_message.reply_text(f"📚 *{n}*\n\n{t}\n\n(+10 EXP — wisdom strengthens the spirit)", parse_mode=ParseMode.MARKDOWN); return
    await update.effective_message.reply_text("📚 *World Philosophy Library*\n" +
        "\n".join(f"{i+1}. {n}" for i,(n,_) in enumerate(PHILOSOPHY)) + "\n\n/philosophy <number>", parse_mode=ParseMode.MARKDOWN)

@heal
async def codex(update, ctx):
    if ctx.args and ctx.args[0].isdigit():
        i = int(ctx.args[0]) - 1
        if 0 <= i < len(CULTIVATION_HISTORY):
            n, t = CULTIVATION_HISTORY[i]
            p = ensure_p(update.effective_user.id, update.effective_user.first_name)
            lvl, _ = exp_up(p, 10, update.effective_user.id)
            await update.effective_message.reply_text(f"🏺 *{n}*\n\n{t}\n\n(+10 EXP — history deepens the roots)", parse_mode=ParseMode.MARKDOWN); return
    await update.effective_message.reply_text("🏺 *Codex of World Cultivation*\n" +
        "\n".join(f"{i+1}. {n}" for i,(n,_) in enumerate(CULTIVATION_HISTORY)) + "\n\n/codex <number>", parse_mode=ParseMode.MARKDOWN)

@heal
async def reallife(update, ctx):
    await update.effective_message.reply_text(REAL_LIFE_GUIDE, parse_mode=ParseMode.MARKDOWN)

# ---------------- BUTTON ROUTER ----------------
@heal
async def btn_router(update, ctx):
    q = update.callback_query; d = q.data
    if d.startswith("gender_"): return await gender_cb(update, ctx)
    if d.startswith("race_"):   return await race_cb(update, ctx)
    if d.startswith("sect_"):   return await sect_cb(update, ctx)
    if d.startswith("buyn_"):   return await buy_cb(update, ctx)
    if d.startswith("art_"):    return await art_cb(update, ctx)
    if d.startswith("herb_"):   return await herb_cb(update, ctx)
    await q.answer()

# ---------------- 24/7 HEALTH PAGE (for UptimeRobot) ----------------
class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Type","text/html"); self.end_headers()
        self.wfile.write(b"<h1>\xf0\x9f\x8c\xb8 Ascend: Eternal Path is ALIVE \xf0\x9f\x91\x91\xe2\x88\x9e</h1>")
    def log_message(self, *a): pass

def start_health_server():
    try:
        s = HTTPServer(("0.0.0.0", PORT), Health)
        threading.Thread(target=s.serve_forever, daemon=True).start()
        print(f"💓 Health page live on port {PORT} — point UptimeRobot here.")
    except Exception as e:
        logging.error(f"Health server: {e}")

# ---------------- MAIN ----------------
COMMANDS = [
 ("start","Begin your eternal path — create your character"),
 ("help","Show every command with hints"),
 ("profile","View your cultivator card"),
 ("stats","View your 8 stats and points"),
 ("up","Spend points: /up strength 2"),
 ("cultivate","Gather Qi (5–10 min cooldown)"),
 ("meditate","Real meditation × martial × breath fusion session"),
 ("fusion","Fusion Codex: /fusion 1–9 for each real practice"),
 ("breathwork","The three paths of real breathwork"),
 ("breathe","Gentle real breathing therapy for asthma & hard breathing"),
 ("energybreath","Real breathing techniques to raise energy & stamina"),
 ("soundqi","Sounding chi: Six Healing Sounds to gather qi by vibration"),
 ("daily","Claim daily rewards and keep your streak"),
 ("forage","Gather real herbs from sea, fields, mountains"),
 ("alchemy","Brew 2 herbs into a pill (may explode — that's teaching!)"),
 ("shop","Buy items with coins"),
 ("quiz","Answer a real knowledge quiz (+30 EXP)"),
 ("memory","Memory training game (+40 EXP)"),
 ("duel","Battle another cultivator: /duel @user"),
 ("boss","Strike the shared world boss"),
 ("guild","Guild: create, join, leave, info, donate"),
 ("guildboss","Guild-only boss with synergy bonus"),
 ("guildwar","How guild wars work (duel = war points)"),
 ("arts","REAL martial arts academy — 11 living arts"),
 ("train","Train an art: /train 1–11 (+50 EXP)"),
 ("myarts","Your learned martial arts"),
 ("herbacademy","REAL herbal formulas (Jun-Chen-Zuo-Shi imperial tradition)"),
 ("formulas","List all herbal formulas"),
 ("brewherb","Craft a formula: /brewherb 1–7"),
 ("philosophy","World philosophy: /philosophy 1–23"),
 ("codex","Real cultivation history: /codex 1–13"),
 ("reallife","Your REAL body refinement weekly guide"),
 ("wisdom","Receive a scroll of wisdom (+10 EXP)"),
 ("history","World history timeline of cultivation"),
 ("top","Leaderboards: /top global|country|region|city"),
 ("setlocation","Set location: /setlocation Country | Region | City"),
 ("halloffame","Season champions and disciples"),
 ("season_info","Current season and time remaining"),
 ("propose","Marry: /propose @user"),
 ("divorce","End a marriage"),
 ("hug","Send a warm-qi hug"),
 ("gift","Scatter gifts to the world"),
 ("chat","Broadcast to all players: /chat hello"),
 ("creator","Meet The Creator (Level ∞, limitless wealth & stats)"),
 ("challengecreator","Challenge The Creator — always lose, +100 EXP"),
 ("disciples","Lineage of the Creator's Disciples"),
 ("trial","Face the Creator's Shadow (disciples only)"),
 ("settitle","Equip a title: /settitle <title>"),
 ("event","Current world events"),
]

async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    seed_creator()
    start_health_server()
    for names, fn in [
        (["start"],start),(["help"],help_cmd),(["profile"],profile),(["stats"],stats_cmd),(["up"],up_cmd),
        (["cultivate"],cultivate),(["meditate"],meditate),(["fusion"],fusion),
        (["breathe"],breathe),(["energybreath","vitalbreath"],energybreath),
        (["soundqi","soundchi"],soundqi),(["breathwork"],breathwork),
        (["daily"],daily),(["forage"],forage),(["alchemy"],alchemy),(["shop"],shop),
        (["quiz"],quiz),(["memory"],memory),(["duel"],duel),(["boss"],boss),
        (["guild"],guild),(["guildboss"],guildboss),(["guildwar"],guildwar),
        (["trial"],trial),(["challengecreator"],challengecreator),(["creator"],creator),(["disciples"],disciples),
        (["event"],event_cmd),(["propose"],propose),(["divorce"],divorce),(["hug"],hug),(["gift"],gift),
        (["chat"],chat),(["setlocation"],setlocation),(["top"],top),(["halloffame"],halloffame),
        (["season_info"],season_info),(["settitle"],settitle),(["wisdom"],wisdom),(["history"],history),
        (["arts"],arts),(["train"],train),(["myarts"],myarts),(["herbacademy","herbs"],herbacademy),
        (["formulas"],formulas),(["brewherb"],brewherb),(["philosophy"],philosophy),(["codex"],codex),
        (["reallife","guide"],reallife)]:
        for n in names: app.add_handler(CommandHandler(n, fn))
    app.add_handler(CallbackQueryHandler(btn_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, quiz_answer), group=1)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mem_answer), group=1)
    app.add_error_handler(err_handler)
    try: await app.bot.set_my_commands([BotCommand(c, d) for c, d in COMMANDS])
    except Exception as e: logging.error(f"set_my_commands: {e}")
    print("🌸 ASCEND: ETERNAL PATH online — eternal cultivation begins. 👑∞")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
