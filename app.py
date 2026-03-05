import streamlit as st
import numpy as np
import plotly.graph_objects as go

# הגדרת הדף כרחב (Wide)
st.set_page_config(page_title="Multi-Threat EW Professional Simulator", layout="wide")
st.title("🛡️ Professional Multi-Threat EW – Phase Uncertain POI")

# =========================================================
# פאנל שליטה ראשי - תצוגה קומפקטית
# =========================================================
st.markdown("### ⚙️ Simulation Setup")

# חלוקה ל-7 עמודות צרות
col1, col2, col_dev, col3, col4, col5, col6 = st.columns(7)

with col1:
    dwell = st.number_input("Dwell [ms]", 1.0, 500.0, 5.0, step=1.0)
with col2:
    revisit = st.number_input("Revisit [ms]", 1.0, 2000.0, 100.0, step=1.0)
with col_dev:
    rev_dev = st.number_input("Rev. Dev (%)", 0.0, 99.0, 0.0, step=1.0)
with col3:
    min_overlap = st.number_input("Min Overlap", 0.0, 100.0, 0.0, step=0.1)
with col4:
    age_in = st.number_input("Age-In (Hits)", 1, 10, 1)  # ברירת מחדל 1
with col5:
    age_out = st.number_input("Age-Out (Miss)", 1, 10, 1)  # ברירת מחדל 1
with col6:
    max_analysis_t = st.number_input("Max Time [ms]", 10.0, 10000.0, 1000.0, step=10.0)

col7, col8 = st.columns([1, 3])
with col7:
    trials = st.number_input("Monte Carlo Trials", 100, 1000000, 30000, step=1000)
with col8:
    num_threats = st.number_input("How many threats?", 1, 20, 1)

st.divider()

# =========================================================
# הגדרת איומים באמצעות לשוניות (Tabs)
# =========================================================
st.markdown("### 🎯 Threat Configuration")
threats_list = []

if int(num_threats) > 0:
    tabs = st.tabs([f"🔥 Threat #{i + 1}" for i in range(int(num_threats))])

    for i, tab in enumerate(tabs):
        with tab:
            # שורה 1: תצורת הפולסים (PRI ו-PW)
            t_col1, t_col2, t_col3, t_col4 = st.columns(4)

            t_pri_type = t_col1.selectbox("PRI Type", ["Fixed", "Jittered", "Staggered", "Custom"], key=f"type_{i}")
            t_data = {"id": i + 1, "type": t_pri_type}

            if t_pri_type == "Fixed":
                t_data["pw"] = t_col2.number_input("PW [ms]", 0.01, 100.0, 5.0, key=f"pw_{i}")
                t_data["base_pri"] = t_col3.number_input("PRI [ms]", 1.0, 2000.0, 100.0 + (i * 20), key=f"pri_{i}")
            elif t_pri_type == "Jittered":
                t_data["pw"] = t_col2.number_input("PW [ms]", 0.01, 100.0, 5.0, key=f"pw_{i}")
                t_data["base_pri"] = t_col3.number_input("Base PRI [ms]", 1.0, 2000.0, 100.0, key=f"bpri_{i}")
                t_data["jitter"] = t_col4.number_input("Jitter (%)", 0, 99, 10, key=f"jit_{i}")
            elif t_pri_type == "Staggered":
                t_data["pw"] = t_col2.number_input("PW [ms]", 0.01, 100.0, 5.0, key=f"pw_{i}")
                stag_in = t_col3.text_input("Stagger Seq (ms)", "80,120,100", key=f"stag_{i}")
                try:
                    t_data["stagger"] = [float(x.strip()) for x in stag_in.split(",")]
                except:
                    t_data["stagger"] = [100.0]
            elif t_pri_type == "Custom":
                cust_in = t_col2.text_input("PW:PRI Pairs (ms)", "5:100, 10:150", help="Format: PW1:PRI1, PW2:PRI2",
                                            key=f"cust_pri_{i}")
                try:
                    pairs = []
                    for p in cust_in.split(","):
                        pw, pri = p.split(":")
                        pairs.append((float(pw.strip()), float(pri.strip())))
                    t_data["custom_seq"] = pairs
                except:
                    t_data["custom_seq"] = [(5.0, 100.0)]  # גיבוי לשגיאת הקלדה

            # שורה 2: תצורת המסגרות (Framing)
            f_col1, f_col2, f_col3, f_col4 = st.columns(4)
            frame_type = f_col1.selectbox("Framing", ["None", "Regular", "Custom"], key=f"frm_type_{i}")
            t_data["frame_type"] = frame_type

            if frame_type == "Regular":
                t_data["frame_on"] = f_col2.number_input("Frame ON [ms]", 1.0, 10000.0, 50.0, key=f"fon_{i}")
                t_data["frame_off"] = f_col3.number_input("Frame OFF [ms]", 1.0, 10000.0, 150.0, key=f"foff_{i}")
                t_data["sync"] = f_col4.selectbox("Internal Sync", ["Continuous", "Reset"], key=f"sync_{i}")
            elif frame_type == "Custom":
                cust_frm = f_col2.text_input("ON:OFF Pairs (ms)", "20:180, 30:270", help="Format: ON1:OFF1, ON2:OFF2",
                                             key=f"cust_frm_{i}")
                try:
                    pairs = []
                    for p in cust_frm.split(","):
                        on_val, off_val = p.split(":")
                        pairs.append((float(on_val.strip()), float(off_val.strip())))
                    t_data["frame_seq"] = pairs
                except:
                    t_data["frame_seq"] = [(20.0, 180.0), (30.0, 270.0)]
                t_data["sync"] = f_col4.selectbox("Internal Sync", ["Continuous", "Reset"], key=f"sync_{i}")
            else:
                t_data["sync"] = "Continuous"  # ללא מסגרת ההתנהגות זהה לרציף

            threats_list.append(t_data)

