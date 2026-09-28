import requests
import pandas as pd
import streamlit as st
st.set_page_config(page_title="Sea conditions near the shore", layout="centered")
# ===== EDIT THESE =====
SPOT = {"name": "Juhu, Mumbai (offshore point)", "lat": 19.10, "lon": 72.79}
LIMITS = {
    "calm":    {"wave": 1.0,  "wind": 20},   # below these = Calm
    "caution": {"wave": 1.75, "wind": 30},   # below these = Caution, above = Rough
}
THRESHOLD_SOURCE = "[write your source here]"
# ======================

NAMES = {-1: "No data", 0: "Calm", 1: "Caution", 2: "Rough"}
# level: (background, text colour, timeline colour)
COLORS = {
    -1: ("#4a5a63", "#ffffff", "#8a9aa3"),
    0:  ("#1f6f4d", "#ffffff", "#2f9e6b"),
    1:  ("#f0b429", "#1b1b1b", "#f0b429"),
    2:  ("#a12f2f", "#ffffff", "#d64545"),
}
MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
@st.cache_data(ttl=900)  # reuse data for 15 minutes
def fetch_data(lat, lon):
    params = {"latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 2}
    m = requests.get(
        MARINE_URL,
        params={**params, "hourly": "wave_height,wave_period,sea_level_height_msl"},
        timeout=15,
    )
    m.raise_for_status()
    w = requests.get(WEATHER_URL, params={**params, "hourly": "wind_speed_10m"}, timeout=15)
    w.raise_for_status()
    marine_json = m.json()
    df_marine = pd.DataFrame(marine_json["hourly"])
    df_wind = pd.DataFrame(w.json()["hourly"])
    df = df_marine.merge(df_wind, on="time", how="left")
    df["time"] = pd.to_datetime(df["time"])
    return df, marine_json["timezone"]
def rate(wave, wind):
    if pd.isna(wave) or pd.isna(wind):
        return -1
    w = 0 if wave < LIMITS["calm"]["wave"] else 1 if wave < LIMITS["caution"]["wave"] else 2
    d = 0 if wind < LIMITS["calm"]["wind"] else 1 if wind < LIMITS["caution"]["wind"] else 2
    return max(w, d)
def hour_text(ts):
    return ts.strftime("%H:%M")
# ---------- load data ---------
try:
    df, tz = fetch_data(SPOT["lat"], SPOT["lon"])
except Exception as e:
    st.markdown(
        "<div style='background:#4a5a63;color:#fff;padding:24px;border-radius:12px;"
        "font-size:3rem;font-weight:800'>No data</div>",
        unsafe_allow_html=True,
    )
    st.error(
        f"Could not load conditions ({e}). Check your internet connection and reload. "
        "Do not rely on this page until it loads."
    )
    st.stop()
# keep the next 24 hours starting from the current hour (in the spot's timezone)
now = pd.Timestamp.now(tz=tz).tz_localize(None).floor("h")
df = df[df["time"] >= now].head(24).reset_index(drop=True)
if df.empty:
    st.error("No forecast hours available right now. Try again in a few minutes.")
    st.stop()
df["level"] = [rate(a, b) for a, b in zip(df["wave_height"], df["wind_speed_10m"])]
cur = df.iloc[0]
level = int(cur["level"])
bg, fg, _ = COLORS[level]
# ---------- big status ---------
st.markdown(
    f"""
    <div style="background:{bg};color:{fg};padding:24px 28px;border-radius:14px;">
      <div style="font-size:1.05rem;opacity:.9">{SPOT['name']}</div>
      <div style="font-size:4.5rem;font-weight:800;line-height:1.05">{NAMES[level]}</div>
      <div style="font-size:1rem;opacity:.9">Conditions right now</div>
    </div>
    """,
    unsafe_allow_html=True,
)
# ---------- live numbers ---------
c1, c2, c3, c4 = st.columns(4)
def fmt(v, unit, digits=1):
    return "–" if pd.isna(v) else f"{v:.{digits}f} {unit}"
c1.metric("Wave height", fmt(cur["wave_height"], "m"))
c2.metric("Wave period", fmt(cur["wave_period"], "s", 0))
c3.metric("Wind", fmt(cur["wind_speed_10m"], "km/h", 0))
tide_label = "Sea level"
if len(df) > 1 and not pd.isna(cur["sea_level_height_msl"]) and not pd.isna(df.iloc[1]["sea_level_height_msl"]):
    tide_label += " (rising)" if df.iloc[1]["sea_level_height_msl"] > cur["sea_level_height_msl"] else " (falling)"
c4.metric(tide_label, fmt(cur["sea_level_height_msl"], "m"))
# ---------- next good window ---------
levels = df["level"].tolist()
if level == 0:
    bad = next((i for i, l in enumerate(levels) if l != 0), None)
    msg = (
        "Conditions look calm for the next 24 hours."
        if bad is None
        else f"Calm until {hour_text(df.loc[bad, 'time'])}."
    )
else:
    good = next(
        (i for i in range(len(levels) - 1) if levels[i] == 0 and levels[i + 1] == 0), None
    )
    msg = (
        "No calm window in the next 24 hours."
        if good is None
        else f"Next calm window starts at {hour_text(df.loc[good, 'time'])}."
    )
st.subheader(msg)
# ---------- 24-hour timeline ---------
st.markdown("#### Next 24 hours")
cells = ""
labels = ""
for i, row in df.iterrows():
    color = COLORS[int(row["level"])][2]
    tip = (
        f"{hour_text(row['time'])}: {NAMES[int(row['level'])]} "
        f"(waves {fmt(row['wave_height'], 'm')}, wind {fmt(row['wind_speed_10m'], 'km/h', 0)})"
    )
    cells += f"<div title='{tip}' style='flex:1;height:48px;background:{color};border-radius:3px'></div>"
    lab = row["time"].strftime("%H") if i % 4 == 0 else ""
    labels += f"<div style='flex:1;font-size:.75rem'>{lab}</div>"
st.markdown(
    f"""
    <div style="display:flex;gap:2px">{cells}</div>
    <div style="display:flex;gap:2px;margin-top:4px">{labels}</div>
    <p style="font-size:.9rem;margin-top:10px">
      Green = Calm &nbsp; Yellow = Caution &nbsp; Red = Rough &nbsp; Grey = No data.
      Hover over a block for details.
    </p>
    """,
    unsafe_allow_html=True,
)
# ---------- wave chart ---------
st.markdown("#### Wave height (m)")
st.line_chart(df.set_index("time")[["wave_height"]])
# ---------- how the rating works ---------
st.markdown("#### How this rating works")
table = pd.DataFrame(
    {
        "Rating": ["Calm", "Caution", "Rough"],
        "Wave height": [
            f"under {LIMITS['calm']['wave']} m",
            f"{LIMITS['calm']['wave']} to {LIMITS['caution']['wave']} m",
            f"above {LIMITS['caution']['wave']} m",
        ],
        "Wind speed": [
            f"under {LIMITS['calm']['wind']} km/h",
            f"{LIMITS['calm']['wind']} to {LIMITS['caution']['wind']} km/h",
            f"above {LIMITS['caution']['wind']} km/h",
        ],
    }
)
st.table(table.set_index("Rating"))
st.caption(
    f"The worse of wave and wind decides the rating. Thresholds come from: {THRESHOLD_SOURCE}. "
    "They have not been tested with fishers."
)
st.warning(
    "This is guidance from a forecast model, not a safety guarantee. It does not know your boat "
    "or your experience."
)
st.caption("Live data from Open-Meteo. Press R to reload.")