import streamlit as st
import numpy as np
import plotly.graph_objects as go

st.set_page_config(page_title="Multi-Threat EW Professional Simulator", layout="wide")
st.title("🛡️ Professional Multi-Threat EW – Phase Uncertain POI")

# =========================================================
# Sidebar - הגדרות מקלט
# =========================================================
st.sidebar.header("1️⃣ Receiver Parameters")
dwell = st.sidebar.number_input("Dwell [ms]", 1.0, 500.0, 40.0)
revisit = st.sidebar.number_input("Revisit [ms]", 1.0, 2000.0, 100.0)

st.sidebar.header("2️⃣ Detection Logic")
# --- התוספת החדשה: חפיפה מינימלית ---
min_overlap = st.sidebar.number_input("Min Overlap for Hit [ms]", 0.0, 100.0, 0.1, step=0.1)
age_in = st.sidebar.number_input("Age-In (Hits Needed)", 1, 10, 2)
age_out = st.sidebar.number_input("Age-Out (Misses Allowed)", 1, 10, 2)
max_analysis_t = st.sidebar.number_input("Max Analysis Time [ms]", 10.0, 10000.0, 1000.0)

st.sidebar.header("3️⃣ Monte Carlo Settings")
trials = st.sidebar.slider("Number of Offsets", 0, 20000, 10000)

# =========================================================
# 4️⃣ הוספת איומים דינמית
# =========================================================
st.sidebar.header("4️⃣ Threat Configuration")
num_threats = st.sidebar.number_input("How many threats?", 1, 20, 2)

threats_list = []
for i in range(int(num_threats)):
    with st.sidebar.expander(f"🔥 Threat #{i + 1} Setup", expanded=(i == 0)):
        t_pri_type = st.selectbox(f"PRI Type", ["Fixed", "Jittered", "Staggered"], key=f"type_{i}")
        t_pw = st.number_input(f"PW [ms]", 0.01, 100.0, 5.0, key=f"pw_{i}")

        t_data = {"id": i + 1, "type": t_pri_type, "pw": t_pw}

        if t_pri_type == "Fixed":
            t_data["base_pri"] = st.number_input(f"PRI [ms]", 1.0, 2000.0, 100.0 + (i * 20), key=f"pri_{i}")
        elif t_pri_type == "Jittered":
            t_data["base_pri"] = st.number_input(f"Base PRI [ms]", 1.0, 2000.0, 100.0, key=f"bpri_{i}")
            t_data["jitter"] = st.number_input(f"Jitter (%)", 0, 99, 10, key=f"jit_{i}")
        elif t_pri_type == "Staggered":
            stag_in = st.text_input(f"Stagger Seq (ms)", "80,120,100", key=f"stag_{i}")
            try:
                t_data["stagger"] = [float(x.strip()) for x in stag_in.split(",")]
            except:
                t_data["stagger"] = [100.0]

        threats_list.append(t_data)


# =========================================================
# פונקציות עזר לסימולציה
# =========================================================
def generate_pulses(threat, time_limit, offset):
    """מייצר רכבת פולסים, מתחיל מזמן שלילי כדי לא לפספס פולסים שגולשים לזמן 0"""
    pulses = []

    # חישוב המחזור הכולל כדי שנוכל ללכת אחורה בזמן
    if threat['type'] == "Staggered":
        period = sum(threat['stagger'])
    else:
        period = threat['base_pri']

    # מתחילים לייצר פולסים הרחק בזמן השלילי כדי לכסות את כל ההיסטוריה
    t = offset - (period * 2)
    st_idx = 0

    while t < time_limit:
        # שומרים רק פולסים שמגיעים לזמן הרלוונטי (חיובי)
        if t + threat['pw'] >= 0:
            pulses.append((t, t + threat['pw']))

        if threat['type'] == "Fixed":
            interval = threat['base_pri']
        elif threat['type'] == "Jittered":
            interval = threat['base_pri'] * np.random.uniform(1 - threat['jitter'] / 100, 1 + threat['jitter'] / 100)
        else:  # Staggered
            interval = threat['stagger'][st_idx]
            st_idx = (st_idx + 1) % len(threat['stagger'])
        t += interval

    return pulses