st.markdown("---")


# =========================================================
# פונקציות עזר לסימולציה
# =========================================================
def generate_pulses(th, time_limit, offset_internal, offset_frame):
    # 1. יצירת חלונות המסגרת האקטיביים (Windowing)
    windows = []
    if th['frame_type'] == "None":
        windows.append((-999999, 999999))  # חלון נצחי
    else:
        if th['frame_type'] == "Regular":
            f_seq = [(th['frame_on'], th['frame_off'])]
        else:
            f_seq = th['frame_seq']

        f_period = sum(f[0] + f[1] for f in f_seq)
        t_f = offset_frame - (f_period * 2)
        f_idx = 0
        while t_f < time_limit:
            on_t, off_t = f_seq[f_idx]
            windows.append((t_f, t_f + on_t))
            t_f += (on_t + off_t)
            f_idx = (f_idx + 1) % len(f_seq)

    pulses = []

    # פונקציית עזר להוצאת ה-PW וה-PRI הבאים לפי הסוג
    def get_pw_pri(idx):
        if th['type'] == "Fixed":
            return th['pw'], th['base_pri']
        elif th['type'] == "Jittered":
            jit = th['base_pri'] * np.random.uniform(1 - th['jitter'] / 100, 1 + th['jitter'] / 100)
            return th['pw'], jit
        elif th['type'] == "Staggered":
            return th['pw'], th['stagger'][idx % len(th['stagger'])]
        elif th['type'] == "Custom":
            return th['custom_seq'][idx % len(th['custom_seq'])]

    # 2. יצירת פולסים והפעלת Masking
    if th['frame_type'] != "None" and th['sync'] == "Reset":
        # מצב Reset: מאפסים את השעון הפנימי בכל פעם שחלון חדש נפתח
        for w_start, w_end in windows:
            if w_end < 0: continue
            p_t = w_start
            p_idx = 0
            while p_t < w_end:
                pw, pri = get_pw_pri(p_idx)
                p_end = p_t + pw

                # חיתוך הפולס בהתאם לגבולות החלון
                o_start = max(w_start, p_t)
                o_end = min(w_end, p_end)
                if o_start < o_end and o_end >= 0 and o_start < time_limit:
                    pulses.append((o_start, o_end))

                p_t += pri
                p_idx += 1
    else:
        # מצב Continuous או ללא מסגרת כלל
        if th['type'] == "Staggered":
            int_per = sum(th['stagger'])
        elif th['type'] == "Custom":
            int_per = sum(p[1] for p in th['custom_seq'])
        else:
            int_per = th['base_pri']

        p_t = offset_internal - (int_per * 2)
        p_idx = 0

        # סינון חלונות שעברו כדי לחסוך זמן חישוב
        valid_windows = [w for w in windows if w[1] >= p_t]
        w_idx = 0

        while p_t < time_limit:
            pw, pri = get_pw_pri(p_idx)
            p_end = p_t + pw

            # קידום אינדקס החלונות אל מול הזמן הנוכחי של הפולס
            while w_idx < len(valid_windows) and valid_windows[w_idx][1] < p_t:
                w_idx += 1

            temp_w = w_idx
            while temp_w < len(valid_windows) and valid_windows[temp_w][0] < p_end:
                w_start, w_end = valid_windows[temp_w]

                # חיתוך הפולס מול החלון הנוכחי
                o_start = max(w_start, p_t)
                o_end = min(w_end, p_end)
                if o_start < o_end and o_end >= 0 and o_start < time_limit:
                    pulses.append((o_start, o_end))
                temp_w += 1

            p_t += pri
            p_idx += 1

    return pulses


