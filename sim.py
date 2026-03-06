import streamlit as st
import numpy as np
import pandas as pd

st.set_page_config(page_title="EW Receiver Optimizer", layout="wide")
st.title("✨ Receiver Auto-Tuner (Optimization Engine)")
st.markdown("כלי זה מחשב את זוגות ה-Dwell וה-Revisit האופטימליים כדי להבטיח גילוי (POI) תחת Max Time נתון.")

# =========================================================
# פאנל הגדרות
# =========================================================
st.markdown("### 1. Threat & Goal Definition")

g_cols = st.columns(5, gap="small")
target_poi = g_cols[0].number_input("Target POI [%]", 90.0, 100.0, 99.0, step=0.5)
max_time = g_cols[1].number_input("Max Time [ms]", 10.0, 10000.0, 1000.0, step=10.0)
age_in = g_cols[2].number_input("Age-In (Hits)", 1, 10, 3)
age_out = g_cols[3].number_input("Age-Out (Miss)", 1, 10, 1)
mc_trials = g_cols[4].number_input("Trials per Test", 500, 50000, 2000, step=500)

st.divider()

t_cols1 = st.columns([1.2, 1, 1.2, 1.8, 3.5], gap="small")
t_pri_type = t_cols1[0].selectbox("PRI Type", ["Fixed", "Jittered", "Staggered", "Custom"])
t_data = {"type": t_pri_type}

if t_pri_type == "Fixed":
    t_data["pw"] = t_cols1[1].number_input("PW [ms]", 0.01, 100.0, 5.0)
    t_data["base_pri"] = t_cols1[2].number_input("PRI [ms]", 1.0, 2000.0, 100.0)
elif t_pri_type == "Jittered":
    t_data["pw"] = t_cols1[1].number_input("PW [ms]", 0.01, 100.0, 5.0)
    t_data["base_pri"] = t_cols1[2].number_input("Base PRI", 1.0, 2000.0, 100.0)
    t_data["jitter"] = t_cols1[3].number_input("Jitter [%]", 0, 99, 10)
elif t_pri_type == "Staggered":
    t_data["pw"] = t_cols1[1].number_input("PW [ms]", 0.01, 100.0, 5.0)
    stag_in = t_cols1[2].text_input("Stagger Seq", "80,120,100")
    t_data["stagger"] = [float(x.strip()) for x in stag_in.split(",")] if stag_in else [100.0]
elif t_pri_type == "Custom":
    cust_in = t_cols1[1].text_input("PW:PRI Pairs", "5:100, 10:150")
    try:
        t_data["custom_seq"] = [(float(p.split(":")[0].strip()), float(p.split(":")[1].strip())) for p in
                                cust_in.split(",")]
    except:
        t_data["custom_seq"] = [(5.0, 100.0)]

t_cols2 = st.columns([1.2, 1, 1, 1.2, 4.3], gap="small")
frame_type = t_cols2[0].selectbox("Framing", ["None", "Regular", "Custom"])
t_data["frame_type"] = frame_type

if frame_type == "Regular":
    t_data["frame_on"] = t_cols2[1].number_input("ON [ms]", 1.0, 10000.0, 50.0)
    t_data["frame_off"] = t_cols2[2].number_input("OFF [ms]", 1.0, 10000.0, 150.0)
    t_data["sync"] = t_cols2[3].selectbox("Internal Sync", ["Continuous", "Reset"])
elif frame_type == "Custom":
    cust_frm = t_cols2[1].text_input("ON:OFF Pairs", "20:180, 30:270")
    try:
        t_data["frame_seq"] = [(float(p.split(":")[0].strip()), float(p.split(":")[1].strip())) for p in
                               cust_frm.split(",")]
    except:
        t_data["frame_seq"] = [(20.0, 180.0)]
    t_data["sync"] = t_cols2[3].selectbox("Internal Sync", ["Continuous", "Reset"])
else:
    t_data["sync"] = "Continuous"

st.divider()


