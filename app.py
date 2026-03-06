import streamlit as st
import numpy as np
import plotly.graph_objects as go

# הגדרת הדף כרחב
st.set_page_config(page_title="Multi-Threat EW Professional Simulator", layout="wide")
st.title("🛡️ Professional Multi-Threat EW – Phase Uncertain POI")

# =========================================================
# פאנל שליטה ראשי - תצוגה צרה, קומפקטית וצפופה
# =========================================================
st.markdown("### ⚙️ Receiver Setup")

# קומה 1: תבנית בסיס (הוספנו עמודת spacer בסוף כדי לכווץ את הכל)
st.markdown("**1. Base Pattern & Detection Logic**")
r_cols = st.columns([1.2, 1, 1, 0.9, 1.1, 0.8, 0.8, 1.1, 1.5], gap="small")

rx_type = r_cols[0].selectbox("Rx Pattern", ["Fixed", "Custom"], key="rx_type")

rx_seq = []
if rx_type == "Fixed":
    rx_dwell = r_cols[1].number_input("Dwell [ms]", 0.1, 500.0, 5.0, step=1.0)
    rx_revisit = r_cols[2].number_input("Rev [ms]", 1.0, 2000.0, 100.0, step=1.0)
    rx_dev = r_cols[3].number_input("Dev [%]", 0.0, 99.0, 0.0, step=1.0)
    rx_seq = [(rx_dwell, rx_revisit)]
else:
    cust_rx_in = r_cols[1].text_input("Dwell:Rev (ms)", "5:100", help="Dwell1:Rev1, Dwell2:Rev2")
    rx_dev = r_cols[2].number_input("Dev [%]", 0.0, 99.0, 0.0, step=1.0)
    try:
        rx_seq = []
        for p in cust_rx_in.split(","):
            d, r = p.split(":")
            rx_seq.append((float(d.strip()), float(r.strip())))
    except:
        rx_seq = [(5.0, 100.0)]

min_overlap = r_cols[4].number_input("Overlap [ms]", 0.0, 100.0, 0.0, step=0.1)
age_in = r_cols[5].number_input("Age-In", 1, 10, 1)
age_out = r_cols[6].number_input("Age-Out", 1, 10, 1)
max_analysis_t = r_cols[7].number_input("Max Time", 10.0, 10000.0, 1000.0, step=10.0)

# קומה 2: אסטרטגיית סריקה (Framing) ומונטה קרלו
st.markdown("**2. Scan Strategy & Simulation**")
f_cols = st.columns([1.2, 1, 1, 1.2, 1.2, 0.9, 2.5], gap="small")

rx_frame_type = f_cols[0].selectbox("Rx Framing", ["None", "Regular", "Custom"], key="rx_frm_type")
rx_frame_seq = [(50.0, 150.0)]
rx_sync = "Continuous"

if rx_frame_type == "Regular":
    rx_fon = f_cols[1].number_input("ON [ms]", 1.0, 10000.0, 50.0, key="rx_fon")
    rx_foff = f_cols[2].number_input("OFF [ms]", 1.0, 10000.0, 150.0, key="rx_foff")
    rx_sync = f_cols[3].selectbox("Sync Mode", ["Continuous", "Reset"], key="rx_sync")
    rx_frame_seq = [(rx_fon, rx_foff)]
elif rx_frame_type == "Custom":
    cust_rx_frm = f_cols[1].text_input("ON:OFF Pairs", "50:150, 60:200", key="rx_cust_frm")
    rx_sync = f_cols[3].selectbox("Sync Mode", ["Continuous", "Reset"], key="rx_sync")
    try:
        rx_frame_seq = []
        for p in cust_rx_frm.split(","):
            on_val, off_val = p.split(":")
            rx_frame_seq.append((float(on_val.strip()), float(off_val.strip())))
    except:
        rx_frame_seq = [(50.0, 150.0), (60.0, 200.0)]

trials = f_cols[4].number_input("MC Trials", 100, 1000000, 30000, step=1000)
num_threats = f_cols[5].number_input("Threats", 1, 20, 1)

st.divider()

# =========================================================
# הגדרת איומים באמצעות לשוניות (Tabs) - תצוגה מכווצת
# =========================================================
st.markdown("### 🎯 Threat Configuration")
threats_list = []