def get_all_lock_times(limit_t):
    r_off = np.random.uniform(-dwell, revisit - dwell)

    all_threats_pulses = []
    for th in threats_list:
        # חישוב המחזור הפנימי להגרלת הפאזה
        if th['type'] == "Staggered":
            internal_period = sum(th['stagger'])
        elif th['type'] == "Custom":
            internal_period = sum(p[1] for p in th['custom_seq'])
        else:
            internal_period = th['base_pri']

        # חישוב מחזור המסגרת להגרלת הפאזה החיצונית
        if th['frame_type'] == "Regular":
            f_period = th['frame_on'] + th['frame_off']
        elif th['frame_type'] == "Custom":
            f_period = sum(f[0] + f[1] for f in th['frame_seq'])
        else:
            f_period = 0

        offset_frame = np.random.uniform(0, f_period) if f_period > 0 else 0

        if th['sync'] == "Continuous" or th['frame_type'] == "None":
            offset_internal = np.random.uniform(0, internal_period)
        else:
            offset_internal = 0

        all_threats_pulses.append(generate_pulses(th, limit_t + 100, offset_internal, offset_frame))

    hits = [0] * len(threats_list)
    misses = [0] * len(threats_list)
    is_locked = [False] * len(threats_list)
    lock_times = [None] * len(threats_list)

    t_curr = r_off
    while t_curr < limit_t:
        d_start, d_end = t_curr, t_curr + dwell
        obs_start, obs_end = max(0, d_start), min(limit_t, d_end)

        if obs_start < obs_end:
            for i in range(len(threats_list)):
                if lock_times[i] is not None: continue

                hit = any((min(obs_end, p[1]) - max(obs_start, p[0])) >= min_overlap for p in all_threats_pulses[i])

                if hit:
                    hits[i] += 1
                    misses[i] = 0
                    if hits[i] >= age_in:
                        is_locked[i] = True
                        lock_times[i] = obs_end
                else:
                    if is_locked[i]:
                        misses[i] += 1
                        if misses[i] >= age_out:
                            is_locked[i] = False
                            hits[i] = 0
                    else:
                        hits[i] = max(0, hits[i] - 1)

        if all(lt is not None for lt in lock_times): break

        if rev_dev > 0:
            current_revisit = revisit * np.random.uniform(1 - rev_dev / 100.0, 1 + rev_dev / 100.0)
        else:
            current_revisit = revisit

        t_curr += current_revisit

    return lock_times


# =========================================================
# הרצה ותצוגה
# =========================================================

all_trials_results = []

with st.spinner(f"Simulating {len(threats_list)} threats over {trials:,} MC trials... This might take a moment."):
    for _ in range(trials):
        all_trials_results.append(get_all_lock_times(max_analysis_t))

# --- עיבוד נתונים משולב (Combined POI) ---
time_axis = np.linspace(0, max_analysis_t, 30)
combined_lock_times = []
for res in all_trials_results:
    valid_times = [t for t in res if t is not None]
    if valid_times:
        combined_lock_times.append(min(valid_times))

final_combined_poi = (len(combined_lock_times) / trials) * 100
mtti_combined = np.mean(combined_lock_times) if combined_lock_times else 0

combined_poi_curve = []
for t_pt in time_axis:
    count = sum(1 for ct in combined_lock_times if ct <= t_pt)
    combined_poi_curve.append((count / trials) * 100)

# --- עיבוד נתונים פרטני (Individual POI) ---
threat_names = [f"Threat #{i + 1}" for i in range(len(threats_list))]
individual_pois_final = []
individual_mttis = []
individual_pois_curve = []

