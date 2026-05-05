import streamlit as st
import numpy as np
import plotly.graph_objects as go
from numba import njit, types
from numba.typed import List
import time

# Set up the page layout to wide mode for better data visualization
st.set_page_config(page_title="Multi-Threat EW Professional Simulator", layout="wide")

custom_css = """
<style>
[data-testid="stNumberInput"] button { display: none !important; }
input[type="number"] { -moz-appearance: textfield; }
input[type="number"]::-webkit-inner-spin-button,
input[type="number"]::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
div[data-testid="column"] { padding-left: 0.15rem !important; padding-right: 0.15rem !important; }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)
st.title("🛡️ Professional Multi-Threat EW – Phase Uncertain POI")


# =========================================================
# NUMBA ENGINE FUNCTIONS
# All functions below use only plain arrays/scalars — no dicts, no lists of objects.
# UI and results processing above/below are completely unchanged.
# =========================================================

@njit(cache=True)
def generate_pulses_fixed(pw, base_pri, frame_type, frame_on, frame_off,
                           frame_seq_on, frame_seq_off, sync_reset,
                           offset_internal, offset_frame, time_limit):
    """
    Generate pulse (start, end) pairs for a Fixed or Jittered PRI threat.
    frame_type: 0=None, 1=Regular, 2=Custom
    sync_reset: True if sync==Reset
    Returns flat array [s0,e0, s1,e1, ...]
    """
    MAX_PULSES = 100000
    out = np.empty(MAX_PULSES * 2, dtype=np.float64)
    count = 0

    # Build frame windows
    MAX_WIN = 50000
    win_start = np.empty(MAX_WIN, dtype=np.float64)
    win_end   = np.empty(MAX_WIN, dtype=np.float64)
    n_win = 0

    if frame_type == 0:
        win_start[0] = -999999.0
        win_end[0]   =  999999.0
        n_win = 1
    else:
        n_frames = len(frame_seq_on)
        f_period = 0.0
        for k in range(n_frames):
            f_period += frame_seq_on[k] + frame_seq_off[k]
        t_f = offset_frame - f_period * 2.0
        f_idx = 0
        while t_f < time_limit and n_win < MAX_WIN:
            win_start[n_win] = t_f
            win_end[n_win]   = t_f + frame_seq_on[f_idx]
            n_win += 1
            t_f  += frame_seq_on[f_idx] + frame_seq_off[f_idx]
            f_idx = (f_idx + 1) % n_frames

    # Generate pulses
    if frame_type != 0 and sync_reset:
        for wi in range(n_win):
            ws, we = win_start[wi], win_end[wi]
            if we < 0.0:
                continue
            p_t = ws
            while p_t < we and count < MAX_PULSES:
                p_end  = p_t + pw
                o_s    = ws   if p_t   < ws   else p_t
                o_e    = we   if p_end > we   else p_end
                if o_s < o_e and o_e >= 0.0 and o_s < time_limit:
                    out[count*2]     = o_s
                    out[count*2 + 1] = o_e
                    count += 1
                p_t += base_pri
    else:
        p_t   = offset_internal - base_pri * 2.0
        w_idx = 0
        while p_t < time_limit and count < MAX_PULSES:
            p_end = p_t + pw
            while w_idx < n_win and win_end[w_idx] < p_t:
                w_idx += 1
            tw = w_idx
            while tw < n_win and win_start[tw] < p_end:
                ws, we = win_start[tw], win_end[tw]
                o_s = ws   if p_t   < ws   else p_t
                o_e = we   if p_end > we   else p_end
                if o_s < o_e and o_e >= 0.0 and o_s < time_limit:
                    out[count*2]     = o_s
                    out[count*2 + 1] = o_e
                    count += 1
                tw += 1
            p_t += base_pri

    return out[:count*2]


@njit(cache=True)
def generate_pulses_staggered(pw, stagger, frame_type, frame_on, frame_off,
                               frame_seq_on, frame_seq_off, sync_reset,
                               offset_internal, offset_frame, time_limit):
    MAX_PULSES = 100000
    out = np.empty(MAX_PULSES * 2, dtype=np.float64)
    count = 0

    MAX_WIN = 50000
    win_start = np.empty(MAX_WIN, dtype=np.float64)
    win_end   = np.empty(MAX_WIN, dtype=np.float64)
    n_win = 0

    if frame_type == 0:
        win_start[0] = -999999.0
        win_end[0]   =  999999.0
        n_win = 1
    else:
        n_frames = len(frame_seq_on)
        f_period = 0.0
        for k in range(n_frames):
            f_period += frame_seq_on[k] + frame_seq_off[k]
        t_f = offset_frame - f_period * 2.0
        f_idx = 0
        while t_f < time_limit and n_win < MAX_WIN:
            win_start[n_win] = t_f
            win_end[n_win]   = t_f + frame_seq_on[f_idx]
            n_win += 1
            t_f  += frame_seq_on[f_idx] + frame_seq_off[f_idx]
            f_idx = (f_idx + 1) % n_frames

    n_stag = len(stagger)
    int_per = 0.0
    for s in stagger:
        int_per += s

    if frame_type != 0 and sync_reset:
        for wi in range(n_win):
            ws, we = win_start[wi], win_end[wi]
            if we < 0.0:
                continue
            p_t, p_idx = ws, 0
            while p_t < we and count < MAX_PULSES:
                pri   = stagger[p_idx % n_stag]
                p_end = p_t + pw
                o_s   = ws if p_t   < ws else p_t
                o_e   = we if p_end > we else p_end
                if o_s < o_e and o_e >= 0.0 and o_s < time_limit:
                    out[count*2]     = o_s
                    out[count*2 + 1] = o_e
                    count += 1
                p_t  += pri
                p_idx += 1
    else:
        p_t   = offset_internal - int_per * 2.0
        p_idx = 0
        w_idx = 0
        while p_t < time_limit and count < MAX_PULSES:
            pri   = stagger[p_idx % n_stag]
            p_end = p_t + pw
            while w_idx < n_win and win_end[w_idx] < p_t:
                w_idx += 1
            tw = w_idx
            while tw < n_win and win_start[tw] < p_end:
                ws, we = win_start[tw], win_end[tw]
                o_s = ws if p_t   < ws else p_t
                o_e = we if p_end > we else p_end
                if o_s < o_e and o_e >= 0.0 and o_s < time_limit:
                    out[count*2]     = o_s
                    out[count*2 + 1] = o_e
                    count += 1
                tw += 1
            p_t  += pri
            p_idx += 1

    return out[:count*2]


@njit(cache=True)
def generate_pulses_custom(pw_arr, pri_arr, frame_type, frame_on, frame_off,
                            frame_seq_on, frame_seq_off, sync_reset,
                            offset_internal, offset_frame, time_limit):
    MAX_PULSES = 100000
    out = np.empty(MAX_PULSES * 2, dtype=np.float64)
    count = 0

    MAX_WIN = 50000
    win_start = np.empty(MAX_WIN, dtype=np.float64)
    win_end   = np.empty(MAX_WIN, dtype=np.float64)
    n_win = 0

    if frame_type == 0:
        win_start[0] = -999999.0
        win_end[0]   =  999999.0
        n_win = 1
    else:
        n_frames = len(frame_seq_on)
        f_period = 0.0
        for k in range(n_frames):
            f_period += frame_seq_on[k] + frame_seq_off[k]
        t_f = offset_frame - f_period * 2.0
        f_idx = 0
        while t_f < time_limit and n_win < MAX_WIN:
            win_start[n_win] = t_f
            win_end[n_win]   = t_f + frame_seq_on[f_idx]
            n_win += 1
            t_f  += frame_seq_on[f_idx] + frame_seq_off[f_idx]
            f_idx = (f_idx + 1) % n_frames

    n_seq   = len(pw_arr)
    int_per = 0.0
    for k in range(n_seq):
        int_per += pri_arr[k]

    if frame_type != 0 and sync_reset:
        for wi in range(n_win):
            ws, we = win_start[wi], win_end[wi]
            if we < 0.0:
                continue
            p_t, p_idx = ws, 0
            while p_t < we and count < MAX_PULSES:
                pw_k  = pw_arr[p_idx % n_seq]
                pri_k = pri_arr[p_idx % n_seq]
                p_end = p_t + pw_k
                o_s   = ws if p_t   < ws else p_t
                o_e   = we if p_end > we else p_end
                if o_s < o_e and o_e >= 0.0 and o_s < time_limit:
                    out[count*2]     = o_s
                    out[count*2 + 1] = o_e
                    count += 1
                p_t  += pri_k
                p_idx += 1
    else:
        p_t   = offset_internal - int_per * 2.0
        p_idx = 0
        w_idx = 0
        while p_t < time_limit and count < MAX_PULSES:
            pw_k  = pw_arr[p_idx % n_seq]
            pri_k = pri_arr[p_idx % n_seq]
            p_end = p_t + pw_k
            while w_idx < n_win and win_end[w_idx] < p_t:
                w_idx += 1
            tw = w_idx
            while tw < n_win and win_start[tw] < p_end:
                ws, we = win_start[tw], win_end[tw]
                o_s = ws if p_t   < ws else p_t
                o_e = we if p_end > we else p_end
                if o_s < o_e and o_e >= 0.0 and o_s < time_limit:
                    out[count*2]     = o_s
                    out[count*2 + 1] = o_e
                    count += 1
                tw += 1
            p_t  += pri_k
            p_idx += 1

    return out[:count*2]


@njit(cache=True)
def build_rx_dwells(rx_dwell_arr, rx_revisit_arr,
                    rx_frame_type, rx_frame_seq_on, rx_frame_seq_off,
                    rx_sync_reset, rx_dev, rx_dev_is_pct,
                    rx_offset_frame, rx_offset_internal,
                    time_limit):
    MAX_DWELLS = 200000
    out = np.empty(MAX_DWELLS * 2, dtype=np.float64)
    count = 0

    MAX_WIN = 50000
    win_start = np.empty(MAX_WIN, dtype=np.float64)
    win_end   = np.empty(MAX_WIN, dtype=np.float64)
    n_win = 0

    if rx_frame_type == 0:
        win_start[0] = -999999.0
        win_end[0]   =  999999.0
        n_win = 1
    else:
        n_frames = len(rx_frame_seq_on)
        f_period = 0.0
        for k in range(n_frames):
            f_period += rx_frame_seq_on[k] + rx_frame_seq_off[k]
        t_f = rx_offset_frame - f_period * 2.0
        f_idx = 0
        while t_f < time_limit and n_win < MAX_WIN:
            win_start[n_win] = t_f
            win_end[n_win]   = t_f + rx_frame_seq_on[f_idx]
            n_win += 1
            t_f  += rx_frame_seq_on[f_idx] + rx_frame_seq_off[f_idx]
            f_idx = (f_idx + 1) % n_frames

    n_seq   = len(rx_dwell_arr)
    int_per = 0.0
    for k in range(n_seq):
        int_per += rx_revisit_arr[k]

    def get_params(idx):
        d = rx_dwell_arr[idx % n_seq]
        r = rx_revisit_arr[idx % n_seq]
        if rx_dev > 0.0:
            rnd = np.random.uniform(-1.0, 1.0)
            if rx_dev_is_pct:
                r = r * (1.0 + rx_dev / 100.0 * rnd)
            else:
                r = r + rx_dev * rnd
        return d, r

    if rx_frame_type != 0 and rx_sync_reset:
        for wi in range(n_win):
            ws, we = win_start[wi], win_end[wi]
            if we < 0.0:
                continue
            p_t, p_idx = ws, 0
            while p_t < we and count < MAX_DWELLS:
                d_val, r_val = get_params(p_idx)
                d_end = p_t + d_val
                o_s   = ws if p_t  < ws else p_t
                o_e   = we if d_end > we else d_end
                if o_s < o_e and o_e >= 0.0 and o_s < time_limit:
                    out[count*2]     = o_s
                    out[count*2 + 1] = o_e
                    count += 1
                p_t  += r_val
                p_idx += 1
    else:
        p_t   = rx_offset_internal - int_per * 2.0
        p_idx = 0
        w_idx = 0
        while p_t < time_limit and count < MAX_DWELLS:
            d_val, r_val = get_params(p_idx)
            d_end = p_t + d_val
            while w_idx < n_win and win_end[w_idx] < p_t:
                w_idx += 1
            tw = w_idx
            while tw < n_win and win_start[tw] < d_end:
                ws, we = win_start[tw], win_end[tw]
                o_s = ws    if p_t  < ws   else p_t
                o_e = we    if d_end > we  else d_end
                if o_s < o_e and o_e >= 0.0 and o_s < time_limit:
                    out[count*2]     = o_s
                    out[count*2 + 1] = o_e
                    count += 1
                tw += 1
            p_t  += r_val
            p_idx += 1

    return out[:count*2]


@njit(cache=True)
def tracker_logic(rx_dwells_flat, all_pulse_flat, pulse_counts,
                  n_threats, min_overlap, age_in, age_out, time_limit):
    """
    Core tracker: given dwells and pulses for all threats,
    return lock_times array (−1 = never locked).
    """
    lock_times = np.full(n_threats, -1.0)
    hits       = np.zeros(n_threats, dtype=np.int64)
    misses     = np.zeros(n_threats, dtype=np.int64)
    is_locked  = np.zeros(n_threats, dtype=np.bool_)

    n_dwells = len(rx_dwells_flat) // 2

    # Build per-threat pulse start indices
    starts = np.zeros(n_threats, dtype=np.int64)
    for i in range(1, n_threats):
        starts[i] = starts[i-1] + pulse_counts[i-1]

    for di in range(n_dwells):
        d_s = rx_dwells_flat[di*2]
        d_e = rx_dwells_flat[di*2 + 1]
        obs_s = 0.0 if d_s < 0.0 else d_s
        obs_e = time_limit if d_e > time_limit else d_e
        if obs_s >= obs_e:
            continue

        all_done = True
        for i in range(n_threats):
            if lock_times[i] >= 0.0:
                continue
            all_done = False

            p_base = starts[i] * 2
            n_p    = pulse_counts[i]
            hit    = False
            for pi in range(n_p):
                p_s = all_pulse_flat[p_base + pi*2]
                p_e = all_pulse_flat[p_base + pi*2 + 1]
                overlap = (obs_e if p_e > obs_e else p_e) - (obs_s if p_s < obs_s else p_s)
                if overlap >= min_overlap:
                    hit = True
                    break

            if hit:
                hits[i]  += 1
                misses[i]  = 0
                if hits[i] >= age_in:
                    is_locked[i]  = True
                    lock_times[i] = obs_e
            else:
                if is_locked[i]:
                    misses[i] += 1
                    if misses[i] >= age_out:
                        is_locked[i] = False
                        hits[i]      = 0
                else:
                    if hits[i] > 0:
                        hits[i] -= 1

        if all_done:
            break

    return lock_times


# =========================================================
# Python wrapper: converts threat dicts → flat arrays, runs one trial
# =========================================================

def build_flat_pulses(th, time_limit):
    """Convert one threat dict into flat pulse array via the right @njit function."""
    # Frame arrays
    if th['frame_type'] == "None":
        ft = 0
        fon  = np.array([1.0], dtype=np.float64)
        foff = np.array([1.0], dtype=np.float64)
    elif th['frame_type'] == "Regular":
        ft   = 1
        fon  = np.array([th['frame_on']],  dtype=np.float64)
        foff = np.array([th['frame_off']], dtype=np.float64)
    else:
        ft   = 2
        fon  = np.array([f[0] for f in th['frame_seq']], dtype=np.float64)
        foff = np.array([f[1] for f in th['frame_seq']], dtype=np.float64)

    sync_reset = (th.get('sync', 'Continuous') == 'Reset') and (th['frame_type'] != 'None')

    # Internal period for random offset
    if th['type'] == "Staggered":
        int_per = sum(th['stagger'])
    elif th['type'] == "Custom":
        int_per = sum(p[1] for p in th['custom_seq'])
    else:
        int_per = th['base_pri']

    f_period = float(np.sum(fon + foff)) if ft != 0 else 0.0
    offset_frame    = np.random.uniform(0, f_period)    if f_period > 0 else 0.0
    offset_internal = np.random.uniform(0, int_per)     if (sync_reset is False) else 0.0

    if th['type'] in ("Fixed", "Jittered"):
        if th['type'] == "Jittered":
            if th.get('jitter_type', '%') == '%':
                actual_pri = th['base_pri'] * np.random.uniform(
                    1 - th['jitter']/100.0, 1 + th['jitter']/100.0)
            else:
                actual_pri = th['base_pri'] + np.random.uniform(
                    -th['jitter_abs'], th['jitter_abs'])
        else:
            actual_pri = th['base_pri']

        return generate_pulses_fixed(
            th['pw'], actual_pri, ft,
            fon[0] if ft==1 else 1.0,
            foff[0] if ft==1 else 1.0,
            fon, foff, sync_reset,
            offset_internal, offset_frame, time_limit + 100.0
        )

    elif th['type'] == "Staggered":
        stag = np.array(th['stagger'], dtype=np.float64)
        return generate_pulses_staggered(
            th['pw'], stag, ft,
            fon[0] if ft==1 else 1.0,
            foff[0] if ft==1 else 1.0,
            fon, foff, sync_reset,
            offset_internal, offset_frame, time_limit + 100.0
        )

    else:  # Custom
        pw_arr  = np.array([p[0] for p in th['custom_seq']], dtype=np.float64)
        pri_arr = np.array([p[1] for p in th['custom_seq']], dtype=np.float64)
        return generate_pulses_custom(
            pw_arr, pri_arr, ft,
            fon[0] if ft==1 else 1.0,
            foff[0] if ft==1 else 1.0,
            fon, foff, sync_reset,
            offset_internal, offset_frame, time_limit + 100.0
        )


def run_trial(time_limit, threats_list_local,
              rx_dwell_arr, rx_revisit_arr,
              rx_frame_type_int, rx_frame_seq_on, rx_frame_seq_off,
              rx_sync_reset, rx_dev, rx_dev_is_pct,
              rx_int_per, rx_f_period,
              min_overlap, age_in, age_out):

    # Receiver offsets
    rx_offset_frame    = np.random.uniform(0, rx_f_period)  if rx_f_period > 0 else 0.0
    rx_offset_internal = np.random.uniform(0, rx_int_per)   if not rx_sync_reset else 0.0

    rx_dwells_flat = build_rx_dwells(
        rx_dwell_arr, rx_revisit_arr,
        rx_frame_type_int, rx_frame_seq_on, rx_frame_seq_off,
        rx_sync_reset, rx_dev, rx_dev_is_pct,
        rx_offset_frame, rx_offset_internal, time_limit
    )

    # Build pulses for all threats
    pulse_arrays  = [build_flat_pulses(th, time_limit) for th in threats_list_local]
    pulse_counts  = np.array([len(p)//2 for p in pulse_arrays], dtype=np.int64)

    # Concatenate all pulses into one flat array
    all_pulse_flat = np.concatenate(pulse_arrays) if pulse_arrays else np.empty(0, dtype=np.float64)

    lock_times_arr = tracker_logic(
        rx_dwells_flat, all_pulse_flat, pulse_counts,
        len(threats_list_local), min_overlap, age_in, age_out, time_limit
    )

    return [lt if lt >= 0 else None for lt in lock_times_arr]


# =========================================================
# Main Control Panel: Receiver Setup
# =========================================================
st.markdown("### ⚙️ Receiver Setup")
st.markdown("**1. Base Pattern & Detection Logic**")
r_cols = st.columns([1.3, 1.1, 0.7, 1.1, 0.7, 0.9, 0.7, 0.9, 0.8, 0.8, 1.1], gap="small")

rx_type = r_cols[0].selectbox("Rx Pattern", ["Fixed", "Custom"], key="rx_type")
rx_seq = []
if rx_type == "Fixed":
    rx_dwell_in   = r_cols[1].number_input("Dwell", value=5.0, format="%g")
    rx_dwell_unit = r_cols[2].selectbox("Unit", ["ms", "us"], key="d_unit", label_visibility="hidden")
    rx_d_mult     = 0.001 if rx_dwell_unit == "us" else 1.0
    rx_revisit_in = r_cols[3].number_input("Rev", value=100.0, format="%g")
    rx_rev_unit   = r_cols[4].selectbox("Unit", ["ms", "us"], key="r_unit", label_visibility="hidden")
    rx_r_mult     = 0.001 if rx_rev_unit == "us" else 1.0
    rx_seq        = [(rx_dwell_in * rx_d_mult, rx_revisit_in * rx_r_mult)]
else:
    cust_rx_in = r_cols[1].text_input("Dwell:Rev (ms)", "5:100")
    try:
        rx_seq = [(float(p.split(":")[0]), float(p.split(":")[1])) for p in cust_rx_in.split(",")]
    except:
        rx_seq = [(5.0, 100.0)]

rx_dev_in   = r_cols[5].number_input("Dev", value=0.0, format="%g")
rx_dev_type = r_cols[6].selectbox("Type", ["%", "Abs"], key="rx_dev_type", label_visibility="hidden")
rx_dev      = rx_dev_in
rx_dev_abs  = rx_dev_in if rx_dev_type == "Abs" else 0.0

min_overlap    = r_cols[7].number_input("Overlap[ms]", value=0.0, format="%g")
age_in         = r_cols[8].number_input("Age-In",      value=1)
age_out        = r_cols[9].number_input("Age-Out",     value=1)
max_analysis_t = r_cols[10].number_input("Max Time [ms]", value=1000.0, format="%g")

st.markdown("**2. Scan Strategy & Simulation**")
f_cols = st.columns([1.2, 1.2, 1.2, 1.2, 1.2, 0.9, 2.5], gap="small")

rx_frame_type = f_cols[0].selectbox("Rx Framing", ["None", "Regular", "Custom"], key="rx_frm_type")
rx_frame_seq  = [(50.0, 150.0)]
rx_sync       = "Continuous"

if rx_frame_type == "Regular":
    rx_fpw_in  = f_cols[1].number_input("Frame PW [ms]",  value=50.0,  key="rx_fpw",  format="%g")
    rx_fpri_in = f_cols[2].number_input("Frame PRI [ms]", value=200.0, key="rx_fpri", format="%g")
    rx_sync    = f_cols[3].selectbox("Sync Mode", ["Continuous", "Reset"], key="rx_sync")
    rx_frame_seq = [(rx_fpw_in, max(0.0001, rx_fpri_in - rx_fpw_in))]
elif rx_frame_type == "Custom":
    cust_rx_frm = f_cols[1].text_input("Frame PW:PRI Pairs", "50:200, 60:260", key="rx_cust_frm")
    rx_sync     = f_cols[3].selectbox("Sync Mode", ["Continuous", "Reset"], key="rx_sync")
    try:
        rx_frame_seq = [(float(p.split(":")[0]), max(0.0001, float(p.split(":")[1]) - float(p.split(":")[0])))
                        for p in cust_rx_frm.split(",")]
    except:
        pass

trials     = f_cols[4].number_input("MC Trials", value=30000)
num_threats = f_cols[5].number_input("Threats",   value=1)

st.divider()

# =========================================================
# Multi-Threat Configuration Panels
# =========================================================
st.markdown("### 🎯 Threat Configuration")
threats_list = []

if int(num_threats) > 0:
    tabs = st.tabs([f"🔥 Threat #{i+1}" for i in range(int(num_threats))])
    for i, tab in enumerate(tabs):
        with tab:
            t_cols1 = st.columns([1.2, 1, 0.8, 1, 0.8, 1, 0.8, 1.5], gap="small")
            t_pri_type = t_cols1[0].selectbox("PRI Type", ["Fixed","Jittered","Staggered","Custom"], key=f"type_{i}")
            t_data = {"id": i+1, "type": t_pri_type}

            if t_pri_type == "Fixed":
                pw_in   = t_cols1[1].number_input("PW",  value=5.0,             key=f"pw_{i}",   format="%g")
                pw_unit = t_cols1[2].selectbox("Unit", ["ms","us"],              key=f"pw_u_{i}", label_visibility="hidden")
                pri_in  = t_cols1[3].number_input("PRI", value=100.0+(i*20),    key=f"pri_{i}",  format="%g")
                pri_unit= t_cols1[4].selectbox("Unit", ["ms","us"],              key=f"pri_u_{i}",label_visibility="hidden")
                t_data["pw"]       = pw_in  * (0.001 if pw_unit  == "us" else 1.0)
                t_data["base_pri"] = pri_in * (0.001 if pri_unit == "us" else 1.0)

            elif t_pri_type == "Jittered":
                pw_in   = t_cols1[1].number_input("PW",       value=5.0,   key=f"pw_{i}",   format="%g")
                pw_unit = t_cols1[2].selectbox("Unit", ["ms","us"],         key=f"pw_u_{i}", label_visibility="hidden")
                pri_in  = t_cols1[3].number_input("Base PRI", value=100.0, key=f"bpri_{i}", format="%g")
                pri_unit= t_cols1[4].selectbox("Unit", ["ms","us"],         key=f"pri_u_{i}",label_visibility="hidden")
                jit_in  = t_cols1[5].number_input("Jitter",   value=10.0,  key=f"jit_{i}",  format="%g")
                jit_type= t_cols1[6].selectbox("Type", ["%","Abs"],         key=f"jit_type_{i}", label_visibility="hidden")
                t_mult  = 0.001 if pri_unit == "us" else 1.0
                t_data["pw"]          = pw_in * (0.001 if pw_unit == "us" else 1.0)
                t_data["base_pri"]    = pri_in * t_mult
                t_data["jitter"]      = jit_in
                t_data["jitter_type"] = jit_type
                if jit_type == "Abs":
                    t_data["jitter_abs"] = jit_in * t_mult

            elif t_pri_type == "Staggered":
                pw_in   = t_cols1[1].number_input("PW", value=5.0, key=f"pw_{i}", format="%g")
                pw_unit = t_cols1[2].selectbox("Unit", ["ms","us"], key=f"pw_u_{i}", label_visibility="hidden")
                t_data["pw"] = pw_in * (0.001 if pw_unit == "us" else 1.0)
                stag_in = t_cols1[3].text_input("Stagger Seq (ms)", "80,120,100", key=f"stag_{i}")
                try:
                    t_data["stagger"] = [float(x.strip()) for x in stag_in.split(",")]
                except:
                    t_data["stagger"] = [100.0]

            elif t_pri_type == "Custom":
                cust_in = t_cols1[1].text_input("PW:PRI Pairs (ms)", "5:100, 10:150", key=f"cust_pri_{i}")
                try:
                    t_data["custom_seq"] = [(float(p.split(":")[0]), float(p.split(":")[1]))
                                            for p in cust_in.split(",")]
                except:
                    t_data["custom_seq"] = [(5.0, 100.0)]

            t_cols2 = st.columns([1.2, 1.2, 1.2, 1.2, 4.3], gap="small")
            frame_type = t_cols2[0].selectbox("Framing", ["None","Regular","Custom"], key=f"frm_type_{i}")
            t_data["frame_type"] = frame_type

            if frame_type == "Regular":
                fpw_in  = t_cols2[1].number_input("Frame PW [ms]",  value=50.0,  key=f"fpw_{i}",  format="%g")
                fpri_in = t_cols2[2].number_input("Frame PRI [ms]", value=200.0, key=f"fpri_{i}", format="%g")
                t_data["frame_on"]  = fpw_in
                t_data["frame_off"] = max(0.0001, fpri_in - fpw_in)
                t_data["sync"]      = t_cols2[3].selectbox("Internal Sync", ["Continuous","Reset"], key=f"sync_{i}")
            elif frame_type == "Custom":
                cust_frm = t_cols2[1].text_input("Frame PW:PRI Pairs", "20:200, 30:300", key=f"cust_frm_{i}")
                try:
                    t_data["frame_seq"] = [(float(p.split(":")[0]),
                                            max(0.0001, float(p.split(":")[1]) - float(p.split(":")[0])))
                                           for p in cust_frm.split(",")]
                except:
                    t_data["frame_seq"] = [(20.0, 180.0), (30.0, 270.0)]
                t_data["sync"] = t_cols2[3].selectbox("Internal Sync", ["Continuous","Reset"], key=f"sync_{i}")
            else:
                t_data["sync"] = "Continuous"

            threats_list.append(t_data)

st.markdown("---")

# =========================================================
# Pre-compute receiver arrays (shared across all trials)
# =========================================================
rx_dwell_arr   = np.array([s[0] for s in rx_seq],  dtype=np.float64)
rx_revisit_arr = np.array([s[1] for s in rx_seq],  dtype=np.float64)

if rx_frame_type == "None":
    rx_frame_type_int = 0
    rx_frame_seq_on   = np.array([1.0], dtype=np.float64)
    rx_frame_seq_off  = np.array([1.0], dtype=np.float64)
elif rx_frame_type == "Regular":
    rx_frame_type_int = 1
    rx_frame_seq_on   = np.array([rx_frame_seq[0][0]], dtype=np.float64)
    rx_frame_seq_off  = np.array([rx_frame_seq[0][1]], dtype=np.float64)
else:
    rx_frame_type_int = 2
    rx_frame_seq_on   = np.array([f[0] for f in rx_frame_seq], dtype=np.float64)
    rx_frame_seq_off  = np.array([f[1] for f in rx_frame_seq], dtype=np.float64)

rx_sync_reset  = (rx_sync == "Reset") and (rx_frame_type != "None")
rx_dev_is_pct  = (rx_dev_type == "%")
rx_int_per     = float(np.sum(rx_revisit_arr))
rx_f_period    = float(np.sum(rx_frame_seq_on + rx_frame_seq_off)) if rx_frame_type != "None" else 0.0

# =========================================================
# Apply button + Session State
# =========================================================
run_sim = st.button("▶️ Apply & Run Simulation", type="primary", use_container_width=True)

if "sim_results" not in st.session_state:
    st.session_state.sim_results     = None
    st.session_state.sim_elapsed     = None
    st.session_state.sim_trials_done = None

if run_sim:
    # Warm-up notice on first ever run
    if not st.session_state.get("numba_warmed", False):
        st.info("⚙️ First run: Numba is compiling the engine (~5-10s one-time cost). All subsequent runs will be fast.")

    results     = []
    progress_bar = st.progress(0)
    status_text  = st.empty()
    start_time   = time.time()

    for idx in range(int(trials)):
        results.append(run_trial(
            max_analysis_t, threats_list,
            rx_dwell_arr, rx_revisit_arr,
            rx_frame_type_int, rx_frame_seq_on, rx_frame_seq_off,
            rx_sync_reset, rx_dev, rx_dev_is_pct,
            rx_int_per, rx_f_period,
            min_overlap, int(age_in), int(age_out)
        ))

        if idx % 500 == 0 or idx == int(trials) - 1:
            pct     = (idx + 1) / int(trials)
            elapsed = time.time() - start_time
            eta     = (elapsed / pct) * (1 - pct) if pct > 0 else 0
            eta_str = f"| ETA: {eta:.1f}s" if eta > 1 else "| Almost done..."
            progress_bar.progress(pct)
            status_text.caption(
                f"⏳ Running... {int(pct*100)}%  "
                f"({idx+1:,} / {int(trials):,} trials)  "
                f"| Elapsed: {elapsed:.1f}s {eta_str}"
            )

    elapsed_total = time.time() - start_time
    progress_bar.empty()
    status_text.empty()

    st.session_state.sim_results     = results
    st.session_state.sim_elapsed     = elapsed_total
    st.session_state.sim_trials_done = int(trials)
    st.session_state.numba_warmed    = True
    st.success(f"✅ Done! {int(trials):,} trials completed in {elapsed_total:.2f}s")

if st.session_state.sim_results is None:
    st.info("👆 Configure parameters and press **Apply** to run the simulation.")
    st.stop()

all_trials_results = st.session_state.sim_results

# =========================================================
# Results Processing & Display  (identical to original)
# =========================================================
time_axis = np.linspace(0, max_analysis_t, 30)
combined_lock_times = []
for res in all_trials_results:
    valid_times = [t for t in res if t is not None]
    if valid_times:
        combined_lock_times.append(min(valid_times))

final_combined_poi = (len(combined_lock_times) / len(all_trials_results)) * 100
mtti_combined      = np.mean(combined_lock_times) if combined_lock_times else 0
combined_poi_curve = [(sum(1 for ct in combined_lock_times if ct <= t_pt) / len(all_trials_results)) * 100
                      for t_pt in time_axis]

threat_names           = [f"Threat #{i+1}" for i in range(len(threats_list))]
individual_pois_final  = []
individual_mttis       = []
individual_pois_curve  = []

for i in range(len(threats_list)):
    t_times = [res[i] for res in all_trials_results if res[i] is not None]
    individual_pois_final.append((len(t_times) / len(all_trials_results)) * 100)
    individual_mttis.append(np.mean(t_times) if t_times else 0)
    individual_pois_curve.append(
        [(sum(1 for res in all_trials_results if res[i] is not None and res[i] <= t_pt)
          / len(all_trials_results)) * 100 for t_pt in time_axis]
    )

st.subheader("📊 Results")
st.caption(f"⚙️ Simulation run with **{len(all_trials_results):,}** MC trials. "
           f"(Graph X-axis normalized to milliseconds `[ms]`)")

to_show = st.multiselect("Select metrics to display:", ["Combined POI"] + threat_names, default=["Combined POI"])
selected_threat_names = [name for name in to_show if name != "Combined POI"]
show_dynamic_combined, dyn_poi_final, dyn_mtti, dyn_poi_curve = False, 0, 0, []

if len(selected_threat_names) > 1:
    show_dynamic_combined = st.checkbox(
        f"Show Dynamic Combined (OR) for {len(selected_threat_names)} selected threats", value=True)
    if show_dynamic_combined:
        selected_indices = [int(name.split('#')[1]) - 1 for name in selected_threat_names]
        dyn_lock_times   = []
        for res in all_trials_results:
            valid_times = [res[i] for i in selected_indices if res[i] is not None]
            if valid_times:
                dyn_lock_times.append(min(valid_times))
        dyn_poi_final = (len(dyn_lock_times) / len(all_trials_results)) * 100
        dyn_mtti      = np.mean(dyn_lock_times) if dyn_lock_times else 0
        dyn_poi_curve = [(sum(1 for ct in dyn_lock_times if ct <= t_pt) / len(all_trials_results)) * 100
                         for t_pt in time_axis]

num_metrics = len(to_show) + (1 if show_dynamic_combined else 0)
if num_metrics > 0:
    cols    = st.columns(num_metrics)
    col_idx = 0
    if show_dynamic_combined:
        cols[col_idx].metric(f"🎯 Selected Combined (OR)", f"{dyn_poi_final:.3f}%",
                             f"MTTI: {dyn_mtti:.1f} ms" if dyn_mtti > 0 else "MTTI: N/A", delta_color="off")
        col_idx += 1
    for name in to_show:
        if name == "Combined POI":
            cols[col_idx].metric("🎯 Combined POI (All)", f"{final_combined_poi:.3f}%",
                                 f"MTTI: {mtti_combined:.1f} ms" if mtti_combined > 0 else "MTTI: N/A",
                                 delta_color="off")
        else:
            t_idx = int(name.split('#')[1]) - 1
            cols[col_idx].metric(f"🎯 {name} POI", f"{individual_pois_final[t_idx]:.3f}%",
                                 f"MTTI: {individual_mttis[t_idx]:.1f} ms" if individual_mttis[t_idx] > 0
                                 else "MTTI: N/A", delta_color="off")
        col_idx += 1
else:
    st.warning("⚠️ Please select at least one metric from the dropdown to view results.")

st.divider()
fig_poi = go.Figure()

if "Combined POI" in to_show:
    fig_poi.add_trace(go.Scatter(x=time_axis, y=combined_poi_curve,
                                 name="Combined (All Threats)",
                                 line=dict(color='#00CC96', width=4, dash='dash')))
if show_dynamic_combined:
    fig_poi.add_trace(go.Scatter(x=time_axis, y=dyn_poi_curve,
                                 name="Combined (Selected OR)",
                                 line=dict(color='#FF8C00', width=4, dash='dot')))
for i, name in enumerate(threat_names):
    if name in to_show:
        t_idx = int(name.split('#')[1]) - 1
        fig_poi.add_trace(go.Scatter(x=time_axis, y=individual_pois_curve[t_idx],
                                     name=f"{name} (MTTI: {individual_mttis[t_idx]:.1f}ms)",
                                     mode='lines'))

fig_poi.update_layout(title="Cumulative POI over Time",
                      xaxis_title="Time [ms]", yaxis_title="POI (%)",
                      yaxis_range=[-2, 105], height=500)
st.plotly_chart(fig_poi, use_container_width=True)