# =========================================================
# פונקציות הסימולציה
# =========================================================
def generate_pulses(th, time_limit, offset_internal, offset_frame):
    windows = []
    if th['frame_type'] == "None":
        windows.append((-999999, 999999))
    else:
        f_seq = [(th['frame_on'], th['frame_off'])] if th['frame_type'] == "Regular" else th['frame_seq']
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
            return th['pw'], th['base_pri'] * np.random.uniform(1 - th['jitter'] / 100, 1 + th['jitter'] / 100)
        elif th['type'] == "Staggered":
            return th['pw'], th['stagger'][idx % len(th['stagger'])]
        elif th['type'] == "Custom":
            return th['custom_seq'][idx % len(th['custom_seq'])]

    if th['frame_type'] != "None" and th['sync'] == "Reset":
        for w_start, w_end in windows:
            if w_end < 0: continue
            p_t, p_idx = w_start, 0
            while p_t < w_end:
                pw, pri = get_pw_pri(p_idx)
                p_end = p_t + pw
                o_start, o_end = max(w_start, p_t), min(w_end, p_end)
                if o_start < o_end and o_end >= 0 and o_start < time_limit: pulses.append((o_start, o_end))
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
        p_idx, w_idx = 0, 0
        valid_windows = [w for w in windows if w[1] >= p_t]

        while p_t < time_limit:
            pw, pri = get_pw_pri(p_idx)
            p_end = p_t + pw
            while w_idx < len(valid_windows) and valid_windows[w_idx][1] < p_t: w_idx += 1
            temp_w = w_idx
            while temp_w < len(valid_windows) and valid_windows[temp_w][0] < p_end:
                w_start, w_end = valid_windows[temp_w]
                o_start, o_end = max(w_start, p_t), min(w_end, p_end)
                if o_start < o_end and o_end >= 0 and o_start < time_limit: pulses.append((o_start, o_end))
                temp_w += 1
            p_t += pri
            p_idx += 1
    return pulses


def check_lock(dwell, revisit):
    if t_data['type'] == "Staggered":
        internal_period = sum(t_data['stagger'])
    elif t_data['type'] == "Custom":
        internal_period = sum(p[1] for p in t_data['custom_seq'])
    else:
        internal_period = t_data['base_pri']

    if t_data['frame_type'] == "Regular":
        f_period = t_data['frame_on'] + t_data['frame_off']
    elif t_data['frame_type'] == "Custom":
        f_period = sum(f[0] + f[1] for f in t_data['frame_seq'])
    else:
        f_period = 0

    offset_frame = np.random.uniform(0, f_period) if f_period > 0 else 0
    offset_internal = np.random.uniform(0, internal_period) if (
                t_data['sync'] == "Continuous" or t_data['frame_type'] == "None") else 0

    pulses = generate_pulses(t_data, max_time + 50, offset_internal, offset_frame)

    t_curr = np.random.uniform(-dwell, revisit - dwell)
    hits, misses = 0, 0

    while t_curr < max_time:
        d_start, d_end = t_curr, t_curr + dwell
        obs_start, obs_end = max(0, d_start), min(max_time, d_end)

        if obs_start < obs_end:
            hit = any((min(obs_end, p[1]) - max(obs_start, p[0])) > 0 for p in pulses)
            if hit:
                hits += 1
                misses = 0
                if hits >= age_in: return True
            else:
                misses += 1
                if misses >= age_out: hits = 0
        t_curr += revisit
    return False


def evaluate_poi(dwell, revisit, trials):
    success = sum(1 for _ in range(trials) if check_lock(dwell, revisit))
    return (success / trials) * 100.0


def check_physical_limit(trials=1000):
    if t_data['type'] == "Staggered":
        internal_period = sum(t_data['stagger'])
    elif t_data['type'] == "Custom":
        internal_period = sum(p[1] for p in t_data['custom_seq'])
    else:
        internal_period = t_data['base_pri']

    if t_data['frame_type'] == "Regular":
        f_period = t_data['frame_on'] + t_data['frame_off']
    elif t_data['frame_type'] == "Custom":
        f_period = sum(f[0] + f[1] for f in t_data['frame_seq'])
    else:
        f_period = 0

    success = 0
    for _ in range(trials):
        offset_frame = np.random.uniform(0, f_period) if f_period > 0 else 0
        offset_internal = np.random.uniform(0, internal_period) if (
                    t_data['sync'] == "Continuous" or t_data['frame_type'] == "None") else 0

        pulses = generate_pulses(t_data, max_time, offset_internal, offset_frame)

        valid_pulses = sum(1 for p in pulses if p[0] < max_time and p[1] > 0)
        if valid_pulses >= age_in:
            success += 1

    return (success / trials) * 100.0