for i in range(len(threats_list)):
    t_times = [res[i] for res in all_trials_results if res[i] is not None]

    individual_pois_final.append((len(t_times) / trials) * 100)
    individual_mttis.append(np.mean(t_times) if t_times else 0)

    poi_curve = []
    for t_pt in time_axis:
        count = sum(1 for res in all_trials_results if res[i] is not None and res[i] <= t_pt)
        poi_curve.append((count / trials) * 100)
    individual_pois_curve.append(poi_curve)

# --- תצוגת UI תחתון ---
st.subheader("📊 Results")
st.caption(f"⚙️ Simulation run with **{trials:,}** MC trials.")

to_show = st.multiselect("Select metrics to display:", ["Combined POI"] + threat_names, default=["Combined POI"])

selected_threat_names = [name for name in to_show if name != "Combined POI"]
show_dynamic_combined = False
dyn_poi_final = 0
dyn_mtti = 0
dyn_poi_curve = []

if len(selected_threat_names) > 1:
    show_dynamic_combined = st.checkbox(f"Show Dynamic Combined (OR) for {len(selected_threat_names)} selected threats",
                                        value=True)

    if show_dynamic_combined:
        selected_indices = [int(name.split('#')[1]) - 1 for name in selected_threat_names]
        dyn_lock_times = []
        for res in all_trials_results:
            valid_times = [res[i] for i in selected_indices if res[i] is not None]
            if valid_times:
                dyn_lock_times.append(min(valid_times))

        dyn_poi_final = (len(dyn_lock_times) / trials) * 100
        dyn_mtti = np.mean(dyn_lock_times) if dyn_lock_times else 0

        for t_pt in time_axis:
            count = sum(1 for ct in dyn_lock_times if ct <= t_pt)
            dyn_poi_curve.append((count / trials) * 100)

num_metrics = len(to_show) + (1 if show_dynamic_combined else 0)

if num_metrics > 0:
    cols = st.columns(num_metrics)
    col_idx = 0

    if show_dynamic_combined:
        mtti_str = f"{dyn_mtti:.1f} ms" if dyn_mtti > 0 else "N/A"
        cols[col_idx].metric(f"🎯 Selected Combined (OR)", f"{dyn_poi_final:.3f}%", f"MTTI: {mtti_str}",
                             delta_color="off")
        col_idx += 1

    for name in to_show:
        if name == "Combined POI":
            poi_val = final_combined_poi
            mtti_str = f"{mtti_combined:.1f} ms" if mtti_combined > 0 else "N/A"
            cols[col_idx].metric("🎯 Combined POI (All)", f"{poi_val:.3f}%", f"MTTI: {mtti_str}", delta_color="off")
        else:
            t_idx = int(name.split('#')[1]) - 1
            poi_val = individual_pois_final[t_idx]
            mtti_val = individual_mttis[t_idx]
            mtti_str = f"{mtti_val:.1f} ms" if mtti_val > 0 else "N/A"
            cols[col_idx].metric(f"🎯 {name} POI", f"{poi_val:.3f}%", f"MTTI: {mtti_str}", delta_color="off")
        col_idx += 1
else:
    st.warning("⚠️ בחר לפחות מדד אחד מתיבת הבחירה כדי לראות נתונים.")

st.divider()
fig_poi = go.Figure()

if "Combined POI" in to_show:
    fig_poi.add_trace(go.Scatter(x=time_axis, y=combined_poi_curve, name="Combined (All Threats)",
                                 line=dict(color='#00CC96', width=4, dash='dash')))

if show_dynamic_combined:
    fig_poi.add_trace(go.Scatter(x=time_axis, y=dyn_poi_curve, name="Combined (Selected OR)",
                                 line=dict(color='#FF8C00', width=4, dash='dot')))

for i, name in enumerate(threat_names):
    if name in to_show:
        t_idx = int(name.split('#')[1]) - 1
        fig_poi.add_trace(go.Scatter(x=time_axis, y=individual_pois_curve[t_idx],
                                     name=f"{name} (MTTI: {individual_mttis[t_idx]:.1f}ms)", mode='lines'))

fig_poi.update_layout(title="Cumulative POI over Time", xaxis_title="Time [ms]", yaxis_title="POI (%)",
                      yaxis_range=[-2, 105], height=500)
st.plotly_chart(fig_poi, use_container_width=True)