if int(num_threats) > 0:
    tabs = st.tabs([f"🔥 Threat #{i + 1}" for i in range(int(num_threats))])

    for i, tab in enumerate(tabs):
        with tab:
            # שימוש בעמודת ספייסר כדי למנוע הימתחות התיבות בלשונית האיום
            t_cols1 = st.columns([1.2, 1, 1.2, 1.8, 3.5], gap="small")

            t_pri_type = t_cols1[0].selectbox("PRI Type", ["Fixed", "Jittered", "Staggered", "Custom"], key=f"type_{i}")
            t_data = {"id": i + 1, "type": t_pri_type}

            if t_pri_type == "Fixed":
                t_data["pw"] = t_cols1[1].number_input("PW [ms]", 0.01, 100.0, 5.0, key=f"pw_{i}")
                t_data["base_pri"] = t_cols1[2].number_input("PRI [ms]", 1.0, 2000.0, 100.0 + (i * 20), key=f"pri_{i}")
            elif t_pri_type == "Jittered":
                t_data["pw"] = t_cols1[1].number_input("PW [ms]", 0.01, 100.0, 5.0, key=f"pw_{i}")
                t_data["base_pri"] = t_cols1[2].number_input("Base PRI", 1.0, 2000.0, 100.0, key=f"bpri_{i}")
                t_data["jitter"] = t_cols1[3].number_input("Jitter [%]", 0, 99, 10, key=f"jit_{i}")
            elif t_pri_type == "Staggered":
                t_data["pw"] = t_cols1[1].number_input("PW [ms]", 0.01, 100.0, 5.0, key=f"pw_{i}")
                stag_in = t_cols1[2].text_input("Stagger Seq", "80,120,100", key=f"stag_{i}")
                try:
                    t_data["stagger"] = [float(x.strip()) for x in stag_in.split(",")]
                except:
                    t_data["stagger"] = [100.0]
            elif t_pri_type == "Custom":
                cust_in = t_cols1[1].text_input("PW:PRI Pairs", "5:100, 10:150", key=f"cust_pri_{i}")
                try:
                    pairs = []
                    for p in cust_in.split(","):
                        pw, pri = p.split(":")
                        pairs.append((float(pw.strip()), float(pri.strip())))
                    t_data["custom_seq"] = pairs
                except:
                    t_data["custom_seq"] = [(5.0, 100.0)]

            t_cols2 = st.columns([1.2, 1, 1, 1.2, 4.3], gap="small")
            frame_type = t_cols2[0].selectbox("Framing", ["None", "Regular", "Custom"], key=f"frm_type_{i}")
            t_data["frame_type"] = frame_type

            if frame_type == "Regular":
                t_data["frame_on"] = t_cols2[1].number_input("ON [ms]", 1.0, 10000.0, 50.0, key=f"fon_{i}")
                t_data["frame_off"] = t_cols2[2].number_input("OFF [ms]", 1.0, 10000.0, 150.0, key=f"foff_{i}")
                t_data["sync"] = t_cols2[3].selectbox("Internal Sync", ["Continuous", "Reset"], key=f"sync_{i}")
            elif frame_type == "Custom":
                cust_frm = t_cols2[1].text_input("ON:OFF Pairs", "20:180, 30:270", key=f"cust_frm_{i}")
                try:
                    pairs = []
                    for p in cust_frm.split(","):
                        on_val, off_val = p.split(":")
                        pairs.append((float(on_val.strip()), float(off_val.strip())))
                    t_data["frame_seq"] = pairs
                except:
                    t_data["frame_seq"] = [(20.0, 180.0), (30.0, 270.0)]
                t_data["sync"] = t_cols2[3].selectbox("Internal Sync", ["Continuous", "Reset"], key=f"sync_{i}")
            else:
                t_data["sync"] = "Continuous"

            threats_list.append(t_data)

st.markdown("---")