# =========================================================
# אלגוריתם האופטימיזציה (Smart Binary Search + Duty Cycle)
# =========================================================
if st.button("🚀 Run Auto-Tuner (Find Optimal Rx)", type="primary"):

    progress_bar = st.progress(0.0)
    status_text = st.empty()

    # --- Step 0: בדיקת היתכנות פיזיקלית ---
    status_text.text("Step 0: Checking physical pulse emission limits...")
    theoretical_max_poi = check_physical_limit(trials=1000)

    if theoretical_max_poi < target_poi:
        st.error(
            f"❌ בלתי אפשרי פיזיקלית! האיום מייצר מספיק פולסים בתוך הזמן המוגדר רק ב-{theoretical_max_poi:.1f}% מהמקרים. נסה להקטין את ה-Age In, או להגדיל את ה-Max Time.")
        progress_bar.empty()
    else:
        # --- Step 1: הגדרת רשת החיפוש (Dwell Candidates) ---
        if t_pri_type == "Custom":
            min_pw = min(p[0] for p in t_data['custom_seq'])
        else:
            min_pw = t_data['pw']

        if t_pri_type == "Staggered":
            avg_pri = sum(t_data['stagger']) / len(t_data['stagger'])
        elif t_pri_type == "Custom":
            avg_pri = sum(p[1] for p in t_data['custom_seq']) / len(t_data['custom_seq'])
        else:
            avg_pri = t_data['base_pri']

        # סדרת Dwells לבדיקה
        candidates = [min_pw, min_pw * 2, avg_pri * 0.25, avg_pri * 0.5, avg_pri]
        dwell_candidates = sorted(list(set([round(d, 2) for d in candidates if d >= min_pw])))

        results = []
        upper_rev_bound = (max_time / age_in)

        for idx, d_cand in enumerate(dwell_candidates):
            status_text.text(f"Scanning Dwell: {d_cand:.1f} ms... ({idx + 1}/{len(dwell_candidates)})")

            low_r = d_cand + 0.1
            high_r = upper_rev_bound
            best_rev = None

            # חיפוש בינארי (Binary Search)
            while (high_r - low_r) > 1.0:
                mid_r = (low_r + high_r) / 2.0
                poi = evaluate_poi(d_cand, mid_r, int(mc_trials / 4))

                if poi >= target_poi:
                    best_rev = mid_r
                    low_r = mid_r
                else:
                    high_r = mid_r

                    # אימות סופי (Fine Validation) וחישוב Duty Cycle
            if best_rev is not None:
                fine_poi = evaluate_poi(d_cand, best_rev, mc_trials)
                if fine_poi >= target_poi:
                    duty_cycle = (d_cand / best_rev) * 100.0
                    results.append({
                        "Dwell [ms]": round(d_cand, 2),
                        "Max Revisit [ms]": round(best_rev, 2),
                        "Duty Cycle [%]": round(duty_cycle, 2),
                        "Achieved POI [%]": round(fine_poi, 2)
                    })
                else:
                    safe_r = best_rev - 2.0
                    if safe_r > d_cand:
                        fine_poi_safe = evaluate_poi(d_cand, safe_r, mc_trials)
                        if fine_poi_safe >= target_poi:
                            duty_cycle_safe = (d_cand / safe_r) * 100.0
                            results.append({
                                "Dwell [ms]": round(d_cand, 2),
                                "Max Revisit [ms]": round(safe_r, 2),
                                "Duty Cycle [%]": round(duty_cycle_safe, 2),
                                "Achieved POI [%]": round(fine_poi_safe, 2)
                            })

            progress_bar.progress((idx + 1) / len(dwell_candidates))

        status_text.text("✅ Optimization Complete!")
        progress_bar.empty()

        # --- הצגת התוצאות ---
        if results:
            st.success("🎯 נמצאו פרמטרים אופטימליים העומדים בדרישות!")

            # הפיכה לדאטה-פריים ומיון לפי Duty Cycle (מהטוב ביותר לגרוע ביותר)
            df = pd.DataFrame(results)
            df = df.sort_values(by="Duty Cycle [%]", ascending=True).reset_index(drop=True)

            # הדגשת השורה המנצחת (ה-Duty Cycle הנמוך ביותר)
            st.dataframe(df.style.highlight_min(subset=['Duty Cycle [%]'], color='lightgreen'))

            st.info(
                "💡 **טיפ:** השורה המודגשת בירוק היא ה-'זולה' ביותר למערכת. היא תופסת את המקלט להכי פחות זמן כולל, ועדיין מבטיחה את ה-POI שדרשת!")
        else:
            st.warning(
                "⚠️ המערכת לא הצליחה למצוא Revisit בטוח עבור ה-Dwells שנבדקו. הדרישות מחמירות מדי עבור זמני ה-OFF של האיום.")