def get_all_lock_times(limit_t):
    """
    מריץ ניסוי אחד. מחזיר רשימה של זמני הנעילה (ms) לכל איום.
    אם איום לא ננעל, הערך שלו יהיה None.
    """
    r_off = np.random.uniform(-dwell, revisit - dwell)

    all_threats_pulses = []
    for th in threats_list:
        p_period = sum(th['stagger']) if th['type'] == "Staggered" else th['base_pri']
        t_off = np.random.uniform(0, p_period)
        all_threats_pulses.append(generate_pulses(th, limit_t + 100, t_off))

    hits = [0] * len(threats_list)
    misses = [0] * len(threats_list)
    is_locked = [False] * len(threats_list)
    lock_times = [None] * len(threats_list)

    t_curr = r_off
    while t_curr < limit_t:
        d_start, d_end = t_curr, t_curr + dwell

        # אנחנו מסתכלים רק על החלק של ה-Dwell שנמצא בתוך טווח האנליזה
        obs_start, obs_end = max(0, d_start), min(limit_t, d_end)

        if obs_start < obs_end:  # יש לנו חלון הקשבה חוקי
            for i in range(len(threats_list)):
                if lock_times[i] is not None: continue  # כבר מצאנו את זמן הנעילה לאיום זה

                # --- השינוי המרכזי: בדיקת משך החפיפה ---
                # מחשבים את אורך החפיפה (overlap) ובודקים אם הוא עומד בסף המינימלי
                hit = any((min(obs_end, p[1]) - max(obs_start, p[0])) >= min_overlap for p in all_threats_pulses[i])

                if hit:
                    hits[i] += 1
                    misses[i] = 0
                    if hits[i] >= age_in:
                        is_locked[i] = True
                        lock_times[i] = obs_end  # שומרים את זמן ההצלחה המדויק
                else:
                    if is_locked[i]:
                        misses[i] += 1
                        if misses[i] >= age_out:
                            is_locked[i] = False
                            hits[i] = 0
                    else:
                        hits[i] = max(0, hits[i] - 1)

        # אם כל האיומים כבר ננעלו, אין טעם להמשיch את הניסוי הזה
        if all(lt is not None for lt in lock_times): break

        t_curr += revisit

    return lock_times


# =========================================================
# הרצה ותצוגה
# =========================================================

all_trials_results = []

with st.spinner(f"Simulating {len(threats_list)} threats over {trials} MC trials..."):
    for _ in range(trials):
        all_trials_results.append(get_all_lock_times(max_analysis_t))

# --- חישוב נתונים לגרפים ולמדדים ---
time_axis = np.linspace(0, max_analysis_t, 30)
threat_names = [f"Threat #{i + 1}" for i in range(len(threats_list))]

# 1. חישוב Combined POI & MTTI (לפחות איום אחד)
combined_poi_curve = []
combined_lock_times = []
for res in all_trials_results:
    valid_times = [t for t in res if t is not None]
    if valid_times:
        combined_lock_times.append(min(valid_times))  # הזמן המהיר ביותר מבין האיומים שניצודו

for t_pt in time_axis:
    count = sum(1 for ct in combined_lock_times if ct <= t_pt)
    combined_poi_curve.append((count / trials) * 100)

mtti_combined = np.mean(combined_lock_times) if combined_lock_times else 0

# 2. חישוב Individual POI & MTTI לכל איום
individual_pois = []
individual_mttis = []
for i in range(len(threats_list)):
    poi_curve = []
    t_times = [res[i] for res in all_trials_results if res[i] is not None]

    for t_pt in time_axis:
        count = sum(1 for res in all_trials_results if res[i] is not None and res[i] <= t_pt)
        poi_curve.append((count / trials) * 100)

    individual_pois.append(poi_curve)
    individual_mttis.append(np.mean(t_times) if t_times else 0)

# --- תצוגת UI ---
st.subheader("📊 POI & MTTI Results")
st.caption(f"⚙️ Simulation run with **{trials}** MC trials across **{len(threats_list)}** active threats.")

# תיבת בחירה איזה גרפים להציג
to_show = st.multiselect("Select curves to display:", ["Combined POI"] + threat_names, default=["Combined POI"])

# שורת מדדים דינמית שמתעדכנת לפי מה שנבחר בתיבת הטקסט
if to_show:
    cols = st.columns(len(to_show))
    for idx, name in enumerate(to_show):
        if name == "Combined POI":
            poi_val = combined_poi_curve[-1]
            mtti_str = f"{mtti_combined:.1f} ms" if mtti_combined > 0 else "N/A"
            cols[idx].metric("🎯 Combined POI", f"{poi_val:.2f}%", f"MTTI: {mtti_str}", delta_color="off")
        else:
            t_idx = int(name.split('#')[1]) - 1
            poi_val = individual_pois[t_idx][-1]
            mtti_val = individual_mttis[t_idx]
            mtti_str = f"{mtti_val:.1f} ms" if mtti_val > 0 else "N/A"
            cols[idx].metric(f"🎯 {name} POI", f"{poi_val:.2f}%", f"MTTI: {mtti_str}", delta_color="off")
else:
    st.warning("⚠️ בחר לפחות גרף אחד מתיבת הבחירה כדי לראות נתונים.")

st.divider()

# ציור הגרף עצמו לפי הבחירה
fig_poi = go.Figure()

if "Combined POI" in to_show:
    fig_poi.add_trace(go.Scatter(x=time_axis, y=combined_poi_curve, name="Combined (Any Threat)",
                                 line=dict(color='#00CC96', width=4, dash='dash')))

for i, name in enumerate(threat_names):
    if name in to_show:
        # כל איום מקבל קו משלו בגרף
        fig_poi.add_trace(go.Scatter(x=time_axis, y=individual_pois[i],
                                     name=f"{name} (MTTI: {individual_mttis[i]:.1f}ms)", mode='lines'))

fig_poi.update_layout(title="Cumulative POI over Time",
                      xaxis_title="Time [ms]",
                      yaxis_title="POI (%)",
                      yaxis_range=[-2, 105],
                      height=500)

st.plotly_chart(fig_poi, use_container_width=True)