# =========================================================
# פונקציות עזר לסימולציה
# =========================================================
def generate_pulses(th, time_limit, offset_internal, offset_frame):
    windows = []
    if th['frame_type'] == "None":
        windows.append((-999999, 999999))
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

    if th['frame_type'] != "None" and th['sync'] == "Reset":
        for w_start, w_end in windows:
            if w_end < 0: continue
            p_t = w_start
            p_idx = 0
            while p_t < w_end:
                pw, pri = get_pw_pri(p_idx)
                p_end = p_t + pw

                o_start = max(w_start, p_t)
                o_end = min(w_end, p_end)
                if o_start < o_end and o_end >= 0 and o_start < time_limit:
                    pulses.append((o_start, o_end))

                p_t += pri
                p_idx += 1
    else:
        if th['type'] == "Staggered":
            int_per = sum(th['stagger'])
        elif th['type'] == "Custom":
            int_per = sum(p[1] for p in th['custom_seq'])
        else:
            int_per = th['base_pri']

        p_t = offset_internal - (int_per * 2)
        p_idx = 0

        valid_windows = [w for w in windows if w[1] >= p_t]
        w_idx = 0

        while p_t < time_limit:
            pw, pri = get_pw_pri(p_idx)
            p_end = p_t + pw

            while w_idx < len(valid_windows) and valid_windows[w_idx][1] < p_t:
                w_idx += 1

            temp_w = w_idx
            while temp_w < len(valid_windows) and valid_windows[temp_w][0] < p_end:
                w_start, w_end = valid_windows[temp_w]

                o_start = max(w_start, p_t)
                o_end = min(w_end, p_end)
                if o_start < o_end and o_end >= 0 and o_start < time_limit:
                    pulses.append((o_start, o_end))
                temp_w += 1

            p_t += pri
            p_idx += 1

    return pulses


def get_all_lock_times(limit_t):
    # 1. יצירת פולסים של האיומים
    all_threats_pulses = []
    for th in threats_list:
        if th['type'] == "Staggered":
            internal_period = sum(th['stagger'])
        elif th['type'] == "Custom":
            internal_period = sum(p[1] for p in th['custom_seq'])
        else:
            internal_period = th['base_pri']

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

    # 2. יצירת Dwells של המקלט
    rx_windows = []
    if rx_frame_type == "None":
        rx_windows.append((-999999, 999999))
    else:
        rx_f_period = sum(f[0] + f[1] for f in rx_frame_seq)
        rx_offset_frame = np.random.uniform(0, rx_f_period) if rx_f_period > 0 else 0
        t_f = rx_offset_frame - (rx_f_period * 2)
        f_idx = 0
        while t_f < limit_t:
            on_t, off_t = rx_frame_seq[f_idx]
            rx_windows.append((t_f, t_f + on_t))
            t_f += (on_t + off_t)
            f_idx = (f_idx + 1) % len(rx_frame_seq)

    rx_dwells = []

    def get_rx_params(idx):
        d, r = rx_seq[idx % len(rx_seq)]
        if rx_dev > 0:
            r = r * np.random.uniform(1 - rx_dev / 100.0, 1 + rx_dev / 100.0)
        return d, r

    if rx_frame_type != "None" and rx_sync == "Reset":
        for w_start, w_end in rx_windows:
            if w_end < 0: continue
            p_t = w_start
            p_idx = 0
            while p_t < w_end:
                d_val, r_val = get_rx_params(p_idx)
                d_end_time = p_t + d_val

                o_start = max(w_start, p_t)
                o_end = min(w_end, d_end_time)

                if o_start < o_end and o_end >= 0 and o_start < limit_t:
                    rx_dwells.append((o_start, o_end))

                p_t += r_val
                p_idx += 1
    else:
        int_per = sum(p[1] for p in rx_seq)
        p_t = np.random.uniform(0, int_per) - (int_per * 2)
        p_idx = 0

        valid_windows = [w for w in rx_windows if w[1] >= p_t]
        w_idx = 0

        while p_t < limit_t:
            d_val, r_val = get_rx_params(p_idx)
            d_end_time = p_t + d_val

            while w_idx < len(valid_windows) and valid_windows[w_idx][1] < p_t:
                w_idx += 1

            temp_w = w_idx
            while temp_w < len(valid_windows) and valid_windows[temp_w][0] < d_end_time:
                w_start, w_end = valid_windows[temp_w]

                o_start = max(w_start, p_t)
                o_end = min(w_end, d_end_time)
                if o_start < o_end and o_end >= 0 and o_start < limit_t:
                    rx_dwells.append((o_start, o_end))
                temp_w += 1

            p_t += r_val
            p_idx += 1

    # 3. בדיקת נעילות
    hits = [0] * len(threats_list)
    misses = [0] * len(threats_list)
    is_locked = [False] * len(threats_list)
    lock_times = [None] * len(threats_list)

    for d_start, d_end in rx_dwells:
        obs_start, obs_end = max(0, d_start), min(limit_t, d_end)
        if obs_start >= obs_end: continue

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