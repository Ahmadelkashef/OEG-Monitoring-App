import streamlit as st
import pandas as pd
import numpy as np
import gspread
from oauth2client.service_account import ServiceAccountCredentials
#from streamlit_gsheets import GSheetsConnection
import ssl
import os
from datetime import timedelta
import json # هنحتاج دي عشان نقرأ بيانات الـ Secrets

from itertools import combinations

import plotly.express as px
import plotly.graph_objects as go


# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="Recharge Behavior Monitoring",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =========================================================
# CUSTOM CSS (Fix for Top Header Clipping)
# =========================================================
st.markdown("""
<style>
/* إخفاء عناصر Streamlit الافتراضية التي قد تغطي العنوان */
header {visibility: hidden;}
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}

.stApp { background-color: #0E1117; color: white; }

/* زيادة الـ padding-top لضمان عدم اختفاء العنوان تحت أي عنصر */
.block-container { 
    max-width: 98%; 
    padding-top: 4rem !important; 
    padding-bottom: 2rem;
}

.main-title { 
    text-align: center; 
    font-size: 36px; 
    font-weight: 800; 
    margin-bottom: 25px;
    color: white;
}

.header-bar {
    display:flex; justify-content:center; align-items:center; gap:50px;
    background-color:#161B22; border:1px solid #30363D; border-radius:14px;
    padding:15px; margin-bottom:20px; font-size:18px; font-weight:700;
}

/* TOP SUMMARY CARDS */
.summary-card {
    background-color: #161B22; border: 1px solid #30363D; border-radius: 12px;
    padding: 15px; text-align: center; transition: 0.3s;
}

.summary-label { color: #8B949E; font-size: 14px; font-weight: 600; margin-bottom: 5px; }
.summary-value { font-size: 26px; font-weight: 800; margin-bottom: 5px; }
.summary-delta { font-size: 14px; font-weight: 700; }
.status-tag { 
    display: inline-block; padding: 3px 10px; border-radius: 4px; 
    font-size: 11px; font-weight: 900; text-transform: uppercase; margin-top: 8px;
    color: white !important;
}
            
/* Tabs Styling */
.stTabs [data-baseweb="tab-list"] { gap: 10px; }
.stTabs [data-baseweb="tab"] {
    height: 45px; background-color: #161B22; border-radius: 5px 5px 0 0;
    padding: 0 20px; color: #8B949E; font-weight: 700;
}
.stTabs [aria-selected="true"] { color: #58A6FF !important; border-bottom: 2px solid #58A6FF !important; }

/*            
.critical-alert { border-color: #991B1B; }
.warning-alert { border-color: #E36209; }
.watch-alert { border-color: #F2CC60; }

.alert-header { font-weight: 800; font-size: 16px; margin-bottom: 5px; }
.alert-detail { font-size: 13px; color: #C9D1D9; }
.growth-tag { font-weight: 900; float: right; font-size: 18px; }
*/
            
/* Alerts Specific Styles */
.alert-summary-container {
    display: flex; justify-content: space-around; background: #161B22; 
    border: 1px solid #30363D; border-radius: 12px; padding: 20px; margin-bottom: 20px;
}
.alert-card {
    background: #1C2128; border: 1px solid #30363D; border-radius: 10px; 
    padding: 15px; margin-bottom: 10px; border-left: 5px solid;
}
.drop-card { border-left-color: #DA3633; }
.up-card { border-left-color: #238636; }
.metric-tag { font-size: 11px; background: #30363D; padding: 2px 8px; border-radius: 10px; color: #8B949E; }

/* DETAILED KPI CARDS */
.kpi-card { background-color:#161B22; border:1px solid #30363D; border-radius:18px; padding:20px; margin-bottom:25px; }
.left-panel { display: flex; flex-direction: column; justify-content: center; align-items: center; height: 100%; padding: 20px; border-right: 1px solid #30363D; }
.metric-title { font-size: 20px; color: #8B949E; font-weight: 600; margin-bottom: 5px; }
.metric-value { font-size: 44px; font-weight: 800; color: white; }

.text-box { background-color:#0D1117; border-radius:12px; padding:15px; min-height:220px; border-left:4px solid #3B82F6; display: flex; flex-direction: column; }
.section-title { text-align:center; font-size:14px; font-weight:700; margin-bottom:12px; color:#C9D1D9; }
.green { color:#238636; font-weight:800; }
.red { color:#DA3633; font-weight:800; }
.trend-text { text-align:center; margin-top: auto; padding-top: 10px; font-size:13px; font-weight:700; color:#F2CC60; }
</style>
""", unsafe_allow_html=True)









# =========================================================
# 2. Global Functions
# =========================================================



# دالة تحديد الحالة (Normal باللون الأخضر أو الأحمر حسب النسبة)
def get_status_details(percentage):
    abs_val = abs(percentage)
    if abs_val <= 1:
        label = "Normal"
        color = "#238636" if percentage >= 0 else "#DA3633"
    elif 1 < abs_val <= 5:
        label = "Watch"
        color = "#F2CC60"
    elif 5 < abs_val <= 10:
        label = "Warning"
        color = "#E36209"
    else:
        label = "Critical"
        color = "#991B1B"
    return label, color

# def get_month_phase(day):
#     if day.day <= 10: return "Early Month"
#     elif day.day <= 20: return "Mid Month"
#     return "Month End"



def get_month_phase(day):
    if   1  <= day.day <= 7: return "Salary Period"
    elif 7  <  day.day <= 15: return "Mid Month"
    elif 15 <  day.day <= 22: return "Late Mid Month"
    return "Month End"


def detect_trend(values):
    vals = [v for v in values if pd.notnull(v)]
    if len(vals) < 3: return "Not enough data"
    if np.std(vals) > 15: return "📊 Random / Volatile"
    avg = np.mean(vals)
    if avg >= 3: return "📈 Gradual Increase"
    if avg <= -3: return "📉 Gradual Decline"
    return "➡ Stable"












# =========================================================
# 2. OVERALL Global Functions FOR ALL MAIN TABS
# =========================================================



#==   1. TAB OVERALL


# =========================================================
# 2. OVERALL TABS
# =========================================================



def render_dynamic_detailed_cards(df, date_col, kpis_config):
    st.write("") # Spacer
    
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df["temp_phase"] = df[date_col].apply(get_month_phase)
    
    target_date_dt = pd.to_datetime(selected_day)
    curr_row = df[df[date_col] == target_date_dt]
    
    if curr_row.empty:
        st.warning(f"⚠️ No data available for the selected date: {selected_day.date()} in this section.")
        return

    for kpi_name, kpi_col in dict(kpis_config).items():
        if kpi_col not in df.columns or kpi_col not in curr_row.columns:
            continue
            
        # 🌟 نجيب القيمة الأصلية الخام من غير أي لعب
        raw_val = curr_row[kpi_col].values[0]
        
        # 🌟 نجهز الرقم التفصيلي بالكامل كـ Integer صريح بالفواصل وبدون (.0) نهائياً
        full_raw_val = f"{int(round(raw_val)):,}"
        
        # اللوجيك الذكي المتكيف حسب الحجم (الكسور تظهر في المليار فقط!)
        if raw_val >= 1_000_000_000:
            # 1️⃣ حالة المليار: بنسيب رقمين عشريين براحتهم عشان الدقة (مثال: 2.93 B)
            formatted_val = f"{round(raw_val / 1_000_000_000, 2):,} B"
            left_panel_html = f"""
                <div class="left-panel">
                    <div class="metric-title">{kpi_name}</div>
                    <div class="metric-value" style="font-size:24px; line-height:1.1;">{formatted_val}</div>
                    <div style="font-size:10px; color:#8B949E; margin-top:4px; font-weight:normal; word-break:break-all;">({full_raw_val})</div>
                </div>
            """
        else:
            # 2️⃣ حالة المليون أو الأقل: يفرش الرقم الأصلي كـ Integer صريح علطول بدون سطر سفلي وبدون كسور
            left_panel_html = f"""
                <div class="left-panel">
                    <div class="metric-title">{kpi_name}</div>
                    <div class="metric-value" style="font-size:22px; line-height:1.2;">{full_raw_val}</div>
                </div>
            """
    
        # =========================================================
        # زون الأسعار
        # =========================================================
        price_update_date = pd.to_datetime("2026-05-05")

        def get_row_phase_tag(target_dt):
            target_dt = pd.to_datetime(target_dt)
            if target_dt < price_update_date:
                return '<span style="color: #238636; font-size: 11px; font-weight: 800;">(Pre)</span>'
            elif target_dt == price_update_date:
                return '<span style="color: #F2CC60; font-size: 11px; font-weight: 800;">(Event)</span>'
            else:
                return '<span style="color: #DA3633; font-size: 11px; font-weight: 800;">(Post)</span>'
    
        # 1. صندوق الحركة اليومية (Daily Movement)
        daily_text, daily_changes = "", []
        for d in range(1, 7):
            target_prev_date = selected_day - timedelta(days=d)
            prev = df[df[date_col] == pd.to_datetime(target_prev_date)]
            if not prev.empty and kpi_col in prev.columns:
                v = prev[kpi_col].values[0]
                if v != 0:
                    growth = round(((raw_val - v) / v) * 100, 1)
                    daily_changes.append(growth)
                    color = "green" if growth >= 0 else "red"
                    
                    date_str = target_prev_date.strftime('%m/%d')
                    phase_tag = get_row_phase_tag(target_prev_date)
                    daily_text += f'<div class="movement-line">D-{d} ({date_str}) {phase_tag} : <span class="{color}">{growth}%</span></div>'
    
        # 2. صندوق نفس يوم الأسبوع (Same Weekday)
        wd_text, wd_changes = "", []
        same_wd = df[(df[date_col].dt.day_name() == weekday_name) & (df[date_col] < target_date_dt)].sort_values(date_col, ascending=False).head(4)
        for i, (_, row) in enumerate(same_wd.iterrows(), 1):
            if kpi_col in row and row[kpi_col] != 0:
                v_val = row[kpi_col]
                growth = round(((raw_val - v_val) / v_val) * 100, 1)
                wd_changes.append(growth)
                color = "green" if growth >= 0 else "red"
                
                target_wd_date = pd.to_datetime(row[date_col])
                date_str = target_wd_date.strftime('%m/%d')
                phase_tag = get_row_phase_tag(target_wd_date)
                wd_text += f'<div class="movement-line">{weekday_name[:3]}-{i} ({date_str}) {phase_tag} : <span class="{color}">{growth}%</span></div>'

        # 3. صندوق يوم الأسبوع + المرحلة (Weekday + Phase)
        ph_text, ph_changes = "", []
        ph_df = df[(df[date_col].dt.day_name() == weekday_name) & (df["temp_phase"] == month_phase) & (df[date_col] < target_date_dt)].sort_values(date_col, ascending=False).head(4)
        for i, (_, row) in enumerate(ph_df.iterrows(), 1):
            if kpi_col in row and row[kpi_col] != 0:
                v_val = row[kpi_col]
                growth = round(((raw_val - v_val) / v_val) * 100, 1)
                ph_changes.append(growth)
                color = "green" if growth >= 0 else "red"
                
                target_ph_date = pd.to_datetime(row[date_col])
                date_str = target_ph_date.strftime('%m/%d')
                phase_tag = get_row_phase_tag(target_ph_date)
                ph_text += f'<div class="movement-line">{month_phase[:3]}. {weekday_name[:3]}-{i} ({date_str}) {phase_tag} : <span class="{color}">{growth}%</span></div>'

        # رسم الـ UI الشيك
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        m_left, m_right = st.columns([1, 3])
        with m_left:
            st.markdown(left_panel_html, unsafe_allow_html=True)
        with m_right:
            s1, s2, s3 = st.columns(3)
            with s1: st.markdown(f'<div class="text-box"><div class="section-title">Daily Movement</div>{daily_text}<div class="trend-text">{detect_trend(daily_changes)}</div></div>', unsafe_allow_html=True)
            with s2: st.markdown(f'<div class="text-box"><div class="section-title">Same Weekday</div>{wd_text}<div class="trend-text">{detect_trend(wd_changes)}</div></div>', unsafe_allow_html=True)
            with s3: st.markdown(f'<div class="text-box"><div class="section-title">Weekday + Phase</div>{ph_text}<div class="trend-text">{detect_trend(ph_changes)}</div></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)


















#==   2. TAB ALERTS


# =========================================================
# 2. ALERTS TABS
# =========================================================






def get_dynamic_alerts(df_raw, date_col, dimensions, metrics_map, thresholds=[3, 5, 10, 20]):
    """
    Dynamic Alerts Engine with Automatic Combinations & Flexible Thresholds.
    thresholds list format: [min_visible, watch_limit, warning_limit, critical_limit]
    Default: [3, 5, 10, 20]
    """
    # حساب تاريخ امبارح بناءً على التاريخ المستهدف
    target_date = pd.to_datetime(selected_day)
    prev_date = target_date - timedelta(days=1)
    
    df_raw = df_raw.copy()
    df_raw[date_col] = pd.to_datetime(df_raw[date_col])
    
    curr = df_raw[df_raw[date_col] == target_date]
    prev = df_raw[df_raw[date_col] == prev_date]
    
    if curr.empty or prev.empty: 
        return pd.DataFrame()

    # 🧠 الـ Combinatorics الذكي: توليد كل الاحتمالات الممكنة رياضياً أوتوماتيكياً
    all_combinations = []
    for r in range(1, len(dimensions) + 1):
        for combo in combinations(dimensions, r):
            all_combinations.append(list(combo))
            
    # استخراج أسماء أعمدة المقاييس من الخريطة (الـ Keys والـ Values)
    metric_cols = list(metrics_map.keys())
    results = []

    # الـ Loop الكبيرة بتلف على كل الاحتمالات الناتجة
    for cols in all_combinations:
        # التأكد إن العواميد دي موجودة فعلاً في الجداول الممررة
        if not all(c in curr.columns and c in prev.columns for c in cols):
            continue
            
        curr_g = curr.groupby(cols)[metric_cols].sum().reset_index()
        prev_g = prev.groupby(cols)[metric_cols].sum().reset_index()
        
        merged = curr_g.merge(prev_g, on=cols, suffixes=('_c', '_p'))
        
        # تفكيك السلم المرن الممرر
        min_v, watch_v, warn_v, crit_v = thresholds
        
        for _, row in merged.iterrows():
            # دمج اسم الشريحة شياكة
            segment_name = " | ".join([str(row[c]) for c in cols])
            
            for col_key, display_name in metrics_map.items():
                p_val = row[f"{col_key}_p"]
                c_val = row[f"{col_key}_c"]
                
                if p_val > 0:
                    growth = ((c_val - p_val) / p_val) * 100
                    abs_g = abs(growth)
                    
                    if abs_g >= min_v: # الحد الأدنى للظهور
                        # تطبيق السلم الديناميكي المرن
                        if abs_g < watch_v: 
                            level = "Normal"
                        elif watch_v <= abs_g < warn_v: 
                            level = "Watch"
                        elif warn_v <= abs_g < crit_v: 
                            level = "Warning"
                        else: 
                            level = "Critical"
                        
                        results.append({
                            "segment": segment_name,
                            "metric": display_name, 
                            "growth": round(growth, 1),
                            # التخلص من الكسور العشرية للأرقام الصحيحة النظيفة
                            "current_val": int(round(c_val)),
                            "previous_val": int(round(p_val)),
                            "level": level, 
                            "direction": "Drop" if growth < 0 else "Up"
                        })
                        
    #return pd.DataFrame(results)
    # 🎯 التعديل السحري هنا: تحويل لـ DataFrame والترتيب المطلق
    df_final = pd.DataFrame(results)
    
    if not df_final.empty:
        # خلق عمود وهمي فيه القيمة المطلقة للـ Growth عشان نرتب بيه
        df_final["abs_growth"] = df_final["growth"].abs()
        
        # ترتيب تنازلي من الأكبر للأصغر (عشان الـ Critical والـ Warning يطيروا فوق)
        df_final = df_final.sort_values(by="abs_growth", ascending=False)
        
        # تنظيف العمود المؤقت وعمل ريست للأندكس
        df_final = df_final.drop(columns=["abs_growth"]).reset_index(drop=True)
        
    return df_final
    









def render_alerts_center_ui(alerts_df):
    """
    Renders a unified, highly polished executive Alerts Center Dashboard.
    Matches exactly the user's original layout and dark theme specifications.
    """
    if alerts_df.empty:
        st.info("ℹ️ No data or deviations detected for the selected date.")
        return
        
    # 1. فصل الداتا للإحصائيات الإجمالية
    drops_df = alerts_df[alerts_df["direction"] == "Drop"]
    ups_df = alerts_df[alerts_df["direction"] == "Up"]
    
    total_deviations = len(alerts_df)
    total_drops = len(drops_df)
    total_ups = len(ups_df)
    
    # 2. الصندوق العلوي الكبير (Total Deviations Banner)
    st.markdown(f"""
        <div style="background-color: #1F190D; border-left: 5px solid #F2CC60; padding: 15px; border-radius: 6px; margin-bottom: 20px;">
            <span style="color: #F2CC60; font-size: 18px; font-weight: bold; margin-right: 8px;">⚠️</span>
            <span style="color: #E6EDF2; font-size: 15px; font-weight: 500;">System detected {total_deviations} deviations for the selected date.</span>
        </div>
    """, unsafe_allow_html=True)
    
    # 3. الـ Split الكبيرة (صندوق الـ Drops وصندوق الـ Ups جنب بعض)
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.markdown(f"""
            <div style="background-color: #161B22; border: 1px solid #30363D; border-radius: 8px; padding: 25px; text-align: center; height: 140px;">
                <div style="color: #DA3633; font-size: 36px; font-weight: 800; line-height: 1.2;">{total_drops}</div>
                <div style="color: #8B949E; font-size: 12px; font-weight: bold; letter-spacing: 0.5px; margin-top: 5px;">DROPS DETECTED</div>
            </div>
        """, unsafe_allow_html=True)
        
    with col_right:
        st.markdown(f"""
            <div style="background-color: #161B22; border: 1px solid #30363D; border-radius: 8px; padding: 25px; text-align: center; height: 140px;">
                <div style="color: #238636; font-size: 36px; font-weight: 800; line-height: 1.2;">{total_ups}</div>
                <div style="color: #8B949E; font-size: 12px; font-weight: bold; letter-spacing: 0.5px; margin-top: 5px;">UPS DETECTED</div>
            </div>
        """, unsafe_allow_html=True)
        
    st.write("") # Spacer
    
    # 4. الـ Main Tabs (DROPS ANALYSIS vs UPS ANALYSIS)
    main_tabs = st.tabs(["📉 DROPS ANALYSIS", "📈 UPS ANALYSIS"])
    levels_order = ["Critical", "Warning", "Watch", "Normal"]
    
    # --- التبويب الأول: Drops ---
    with main_tabs[0]:
        if drops_df.empty:
            st.info("No drop alerts found.")
        else:
            # الـ Sub Tabs الفرعية للفلات السلم جوه الـ Drops
            sub_tabs_drop = st.tabs([f"{l} ({len(drops_df[drops_df['level']==l])})" for l in levels_order])
            for idx, lvl in enumerate(levels_order):
                with sub_tabs_drop[idx]:
                    subset = drops_df[drops_df["level"] == lvl]
                    if subset.empty:
                        st.info(f"No {lvl} drop alerts found.")
                    else:
                        for _, r in subset.iterrows():
                            st.markdown(f"""
                            <div class="alert-card drop-card" style="background-color: #161B22; border: 1px solid #30363D; border-left: 4px solid #DA3633; padding: 15px; border-radius: 6px; margin-bottom: 12px; position: relative;">
                                <span style="float: right; color: #DA3633; font-weight: 800; font-size: 16px;">
                                    ▼ {abs(r['growth'])}%
                                </span>
                                <div style="font-weight: 700; color: #F0F6FC; font-size: 15px; margin-bottom: 6px; padding-right: 80px;">{r['segment']}</div>
                                <div style="font-size: 13px; color: #8B949E; margin-bottom: 10px;">
                                    Current: <b style="color: #C9D1D9;">{r['current_val']:,}</b> | Previous: <b style="color: #C9D1D9;">{r['previous_val']:,}</b>
                                </div>
                                <span class="metric-tag" style="background-color: #21262D; color: #8B949E; font-size: 11px; padding: 4px 8px; border-radius: 4px; font-weight: 600;">Metric: {r['metric']}</span>
                            </div>
                            """, unsafe_allow_html=True)

    # --- التبويب الثاني: Ups ---
    with main_tabs[1]:
        if ups_df.empty:
            st.info("No up alerts found.")
        else:
            # الـ Sub Tabs الفرعية للفلات السلم جوه الـ Ups
            sub_tabs_up = st.tabs([f"{l} ({len(ups_df[ups_df['level']==l])})" for l in levels_order])
            for idx, lvl in enumerate(levels_order):
                with sub_tabs_up[idx]:
                    subset = ups_df[ups_df["level"] == lvl]
                    if subset.empty:
                        st.info(f"No {lvl} up alerts found.")
                    else:
                        for _, r in subset.iterrows():
                            st.markdown(f"""
                            <div class="alert-card up-card" style="background-color: #161B22; border: 1px solid #30363D; border-left: 4px solid #238636; padding: 15px; border-radius: 6px; margin-bottom: 12px; position: relative;">
                                <span style="float: right; color: #238636; font-weight: 800; font-size: 16px;">
                                    ▲ {abs(r['growth'])}%
                                </span>
                                <div style="font-weight: 700; color: #F0F6FC; font-size: 15px; margin-bottom: 6px; padding-right: 80px;">{r['segment']}</div>
                                <div style="font-size: 13px; color: #8B949E; margin-bottom: 10px;">
                                    Current: <b style="color: #C9D1D9;">{r['current_val']:,}</b> | Previous: <b style="color: #C9D1D9;">{r['previous_val']:,}</b>
                                </div>
                                <span class="metric-tag" style="background-color: #21262D; color: #8B949E; font-size: 11px; padding: 4px 8px; border-radius: 4px; font-weight: 600;">Metric: {r['metric']}</span>
                            </div>
                            """, unsafe_allow_html=True)

















#==   2. TAB contribution_alerts


# =========================================================
# 2. contribution_alerts TABS
# =========================================================







def get_dynamic_contribution_alerts(df_raw, df_global, date_col, dimensions, metrics_map, global_metrics_map, thresholds=[5, 15, 30], comp_mode="vs Yesterday (D-1)", selected_day=None):
    """
    Dynamic Contribution Engine (Root Cause Analysis V5).
    Guarantees perfect subscriber uniqueness by explicitly mapping df_raw columns to df_global columns.
    """
    if selected_day is None:
        return pd.DataFrame()
        
    target_date = pd.to_datetime(selected_day)
    
    def get_phase(dt):
        day = dt.day
        if 1 <= day <= 7: return "Salary Period"
        elif 8 <= day <= 15: return "Mid-Month"
        elif 16 <= day <= 22: return "Late-Mid"
        else: return "End-Month"

    if comp_mode == "vs Yesterday (D-1)":
        prev_date = target_date - timedelta(days=1)
    elif comp_mode == "vs Same Day Last Week (D-7)":
        prev_date = target_date - timedelta(days=7)
    else:
        target_weekday = target_date.weekday()
        target_phase = get_phase(target_date)
        found = False
        weeks_back = 1
        while weeks_back <= 6:
            check_date = target_date - timedelta(days=7 * weeks_back)
            if check_date.weekday() == target_weekday and get_phase(check_date) == target_phase:
                prev_date = check_date
                found = True
                break
            weeks_back += 1
        if not found:
            prev_date = target_date - timedelta(days=28)

    df_raw = df_raw.copy()
    df_raw[date_col] = pd.to_datetime(df_raw[date_col])
    curr = df_raw[df_raw[date_col] == target_date]
    prev = df_raw[df_raw[date_col] == prev_date]
    
    df_global = df_global.copy()
    df_global[date_col] = pd.to_datetime(df_global[date_col])
    global_curr = df_global[df_global[date_col] == target_date]
    global_prev = df_global[df_global[date_col] == prev_date]
    
    if curr.empty or prev.empty or global_curr.empty or global_prev.empty: 
        return pd.DataFrame()

    # 🧠 هنا السحر: حساب الـ Total Network Move الحقيقي بناءً على الماب الصريحة للـ Global
    global_diffs = {}
    for col_raw, col_global in global_metrics_map.items():
        display_name = metrics_map[col_raw]
        if col_global in global_curr.columns and col_global in global_prev.columns:
            c_tot = global_curr[col_global].values[0]
            p_tot = global_prev[col_global].values[0]
            global_diffs[display_name] = c_tot - p_tot
        else:
            global_diffs[display_name] = 0

    all_combinations = []
    for r in range(1, len(dimensions) + 1):
        for combo in combinations(dimensions, r):
            all_combinations.append(list(combo))
            
    metric_cols = list(metrics_map.keys())
    results = []

    for cols in all_combinations:
        if not all(c in curr.columns and c in prev.columns for c in cols):
            continue
            
        curr_g = curr.groupby(cols)[metric_cols].sum().reset_index()
        prev_g = prev.groupby(cols)[metric_cols].sum().reset_index()
        
        merged = curr_g.merge(prev_g, on=cols, suffixes=('_c', '_p'))
        
        min_v, major_v, primary_v = thresholds
        
        for _, row in merged.iterrows():
            segment_name = " | ".join([str(row[c]) for c in cols])
            
            for col_key, display_name in metrics_map.items():
                p_val = row[f"{col_key}_p"]
                c_val = row[f"{col_key}_c"]
                
                seg_diff = c_val - p_val
                tot_diff = global_diffs[display_name]
                
                if tot_diff == 0: 
                    continue
                
                contribution_pct = round((seg_diff / abs(tot_diff)) * 100, 1)
                abs_contrib = abs(contribution_pct)
                
                if abs_contrib >= min_v:
                    if abs_contrib < major_v:
                        level = "Minor Contributor"
                    elif major_v <= abs_contrib < primary_v:
                        level = "Major Contributor"
                    else:
                        level = "Primary Driver"
                        
                    segment_direction = "Increase" if seg_diff > 0 else "Decline"
                    
                    results.append({
                        "segment": segment_name,
                        "metric": display_name, 
                        "contribution": abs_contrib,
                        "seg_diff": round(seg_diff, 1),
                        "tot_diff": round(tot_diff, 1),
                        "current_val": round(c_val, 1),
                        "previous_val": round(p_val, 1),
                        "level": level, 
                        "network_direction": segment_direction,
                        "compared_to_date": prev_date.strftime('%Y-%m-%d')
                    })
                        
    #return pd.DataFrame(results)
    # 🔥 الحتة السحرية الجديدة للترتيب التنازلي المظبوط 🔥
    df_final = pd.DataFrame(results)
    if not df_final.empty:
        # بنرتب الداتا تنازلياً من الكبير للصغير بناءً على رقم الـ contribution نفسه
        df_final = df_final.sort_values(by="contribution", ascending=False).reset_index(drop=True)
        
    return df_final










def render_contribution_center_ui(contribution_df, comp_mode="vs Yesterday (D-1)", selected_day=None):
    if contribution_df.empty:
        st.info("ℹ️ No continuous business drivers or deviations detected for the filters selected.")
        return
        
    baseline_date = contribution_df["compared_to_date"].iloc[0]
    target_date_str = selected_day if isinstance(selected_day, str) else selected_day.strftime('%Y-%m-%d')
    
    st.markdown(f"""
        <div style="background-color: #1F190D; border-left: 5px solid #F2CC60; padding: 12px 15px; border-radius: 6px; margin-bottom: 20px;">
            <span style="color: #F2CC60; font-size: 16px; font-weight: bold; margin-right: 6px;">💡</span>
            <span style="color: #E6EDF2; font-size: 14px; font-weight: 500;">
                Currently matching data of <b>{target_date_str}</b> against historical baseline date: <b>{baseline_date}</b> ({comp_mode})
            </span>
        </div>
    """, unsafe_allow_html=True)
    
    decline_df = contribution_df[contribution_df["network_direction"] == "Decline"]
    increase_df = contribution_df[contribution_df["network_direction"] == "Increase"]
    
    total_declines = len(decline_df)
    total_increases = len(increase_df)
    
    col_left, col_right = st.columns(2)
    with col_left:
        st.markdown(f"""
            <div style="background-color: #161B22; border: 1px solid #30363D; border-radius: 8px; padding: 25px; text-align: center; height: 130px;">
                <div style="color: #DA3633; font-size: 36px; font-weight: 800; line-height: 1.2;">{total_declines}</div>
                <div style="color: #8B949E; font-size: 11px; font-weight: bold; letter-spacing: 0.5px; margin-top: 5px;">DRIVERS OF DECLINE (Filtered KPIs)</div>
            </div>
        """, unsafe_allow_html=True)
        
    with col_right:
        st.markdown(f"""
            <div style="background-color: #161B22; border: 1px solid #30363D; border-radius: 8px; padding: 25px; text-align: center; height: 130px;">
                <div style="color: #238636; font-size: 36px; font-weight: 800; line-height: 1.2;">{total_increases}</div>
                <div style="color: #8B949E; font-size: 11px; font-weight: bold; letter-spacing: 0.5px; margin-top: 5px;">DRIVERS OF INCREASE (Filtered KPIs)</div>
            </div>
        """, unsafe_allow_html=True)
        
    st.write("") 
    
    main_tabs = st.tabs(["📉 DRIVERS OF DECLINE ANALYSIS", "📈 DRIVERS OF INCREASE ANALYSIS"])
    levels_order = ["Primary Driver", "Major Contributor", "Minor Contributor"]
    
    with main_tabs[0]:
        if decline_df.empty:
            st.info("No drivers of decline found for this view.")
        else:
            sub_tabs = st.tabs([f"🎯 {l} ({len(decline_df[decline_df['level']==l])})" for l in levels_order])
            for idx, lvl in enumerate(levels_order):
                with sub_tabs[idx]:
                    subset = decline_df[decline_df["level"] == lvl]
                    if subset.empty:
                        st.info(f"No {lvl} decline factors found.")
                    else:
                        for _, r in subset.iterrows():
                            color = "#DA3633" if lvl == "Primary Driver" else ("#E36209" if lvl == "Major Contributor" else "#F2CC60")
                            st.markdown(f"""
                            <div class="alert-card" style="background-color: #161B22; border: 1px solid #30363D; border-left: 5px solid {color}; padding: 15px; border-radius: 6px; margin-bottom: 12px;">
                                <span style="float: right; color: {color}; font-weight: 800; font-size: 16px;">
                                    Share: {r['contribution']}%
                                </span>
                                <div style="font-weight: 700; color: #F0F6FC; font-size: 15px; margin-bottom: 6px;">{r['segment']}</div>
                                <div style="font-size: 13px; color: #8B949E; margin-bottom: 10px;">
                                    Segment Move: <b style="color: #DA3633;">▼ {abs(r['seg_diff']):,}</b> &nbsp;|&nbsp; Total Network Move: <b style="color: #C9D1D9;">{r['tot_diff']:,}</b>
                                </div>
                                <span class="metric-tag" style="background-color: #21262D; color: #8B949E; font-size: 11px; padding: 4px 8px; border-radius: 4px; font-weight: 600; margin-right: 6px;">Metric: {r['metric']}</span>
                                <span style="color: {color}; font-size: 11px; font-weight: bold;">{lvl}</span>
                            </div>
                            """, unsafe_allow_html=True)

    with main_tabs[1]:
        if increase_df.empty:
            st.info("No drivers of increase found for this view.")
        else:
            sub_tabs = st.tabs([f"🎯 {l} ({len(increase_df[increase_df['level']==l])})" for l in levels_order])
            for idx, lvl in enumerate(levels_order):
                with sub_tabs[idx]:
                    subset = increase_df[increase_df["level"] == lvl]
                    if subset.empty:
                        st.info(f"No {lvl} increase factors found.")
                    else:
                        for _, r in subset.iterrows():
                            color = "#238636" if lvl == "Primary Driver" else ("#E36209" if lvl == "Major Contributor" else "#F2CC60")
                            st.markdown(f"""
                            <div class="alert-card" style="background-color: #161B22; border: 1px solid #30363D; border-left: 5px solid {color}; padding: 15px; border-radius: 6px; margin-bottom: 12px;">
                                <span style="float: right; color: {color}; font-weight: 800; font-size: 16px;">
                                    Share: {r['contribution']}%
                                </span>
                                <div style="font-weight: 700; color: #F0F6FC; font-size: 15px; margin-bottom: 6px;">{r['segment']}</div>
                                <div style="font-size: 13px; color: #8B949E; margin-bottom: 10px;">
                                    Segment Move: <b style="color: #238636;">▲ {abs(r['seg_diff']):,}</b> &nbsp;|&nbsp; Total Network Move: <b style="color: #C9D1D9;">{r['tot_diff']:,}</b>
                                </div>
                                <span class="metric-tag" style="background-color: #21262D; color: #8B949E; font-size: 11px; padding: 4px 8px; border-radius: 4px; font-weight: 600; margin-right: 6px;">Metric: {r['metric']}</span>
                                <span style="color: {color}; font-size: 11px; font-weight: bold;">{lvl}</span>
                            </div>
                            """, unsafe_allow_html=True)












def render_contribution_section(df_raw, df_global, date_col, dimensions, metrics_map, global_metrics_map, thresholds=[5, 15, 30], selected_day=None, prefix="rch"):
    """
    Unified Contribution Center Section.
    Added 'prefix' to dynamically generate unique keys per section.
    """
    col_filter_left, col_filter_right = st.columns(2)

    with col_filter_left:
        # 🧠 الـ key هنا بقى ديناميكي ومتغير حسب الـ prefix
        selected_comp_mode = st.selectbox(
            "📅 Select Comparison Basis (Seasonality):", 
            ["vs Yesterday (D-1)", "vs Same Day Last Week (D-7)", "vs Same Weekday & Month Phase (Smart Match)"],
            key=f"{prefix}_contrib_seasonality_internal_key"
        )

    with col_filter_right:
        kpi_dropdown_options = ["All KPIs"] + list(metrics_map.values())
        # 🧠 والـ key ده كمان بقى ديناميكي ومستحيل يتكرر
        selected_kpi_filter = st.selectbox(
            "🔍 Filter Alerts by KPI:", 
            kpi_dropdown_options,
            key=f"{prefix}_contrib_kpi_filter_internal_key"
        )

    # باقي كود الدالة المايسترو بيكمل تحت زي ما هو بالظبط...


    df_results = get_dynamic_contribution_alerts(
        df_raw=df_raw,         
        df_global=df_global,    
        date_col=date_col,             
        dimensions=dimensions, 
        metrics_map=metrics_map,
        global_metrics_map=global_metrics_map,
        thresholds=thresholds,         
        comp_mode=selected_comp_mode,   
        selected_day=selected_day       
    )

    if not df_results.empty and selected_kpi_filter != "All KPIs":
        df_results = df_results[df_results["metric"] == selected_kpi_filter]

    render_contribution_center_ui(
        contribution_df=df_results, 
        comp_mode=selected_comp_mode,
        selected_day=selected_day
    )





















#==================================
# IBRO
#==================================



def process_behavioral_data_dynamic(df_day_filtered, chosen_filters):
    """
    الدالة المحركة (Engine): تقوم بفلترة البيانات ديناميكياً بناءً على قاموس الفلاتر الممرر،
    ثم تحسب المؤشرات الرئيسية (KPIs) وأكثر محافظة تعرضت لنزيف الخطوط.
    """
    # حماية: لو الداتا الأساسية فاضية من الأول
    if df_day_filtered.empty:
        return 0, 0, 0, pd.DataFrame()

    df_res = df_day_filtered.copy()
    
    # 1. تطبيق الفلاتر الديناميكية الممررة بالـ Loop
    for col, val in chosen_filters.items():
        if val != "All" and col in df_res.columns:
            df_res = df_res[df_res[col] == val]
        
    # لو الداتا طلعت فاضية بعد الفلاتر
    if df_res.empty:
        return 0, 0, 0, pd.DataFrame()
        
    # 2. حساب المؤشرات الرئيسية (KPIs)
    inflow_subs = df_res[df_res['movement_type'] == 'INFLOW']['unq_subs'].sum()
    outflow_subs = df_res[df_res['movement_type'] == 'OUTFLOW']['unq_subs'].sum()
    net_change = inflow_subs - outflow_subs
    
    return int(inflow_subs), int(outflow_subs), int(net_change), df_res






















def f_tab_dynamic_dashboard(
    tab_title="🚀 Behavioral Data Center",
    df_source=None,
    dimensions=None,
    prefix="ibro",
    waterfall_dim="market_zone",
    mirror_dim="governorate",
    inflow_profile_col="rch_behaviour_current_period",
    outflow_profile_col="rch_behaviour_previous_period"
):
    """
    دالة الـ UI الموحدة والديناميكية بالكامل:
    - dimensions: لستة بالعواميد اللي عايزها تظهر كفلاتر (مثلاً: ['mode', 'tariff_sub_category_2'])
    - prefix: نص مميز لكل تابة لضمان عدم تداخل الـ widgets في Streamlit
    - waterfall_dim, mirror_dim, inflow_profile_col, outflow_profile_col: 
      أسامي العواميد للرسومات، لو ممررين قيمتها بـ None التشارْت المقابل بيختفي تماماً.
    """
    st.markdown(f'<div class="section-header">{tab_title}</div>', unsafe_allow_html=True)
    
    # 1. الحماية والتأكد أن الداتا فريم موجود ومش فاضي
    if df_source is None or df_source.empty:
        st.error("❌ Data source is empty or not loaded properly.")
        return

    # تنسيق التواريخ لضمان دقة الفلترة
    df_clean = df_source.copy()
    df_clean['reported_date_str'] = pd.to_datetime(df_clean['reported_date']).dt.strftime('%Y-%m-%d')
    target_date_str = pd.to_datetime(selected_day).strftime('%Y-%m-%d')
    
    # تصفية البيانات المبدئية لليوم المختار فقط
    df_day_base = df_clean[df_clean['reported_date_str'] == target_date_str]
    
    if df_day_base.empty:
        st.warning(f"⚠️ No data available for the selected date: **{target_date_str}**.")
        return

    # 2. بناء الفلاتر التكتيكية ديناميكياً بناءً على الـ Dimensions الممررة
    if dimensions:
        st.markdown("#### 🎛️ Dashboard Controls")
        filters_cols = st.columns(len(dimensions))
        chosen_filters = {}
        
        for idx, col in enumerate(filters_cols):
            dim_name = dimensions[idx]
            if dim_name in df_day_base.columns:
                with col:
                    # لو البُعد هو الـ mode مفيش حاجة اسمها الكل "All" لازم يختار ويندوز زمني
                    if dim_name.lower() == 'mode':
                        options = sorted(list(df_day_base[dim_name].unique()))
                        label_name = "🔄 Time Window (Mode):"
                    else:
                        options = ["All"] + sorted(list(df_day_base[dim_name].unique()))
                        label_name = f"👥 Filter by {dim_name.replace('_', ' ').title()}:"
                    
                    # الـ Selectbox بـ Key محمي ديناميكياً بالـ prefix والـ column name
                    chosen_filters[dim_name] = st.selectbox(
                        label_name, 
                        options=options, 
                        index=0, 
                        key=f"{prefix}_{dim_name}_widget"
                    )
        st.write("---")
    else:
        chosen_filters = {}

    # 3. استدعاء المحرك الديناميكي للحسابات
    inflow, outflow, net, df_final_chart = process_behavioral_data_dynamic(df_day_base, chosen_filters)
    
    # 4. لوجيك حساب المحافظة الأكثر تأثراً بالنزيف (Worst Gov)
    if not df_final_chart.empty and 'governorate' in df_final_chart.columns:
        df_gov_calc = df_final_chart.copy()
        df_gov_calc['signed_subs'] = df_gov_calc.apply(
            lambda r: r['unq_subs'] if r['movement_type'] == 'INFLOW' else -r['unq_subs'], axis=1
        )
        df_gov_net_sum = df_gov_calc.groupby('governorate')['signed_subs'].sum().reset_index()
        df_only_losers = df_gov_net_sum[df_gov_net_sum['signed_subs'] < 0]
        
        if not df_only_losers.empty:
            worst_row = df_only_losers.sort_values(by='signed_subs', ascending=True).iloc[0]
            has_leakage = True
        else:
            has_leakage = False
    else:
        has_leakage = False

    # 5. عرض كروت الـ KPIs بتصميم ناصع وقوي
    st.markdown(f"##### 📈 KPIs Overview for **{target_date_str}**")
    
    st.markdown("""
        <style>
            [data-testid="stMetricLabel"] { font-size: 14px !important; font-weight: bold !important; color: #ffffff !important; }
            [data-testid="stMetricValue"] { font-size: 24px !important; font-weight: 900 !important; color: #00ffcc !important; }
            [data-testid="stMetricDelta"] { font-size: 18px !important; font-weight: bold !important; }
        </style>
    """, unsafe_allow_html=True)
    
    kpi_1, kpi_2, kpi_3, kpi_4 = st.columns(4)
    with kpi_1:
        st.metric(label="🟢 Total Inflow Subs", value=f"{inflow:,}")
    with kpi_2:
        st.metric(label="🔴 Total Outflow Subs", value=f"{outflow:,}")
    with kpi_3:
        delta_color = "normal" if net >= 0 else "inverse"
        st.metric(label="⚖️ Net Growth / Leakage", value=f"{net:,}", delta=f"{net:,} Subs", delta_color=delta_color)
    with kpi_4:
        if has_leakage:
            st.metric(
                label="🚨 Most Affected Gov (Highest Leakage)", 
                value=f"📍 {worst_row['governorate']}", 
                delta=f"{worst_row['signed_subs']:,} Subs",
                delta_color="normal"
            )
        else:
            st.metric(label="🚨 Most Affected Gov (Highest Leakage)", value="No Net Leakage")

    st.write("---")

    if df_final_chart.empty:
        st.info("💡 No active data found matching the selected combination of filters.")
        return

    # ==================== [الرسمة رقم 1: الشلال - Waterfall Chart] ====================
    if waterfall_dim and waterfall_dim in df_final_chart.columns:
        st.markdown(f"##### 🌊 Subscriber Net Flow Breakdown ({waterfall_dim.replace('_', ' ').title()} Waterfall Analysis)")
        df_wfl = df_final_chart.copy()
        df_wfl['subs_signed'] = df_wfl.apply(
            lambda row: row['unq_subs'] if row['movement_type'] == 'INFLOW' else -row['unq_subs'], axis=1
        )
        df_wfl_agg = df_wfl.groupby(waterfall_dim)['subs_signed'].sum().reset_index()
        
        x_data = ["Base (0)"]
        y_data = [0]
        measure_data = ["relative"]
        for _, row in df_wfl_agg.iterrows():
            x_data.append(row[waterfall_dim])
            y_data.append(row['subs_signed'])
            measure_data.append("relative")
        
        x_data.append("📊 Total Net Result")
        y_data.append(net)
        measure_data.append("total")
        
        fig_waterfall = go.Figure(go.Waterfall(
            name="Net Flow", orientation="v", measure=measure_data, x=x_data, textposition="outside",
            text=[f"{val:+,}" if m == "relative" and val != 0 else f"{val:,}" for val, m in zip(y_data, measure_data)],
            y=y_data,
            increasing=dict(marker=dict(color="#2ecc71")),
            decreasing=dict(marker=dict(color="#e74c3c")),
            totals=dict(marker=dict(color="#3498db")),
        ))
        fig_waterfall.update_layout(
            waterfallgap=0.3, margin=dict(l=20, r=20, t=20, b=20), height=380,
            template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color="white", size=12)
        )
        st.plotly_chart(fig_waterfall, use_container_width=True)
        st.write("---")

    # ==================== [الرسمة رقم 2: المحافظات مـرآة - Mirror Top 5] ====================
    if mirror_dim and mirror_dim in df_final_chart.columns:
        st.markdown(f"##### 🎯 Net Flow Focus: Top 5 Gainers vs Top 5 Losers ({mirror_dim.replace('_', ' ').title()} Level)")
        col_net1, col_net2 = st.columns(2)
        
        df_mir = df_final_chart.copy()
        df_mir['signed_subs'] = df_mir.apply(
            lambda r: r['unq_subs'] if r['movement_type'] == 'INFLOW' else -r['unq_subs'], axis=1
        )
        df_mir_summary = df_mir.groupby(mirror_dim)['signed_subs'].sum().reset_index()
        
        with col_net1:
            st.markdown("<p style='color: #2ecc71; font-weight: bold; font-size:14px;'>📈 Top 5 Net Gainers </p>", unsafe_allow_html=True)
            df_gainers = df_mir_summary[df_mir_summary['signed_subs'] > 0].sort_values(by='signed_subs', ascending=True).tail(5)
            
            if not df_gainers.empty:
                fig_gainers = px.bar(df_gainers, x='signed_subs', y=mirror_dim, orientation='h', text_auto='+,', template='plotly_dark')
                fig_gainers.update_traces(marker_color='#2ecc71', textposition='outside', textfont=dict(color="white", size=11))
                fig_gainers.update_layout(
                    margin=dict(l=10, r=10, t=10, b=10), height=250, xaxis_title="Net Subs Gained", yaxis_title=None,
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="white")
                )
                st.plotly_chart(fig_gainers, use_container_width=True)
            else:
                st.caption("No positive net gainers for this selection.")
                
        with col_net2:
            st.markdown("<p style='color: #e74c3c; font-weight: bold; font-size:14px; text-align: right;'>📉 Top 5 Net Losers </p>", unsafe_allow_html=True)
            df_losers = df_mir_summary[df_mir_summary['signed_subs'] < 0].sort_values(by='signed_subs', ascending=False).tail(5)
            
            if not df_losers.empty:
                fig_losers = px.bar(df_losers, x='signed_subs', y=mirror_dim, orientation='h', text_auto=',', template='plotly_dark')
                fig_losers.update_traces(marker_color='#e74c3c', textposition='outside', textfont=dict(color="white", size=11))
                fig_losers.update_layout(
                    margin=dict(l=10, r=10, t=10, b=10), height=250, xaxis_title="Net Subs Lost", yaxis_title=None,
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="white"), yaxis=dict(side='right')
                )
                st.plotly_chart(fig_losers, use_container_width=True)
            else:
                st.caption("No negative net losers for this selection.")
        st.write("---")

    # ==================== [الرسمة رقم 3: الدونات - Behavioral Donut Charts] ====================
    show_in_pie = inflow_profile_col and inflow_profile_col in df_final_chart.columns
    show_out_pie = outflow_profile_col and outflow_profile_col in df_final_chart.columns

    if show_in_pie or show_out_pie:
        st.markdown("##### 🍰 Behavioral Mix Analysis (Inflow vs Outflow Profiles)")
        col_pie1, col_pie2 = st.columns(2)
        
        behavior_colors = {'MIX': '#7f8c8d', 'BC_ONLY': '#f39c12', 'NORMAL_ONLY': '#c0392b', 'SILENT': '#34495e'}
        
        with col_pie1:
            if show_in_pie:
                st.markdown("<p style='text-align: center; color: #2ecc71; font-weight: bold;'>🟢 INFLOW Profile</p>", unsafe_allow_html=True)
                df_in = df_final_chart[df_final_chart['movement_type'] == 'INFLOW']
                if not df_in.empty:
                    df_in_pie = df_in.groupby(inflow_profile_col)['unq_subs'].sum().reset_index()
                    fig_in_pie = px.pie(df_in_pie, values='unq_subs', names=inflow_profile_col, hole=0.4, color=inflow_profile_col, color_discrete_map=behavior_colors, template='plotly_dark')
                    fig_in_pie.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=250, showlegend=True, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', legend=dict(font=dict(color="white", size=12)))
                    fig_in_pie.update_traces(textposition='inside', textinfo='percent', textfont=dict(color="white", size=12, weight="bold"))
                    st.plotly_chart(fig_in_pie, use_container_width=True)
                else:
                    st.caption("No Inflow data available.")
            else:
                st.info("ℹ️ Inflow profile chart is disabled for this tab.")
                
        with col_pie2:
            if show_out_pie:
                st.markdown("<p style='text-align: center; color: #e74c3c; font-weight: bold;'>🔴 OUTFLOW Profile</p>", unsafe_allow_html=True)
                df_out = df_final_chart[df_final_chart['movement_type'] == 'OUTFLOW']
                if not df_out.empty:
                    df_out_pie = df_out.groupby(outflow_profile_col)['unq_subs'].sum().reset_index()
                    fig_out_pie = px.pie(df_out_pie, values='unq_subs', names=outflow_profile_col, hole=0.4, color=outflow_profile_col, color_discrete_map=behavior_colors, template='plotly_dark')
                    fig_out_pie.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=250, showlegend=True, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', legend=dict(font=dict(color="white", size=12)))
                    fig_out_pie.update_traces(textposition='inside', textinfo='percent', textfont=dict(color="white", size=12, weight="bold"))
                    st.plotly_chart(fig_out_pie, use_container_width=True)
                else:
                    st.caption("No Outflow data available.")
            else:
                st.info("ℹ️ Outflow profile chart is disabled for this tab.")



















#==================================
#Network
#==================================

#===================   GEMINI



# def get_dynamic_network_analysis(df, target_day, past_dates, filters_dict, metrics_map):
#     # تحويل التواريخ لضمان التوافق
#     df = df.copy()
#     df['rch_day'] = pd.to_datetime(df['rch_day'])
#     target_day = pd.to_datetime(target_day)
#     past_dates = [pd.to_datetime(d) for d in past_dates]

#     # الفلترة الأساسية
#     df_filtered = df[df['rch_day'].isin([target_day] + past_dates)].copy()
    
#     # تطبيق الفلاتر (الديناميكية)
#     for col, val in filters_dict.items():
#         if val != "All":
#             df_filtered = df_filtered[df_filtered[col] == val]

#     if df_filtered.empty: return None

#     df_curr = df_filtered[df_filtered['rch_day'] == target_day]
#     df_past = df_filtered[df_filtered['rch_day'].isin(past_dates)]

#     if df_curr.empty or df_past.empty: return None

#     # الحسابات
#     metrics_cols = list(metrics_map.keys())
#     past_avg = df_past.groupby('site_code')[metrics_cols].mean().reset_index()
    
#     merged = pd.merge(df_curr, past_avg, on='site_code', how='inner', suffixes=('', '_past'))

#     for col, name in metrics_map.items():
#         merged[f'{name} Diff'] = merged[col] - merged[f'{col}_past']
#         merged[f'{name} Change %'] = (merged[f'{name} Diff'] / merged[f'{col}_past']) * 100
        
#     return merged.replace([np.inf, -np.inf], np.nan).fillna(0)














# def f_tab_network_dynamic(df_net, dimensions_list, target_day, metrics_map):
#     st.subheader("📡 Network Sites Performance & Top 10 Analysis")

#     # 1. الفلاتر
#     filters = {}
#     temp_df = df_net.copy()
#     for dim in dimensions_list:
#         options = ["All"] + list(temp_df[dim].dropna().unique())
#         filters[dim] = st.selectbox(f"Filter by {dim.replace('_', ' ').title()}:", options, key=f"net_{dim}")
#         if filters[dim] != "All":
#             temp_df = temp_df[temp_df[dim] == filters[dim]]

#     # 2. وضع العرض (Growth vs Drop)
#     analysis_mode = st.radio("📊 View:", ["📈 Growth", "📉 Drop"], horizontal=True, key="net_analysis_mode")
#     st.markdown("---")

#     # 3. التابات والتواريخ
#     tabs = st.tabs(["Daily", "Weekly", "Monthly"])
    
#     configs = {
#         "Daily": [target_day - timedelta(days=i) for i in range(1, 7)],
#         "Weekly": [target_day - timedelta(days=7*i) for i in range(1, 5)],
#         "Monthly": [target_day - timedelta(days=30*i) for i in range(1, 5)]
#     }

#     # 4. التنفيذ
#     for tab, (name, past_dates) in zip(tabs, configs.items()):
#         with tab:
#             # الحساب
#             res = get_dynamic_network_analysis(temp_df, target_day, past_dates, filters, metrics_map)
            
#             # العرض (ربطنا الـ render هنا مباشرة)
#             if res is not None and not res.empty:
#                 # ملاحظة: تأكد إن فانكشن الـ render بتستقبل (res, analysis_mode)
#                 render_top_10_columns(res, analysis_mode)
#             else:
#                 st.warning("No data found. Try changing the filters or date.")




























#================ GPT  V1






# =========================================================
# NETWORK MODULE CONFIGS
# =========================================================


# 📂 تعريف مسارات الفولدرات في أول السكريبت
# RECHARGE_DIR = "Data_Drive/recharge_module/"
# # DATA_DIR     = "Data_Drive/data_module/"
# # VOICE_DIR    = "Data_Drive/voice_module/"
# # CASH_DIR     = "Data_Drive/orange_cash_module/"

# # RCH_SITES_PER_DAY_HIST = pd.read_parquet(f"{RECHARGE_DIR}RCH_SITES_PER_DAY_HIST.parquet"



# NETWORK_MODULES = {

#     "recharge": {
#         "module_name": "Recharge",
#         "file_path": f"{RECHARGE_DIR}RCH_SITES_PER_DAY_HIST.parquet",

#         "metrics": {
#             "Subscribers": "unq_subs",
#             "Transactions": "total_rch_cnt",
#             "Amount": "total_rch_amt"
#         }
#     },

#     "voice": {
#         "module_name": "Voice",
#         "file_path": f"{RECHARGE_DIR}RCH_SITES_PER_DAY_HIST.parquet",

#         "metrics": {
#             "Subscribers": "unq_subs",
#             "Minutes": "total_minutes",
#             "Calls": "total_calls"
#         }
#     },

#     "data": {
#         "module_name": "Data",
#         "file_path": f"{RECHARGE_DIR}RCH_SITES_PER_DAY_HIST.parquet",

#         "metrics": {
#             "Subscribers": "unq_subs",
#             "MB Usage": "total_mb",
#             "Sessions": "total_sessions"
#         }
#     },

#     "oc": {
#         "module_name": "Orange Cash",
#         "file_path": f"{RECHARGE_DIR}RCH_SITES_PER_DAY_HIST.parquet",

#         "metrics": {
#             "Subscribers": "unq_subs",
#             "Transactions": "total_trx",
#             "Amount": "total_amt"
#         }
#     }
# }






















# # =========================================================
# # LOAD NETWORK MODULE DATA
# # =========================================================

# #@st.cache_data(ttl=600)
# def load_network_module_data(module_key):

#     try:

#         config = NETWORK_MODULES[module_key]

#         df = pd.read_parquet(config["file_path"])

#         df['rch_day'] = pd.to_datetime(df['rch_day'])

#         return df

#     except Exception as e:

#         st.error(f"❌ Error loading network module: {e}")

#         return pd.DataFrame()
    










# # =========================================================
# # GENERATE COMPARISON DATES
# # =========================================================

# def generate_comparison_dates(target_day):

#     return {

#         "Daily Trend (vs Past 6 Days)": [
#             target_day - timedelta(days=i)
#             for i in range(1, 7)
#         ],

#         "Weekly Trend (vs Same Day - Past 4 Weeks)": [
#             target_day - timedelta(days=7*i)
#             for i in range(1, 5)
#         ],

#         "Monthly Trend (vs Same Stage - Past 4 Months)": [
#             target_day - timedelta(days=30*i)
#             for i in range(1, 5)
#         ]
#     }




















# # =========================================================
# # MAIN ANALYTICS ENGINE
# # =========================================================

# def calculate_network_top10(
#     df_net,
#     target_day,
#     past_dates_list,
#     metrics_config,
#     selected_zone="All",
#     selected_gov="All"
# ):

#     all_needed_dates = [target_day] + list(past_dates_list)

#     df_filtered = df_net[
#         df_net['rch_day'].isin(all_needed_dates)
#     ].copy()

#     # =========================
#     # APPLY FILTERS
#     # =========================

#     if selected_zone != "All":

#         df_filtered = df_filtered[
#             df_filtered['market_zone'] == selected_zone
#         ]

#     if selected_gov != "All":

#         df_filtered = df_filtered[
#             df_filtered['governorate'] == selected_gov
#         ]

#     if df_filtered.empty:
#         return None

#     # =========================
#     # CURRENT / PAST
#     # =========================

#     df_curr = df_filtered[
#         df_filtered['rch_day'] == target_day
#     ]

#     df_past = df_filtered[
#         df_filtered['rch_day'].isin(past_dates_list)
#     ]

#     if df_curr.empty or df_past.empty:
#         return None

#     # =========================
#     # BUILD PAST AGG
#     # =========================

#     metric_cols = list(metrics_config.values())

#     past_avg = (
#         df_past
#         .groupby('site_code')[metric_cols]
#         .mean()
#         .reset_index()
#     )

#     rename_map = {}

#     for col in metric_cols:

#         rename_map[col] = f"past_{col}_avg"

#     past_avg = past_avg.rename(columns=rename_map)

#     # =========================
#     # MERGE
#     # =========================

#     merged = pd.merge(
#         df_curr,
#         past_avg,
#         on='site_code',
#         how='inner'
#     )

#     if merged.empty:
#         return None

#     # =========================
#     # DYNAMIC KPI CALCULATIONS
#     # =========================

#     for metric_name, metric_col in metrics_config.items():

#         merged[f"{metric_name}_Diff"] = (
#             merged[metric_col]
#             - merged[f"past_{metric_col}_avg"]
#         )

#         merged[f"{metric_name}_Pct"] = (
#             merged[f"{metric_name}_Diff"]
#             / merged[f"past_{metric_col}_avg"]
#         ) * 100

#     merged = merged.replace(
#         [np.inf, -np.inf],
#         np.nan
#     ).fillna(0)

#     return merged















# # =========================================================
# # RENDER TABLES
# # =========================================================

# def render_network_tables(
#     df_res,
#     metrics_config,
#     analysis_mode
# ):

#     if df_res is None or df_res.empty:

#         st.warning(
#             "⚠️ No historical data found for this selection."
#         )

#         return

#     metric_names = list(metrics_config.keys())

#     cols = st.columns(len(metric_names))

#     # =========================
#     # SORT MODE
#     # =========================

#     if "Growth" in analysis_mode:

#         get_ranked = lambda df, col: df.nlargest(10, col)

#         title_suffix = "Growth"

#     else:

#         get_ranked = lambda df, col: df.nsmallest(10, col)

#         title_suffix = "Drop"

#     # =========================
#     # COLORING
#     # =========================

#     def color_delta(val):

#         color = '#123819' if val >= 0 else '#5c1d1d'

#         return f'''
#             background-color: {color};
#             color: white;
#             font-weight: bold;
#         '''

#     # =========================
#     # LOOP METRICS
#     # =========================

#     for idx, metric_name in enumerate(metric_names):

#         with cols[idx]:

#             diff_col = f"{metric_name}_Diff"

#             pct_col = f"{metric_name}_Pct"

#             st.markdown(
#                 f"""
#                 <h4 style='text-align:center; color:#4A90E2;'>
#                 🔝 Top 10 {metric_name} {title_suffix}
#                 </h4>
#                 """,
#                 unsafe_allow_html=True
#             )

#             top_df = get_ranked(
#                 df_res,
#                 diff_col
#             )[
#                 [
#                     'site_code',
#                     diff_col,
#                     pct_col
#                 ]
#             ]

#             top_df.columns = [
#                 'Site Code',
#                 f'{metric_name} Delta',
#                 'Growth %'
#             ]

#             st.dataframe(
#                 top_df
#                 .style
#                 .format({
#                     f'{metric_name} Delta': '{:+.0f}',
#                     'Growth %': '{:+.1f}%'
#                 })
#                 .map(
#                     color_delta,
#                     subset=['Growth %']
#                 ),

#                 use_container_width=True,
#                 hide_index=True
#             )















# # =========================================================
# # FINAL NETWORK TAB ENGINE
# # =========================================================

# def f_tab_network(
#     module_key,
#     global_selected_date
# ):

#     config = NETWORK_MODULES[module_key]

#     st.subheader(
#         f"📡 {config['module_name']} Network Performance"
#     )

#     # =========================
#     # LOAD DATA
#     # =========================

#     df_net = load_network_module_data(module_key)

#     if df_net.empty:
#         return

#     target_day = pd.to_datetime(global_selected_date)

#     # =========================
#     # FILTERS
#     # =========================

#     col_f1, col_f2 = st.columns(2)

#     with col_f1:

#         zones_options = ["All"] + list(
#             df_net['market_zone']
#             .dropna()
#             .unique()
#         )

#         selected_zone = st.selectbox(
#             "🌐 Select Market Zone:",
#             options=zones_options,
#             key=f"{module_key}_zone"
#         )

#     with col_f2:

#         if selected_zone != "All":

#             available_govs = df_net[
#                 df_net['market_zone'] == selected_zone
#             ]['governorate'].dropna().unique()

#         else:

#             available_govs = df_net[
#                 'governorate'
#             ].dropna().unique()

#         govs_options = ["All"] + list(available_govs)

#         selected_gov = st.selectbox(
#             "📍 Select Governorate:",
#             options=govs_options,
#             key=f"{module_key}_gov"
#         )

#     # =========================
#     # ANALYSIS MODE
#     # =========================

#     st.markdown("---")

#     analysis_mode = st.radio(
#         "📊 Select Analysis View:",
#         options=[
#             "📈 Top 10 Growth (Highest Gain)",
#             "📉 Top 10 Drop (Highest Loss)"
#         ],
#         horizontal=True,
#         key=f"{module_key}_analysis_mode"
#     )

#     st.markdown("---")

#     # =========================
#     # COMPARISON MODES
#     # =========================

#     comparison_modes = generate_comparison_dates(
#         target_day
#     )

#     sub_tabs = st.tabs(
#         list(comparison_modes.keys())
#     )

#     # =========================
#     # LOOP SUBTABS
#     # =========================

#     for idx, (
#         mode_name,
#         past_dates
#     ) in enumerate(comparison_modes.items()):

#         with sub_tabs[idx]:

#             df_result = calculate_network_top10(
#                 df_net=df_net,
#                 target_day=target_day,
#                 past_dates_list=past_dates,
#                 metrics_config=config["metrics"],
#                 selected_zone=selected_zone,
#                 selected_gov=selected_gov
#             )

#             render_network_tables(
#                 df_result,
#                 config["metrics"],
#                 analysis_mode
#             )
















#================NETWORK  GPT V2





#=========================================================
#   1. CONFIG LAYER
#=========================================================




RECHARGE_DIR = "Data_Drive/recharge_module/"
DATA_DIR     = "Data_Drive/data_module/"
VOICE_DIR    = "Data_Drive/voice_module/"
CASH_DIR     = "Data_Drive/orange_cash_module/"


NETWORK_MODULES = {

    "RCH": {
        "module_name": "RCH",
        "file_path": f"{RECHARGE_DIR}RCH_SITES_PER_DAY_HIST.parquet",
        "date_col": "rch_day",
        "metrics": {
            "Subscribers" : "unq_subs",
            "Transactions": "total_rch_cnt",
            "Amount"      : "total_rch_amt"
        }
    },

    "OUG_VOICE": {
        "module_name": "OUG_VOICE",
        "file_path": f"{VOICE_DIR}OUG_VOICE_SITES_PER_DAY_HIST.parquet",
        "date_col": "vu_day",
        "metrics": {
            "Subscribers": "unq_subs",
            "Minutes"    : "total_oug_mous",
            "Calls"      : "total_oug_cnts"
        }
    },

    "DATA_USAGE": {
        "module_name": "DATA_USAGE",
        "file_path": f"{DATA_DIR}DATA_USAGE_SITES_PER_DAY_HIST.parquet",
        "date_col": "du_day",
        "metrics": {
            "Subscribers"   : "unq_subs",
            "Total MB Usage": "total_mb",
            "5G MB Usage"   : "total_5g_mb"
        }
    },

    "OC": {
        "module_name": "OC",
        "file_path": f"{CASH_DIR}OC_SITES_PER_DAY_HIST.parquet",
        "date_col": "oc_day",
        "metrics": {
            "Subscribers" : "unq_subs",
            "Transactions": "total_oc_trx_cnts",
            "Amount"      : "total_oc_trx_amts"
        }
    }
}







#=========================================================
#   2.  LOAD DATA
#=========================================================



#@st.cache_data(ttl=600)
def load_network_module_data(module_key):

    config = NETWORK_MODULES[module_key]

    df = pd.read_parquet(config["file_path"])
    df[config["date_col"]] = pd.to_datetime(df[config["date_col"]])

    return df






#=========================================================
#   3. COMPARISON ENGINE (WITH DATES + DESCRIPTION)
#=========================================================



def generate_comparison_modes(target_day):

    target_day = pd.to_datetime(target_day)

    return {

        "Daily Trend": {
            "dates": [target_day - timedelta(days=i) for i in range(1, 7)],
            "description": "Compared Against Average of Previous 6 Days"
        },

        "Weekly Trend": {
            "dates": [target_day - timedelta(days=7*i) for i in range(1, 5)],
            "description": "Compared Against Same Day Across Previous 4 Weeks"
        },

        "Monthly Trend": {
            "dates": [target_day - timedelta(days=30*i) for i in range(1, 5)],
            "description": "Compared Against Same Stage Across Previous 4 Months"
        }
    }











#=========================================================
#  4. ANALYTICS ENGINE
#=========================================================




def calculate_network_top10(
    df,
    date_col,
    target_day,
    past_dates,
    metrics,
    selected_zone,
    selected_gov
):

    all_dates = [target_day] + past_dates

    df = df[df[date_col].isin(all_dates)].copy()

    if selected_zone != "All":
        df = df[df["market_zone"] == selected_zone]

    if selected_gov != "All":
        df = df[df["governorate"] == selected_gov]

    if df.empty:
        return None

    df_curr = df[df[date_col] == target_day]
    df_past = df[df[date_col].isin(past_dates)]

    metric_cols = list(metrics.values())

    past_avg = (
        df_past.groupby("site_code")[metric_cols]
        .mean()
        .reset_index()
    )

    rename = {c: f"past_{c}" for c in metric_cols}
    past_avg = past_avg.rename(columns=rename)

    merged = df_curr.merge(past_avg, on="site_code", how="inner")

    for name, col in metrics.items():

        merged[f"{name}_diff"] = merged[col] - merged[f"past_{col}"]
        merged[f"{name}_pct"] = (
            merged[f"{name}_diff"] / merged[f"past_{col}"]
        ) * 100

    return merged.replace([np.inf, -np.inf], 0).fillna(0)










#=========================================================
#  5. INSIGHT HEADER (NEW IMPORTANT PART)
#=========================================================



def render_context_info(module_name, target_day, mode_desc, dates_list, zone, gov):

    st.info(f"""
📡 Module: {module_name}

📅 Selected Date: {target_day}

📊 {mode_desc}

🗓 Comparison Dates:
{', '.join([str(d.date()) for d in dates_list])}

🌐 Zone: {zone}
📍 Governorate: {gov}
""")









#=========================================================
#  6. RENDER ENGINE
#=========================================================




# def render_network_tables(df, metrics, analysis_mode):

#     if df is None or df.empty:
#         st.warning("No data available")
#         return

#     metric_names = list(metrics.keys())

#     cols = st.columns(len(metric_names))

#     is_growth = "Growth" in analysis_mode

#     for i, metric in enumerate(metric_names):

#         diff = f"{metric}_diff"
#         pct = f"{metric}_pct"

#         with cols[i]:

#             st.markdown(f"### 🔝 Top 10 {metric}")

#             if is_growth:
#                 top = df.nlargest(10, diff)
#             else:
#                 top = df.nsmallest(10, diff)

#             st.dataframe(
#                 top[["site_code", diff, pct]],
#                 use_container_width=True
#             )





# def render_network_tables(df, metrics, analysis_mode):
#     if df is None or df.empty:
#         st.warning("No data available")
#         return

#     # فانكشن الألوان للـ Change %
#     def color_delta(val):
#         color = '#123819' if val >= 0 else '#5c1d1d'
#         return f'background-color: {color}; color: white;'

#     metric_names = list(metrics.keys())
#     cols = st.columns(len(metric_names))
#     is_growth = "Growth" in analysis_mode

#     for i, metric in enumerate(metric_names):
#         diff = f"{metric}_diff"
#         pct = f"{metric}_pct"

#         with cols[i]:
#             # العنوان الديناميكي
#             title_prefix = "Growth in" if is_growth else "Drop in"
#             st.markdown(f"### 🔝 {title_prefix} {metric}")

#             # الترتيب
#             top = df.nlargest(10, diff) if is_growth else df.nsmallest(10, diff)
            
#             # تجهيز الداتا للعرض
#             df_display = top[['site_code', diff, pct]].rename(
#                 columns={'site_code': 'Site', diff: 'Change', pct: 'Change %'}
#             )
            
#             # التنسيق الاحترافي
#             st.dataframe(
#                 df_display.style.format({'Change': '{:+.0f}', 'Change %': '{:+.1f}%'})
#                           .map(color_delta, subset=['Change %']),
#                 use_container_width=True, 
#                 hide_index=True
#             )







# وكمان عشان "render_network_tables" تبقى كاملة بالتعديلات اللي اتفقنا عليها:
def render_network_tables(df, metrics, analysis_mode):
    if df is None or df.empty:
        st.warning("No data available")
        return

    def color_delta(val):
        color = '#123819' if val >= 0 else '#5c1d1d'
        return f'background-color: {color}; color: white;'

    metric_names = list(metrics.keys())
    cols = st.columns(len(metric_names))
    is_growth = "Growth" in analysis_mode

    for i, metric in enumerate(metric_names):
        diff = f"{metric}_diff"
        pct = f"{metric}_pct"

        with cols[i]:
            # التعديل هنا: العنوان الديناميكي
            title_prefix = "Growth in" if is_growth else "Drop in"
            st.markdown(f"### 🔝 {title_prefix} {metric}")

            top = df.nlargest(10, diff) if is_growth else df.nsmallest(10, diff)
            
            df_display = top[['site_code', diff, pct]].rename(
                columns={'site_code': 'Site', diff: 'Change', pct: 'Change %'}
            )
            
            st.dataframe(
                df_display.style.format({'Change': '{:+.0f}', 'Change %': '{:+.1f}%'})
                          .map(color_delta, subset=['Change %']),
                use_container_width=True, 
                hide_index=True
            )






#=========================================================
#  7. MAIN TAB FUNCTION
#=========================================================





def f_tab_network(module_key, selected_day):
    # 1. إجبار ظهور الخط باللون الأبيض لكل الـ Labels والـ Radio Options
    st.markdown("""
        <style>
        /* Labels of inputs */
        div[data-testid="stWidgetLabel"] p { color: white !important; }
        /* Radio button options */
        div[role="radiogroup"] label p { color: white !important; }
        </style>
    """, unsafe_allow_html=True)

    config = NETWORK_MODULES[module_key]

    df = load_network_module_data(module_key)

    if df.empty:
        return

    target_day = pd.to_datetime(selected_day)

    col1, col2 = st.columns(2)

    with col1:
        zone = st.selectbox("Zone", ["All"] + list(df["market_zone"].unique()))

    with col2:
        gov = st.selectbox("Gov", ["All"] + list(df["governorate"].unique()))

    analysis_mode = st.radio(
        "Mode",
        ["Growth", "Drop"],
        horizontal=True
    )

    comparison_modes = generate_comparison_modes(target_day)

    tabs = st.tabs(list(comparison_modes.keys()))

    for i, (mode_name, meta) in enumerate(comparison_modes.items()):

        with tabs[i]:

            df_res = calculate_network_top10(
                df=df,
                date_col=config["date_col"],
                target_day=target_day,
                past_dates=meta["dates"],
                metrics=config["metrics"],
                selected_zone=zone,
                selected_gov=gov
            )

            render_context_info(
                config["module_name"],
                target_day.date(),
                meta["description"],
                meta["dates"],
                zone,
                gov
            )

            render_network_tables(
                df_res,
                config["metrics"],
                analysis_mode
            )





































#============PASSWORD



def check_password():
    """بتفرمل الأبلكيشن وتطلع شاشة تسجيل الدخول بناءً على صلاحية الباسورد من الـ secrets"""
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False
    if "user_role" not in st.session_state:
        st.session_state.user_role = None

    # لو اليوزر كتبها صح قبل كده، عدي علطول
    if st.session_state.password_correct:
        return True

    # رسم شاشة الدخول الشيك في نص الصفحة
    st.title("🔒 Orange Internal Dashboard")
    user_password = st.text_input("Enter Password to Access the Dashboard:", type="password")
    
    if st.button("Login"):
        # 1️⃣ بيقارن بباسورد الأدمن / المدير
        if user_password == st.secrets["admin_password"]:
            st.session_state.password_correct = True
            st.session_state.user_role = "admin" # حفظ الصلاحية كـ أدمن
            st.rerun() 
            
        # 2️⃣ بيقارن بباسورد مهندس النتورك
        elif user_password == st.secrets["network_password"]:
            st.session_state.password_correct = True
            st.session_state.user_role = "network" # حفظ الصلاحية كـ نتورك
            st.rerun()
            
        else:
            st.error("❌ Incorrect Password. Please try again.")
            
    return False

# 🛑 تشغيل حارس البوابة الرئيسي (لو رجع False الأبلكيشن هيفضل مقفول بره)
if not check_password():
    st.stop()













#Data_Drive_DIR = "Data_Drive/"


# 📂 تعريف مسارات الفولدرات في أول السكريبت
RECHARGE_DIR = "Data_Drive/recharge_module/"
DATA_DIR     = "Data_Drive/data_module/"
VOICE_DIR    = "Data_Drive/voice_module/"
CASH_DIR     = "Data_Drive/orange_cash_module/"

# 📊 وقت السحب والقراءة تحت في الكود:
#df_recharge = pd.read_parquet(f"{RECHARGE_DIR}recharge_master.parquet")
#df_data     = pd.read_parquet(f"{DATA_DIR}data_master.parquet")





# =====================================================
# Git Connection
# =====================================================

#@st.cache_data(ttl=600)
#@st.cache_data(ttl=60)
def load_data():
    try:
        # Read From Repo
        RCH_PER_DAY_HIST = pd.read_parquet(f"{RECHARGE_DIR}RCH_PER_DAY_HIST.parquet")
        RCH_PER_DAY_HIST['RCH_DAY'] = pd.to_datetime(RCH_PER_DAY_HIST['RCH_DAY'])


        DATA_USAGE_PER_DAY_HIST  = pd.read_parquet(f"{DATA_DIR}DATA_USAGE_PER_DAY_HIST.parquet")
        DATA_USAGE_PER_DAY_HIST['data_usage_day'] = pd.to_datetime(DATA_USAGE_PER_DAY_HIST['data_usage_day'])


        OUG_VOICE_PER_DAY_HIST   = pd.read_parquet(f"{VOICE_DIR}OUG_VOICE_PER_DAY_HIST.parquet")
        OUG_VOICE_PER_DAY_HIST['voice_usage_day'] = pd.to_datetime(OUG_VOICE_PER_DAY_HIST['voice_usage_day'])


        OC_PER_DAY_HIST  = pd.read_parquet(f"{CASH_DIR}OC_PER_DAY_HIST.parquet")
        OC_PER_DAY_HIST['oc_usage_day']           = pd.to_datetime(OC_PER_DAY_HIST['oc_usage_day'])


        OC_SERVICES_PER_DAY_HIST = pd.read_parquet(f"{CASH_DIR}OC_SERVICES_PER_DAY_HIST.parquet")
        OC_SERVICES_PER_DAY_HIST['oc_usage_day']  = pd.to_datetime(OC_SERVICES_PER_DAY_HIST['oc_usage_day'])






        
        RCH_IBRO_PER_DAY_HIST = pd.read_parquet(f"{RECHARGE_DIR}RCH_IBRO_PER_DAY_HIST.parquet")
        RCH_IBRO_PER_DAY_HIST['reported_date'] = pd.to_datetime(RCH_IBRO_PER_DAY_HIST['reported_date'])


        DATA_USAGE_IBRO_PER_DAY_HIST = pd.read_parquet(f"{DATA_DIR}DATA_USAGE_IBRO_PER_DAY_HIST.parquet")
        DATA_USAGE_IBRO_PER_DAY_HIST['reported_date'] = pd.to_datetime(DATA_USAGE_IBRO_PER_DAY_HIST['reported_date'])


        OUG_VOICE_IBRO_PER_DAY_HIST = pd.read_parquet(f"{VOICE_DIR}OUG_VOICE_IBRO_PER_DAY_HIST.parquet")
        OUG_VOICE_IBRO_PER_DAY_HIST['reported_date'] = pd.to_datetime(OUG_VOICE_IBRO_PER_DAY_HIST['reported_date'])


        OC_IBRO_PER_DAY_HIST = pd.read_parquet(f"{CASH_DIR}OC_IBRO_PER_DAY_HIST.parquet")
        OC_IBRO_PER_DAY_HIST['reported_date'] = pd.to_datetime(OC_IBRO_PER_DAY_HIST['reported_date'])










        RCH_SITES_PER_DAY_HIST = pd.read_parquet(f"{RECHARGE_DIR}RCH_SITES_PER_DAY_HIST.parquet")
        RCH_SITES_PER_DAY_HIST['rch_day'] = pd.to_datetime(RCH_SITES_PER_DAY_HIST['rch_day'])


        DATA_USAGE_SITES_PER_DAY_HIST = pd.read_parquet(f"{DATA_DIR}DATA_USAGE_SITES_PER_DAY_HIST.parquet")
        DATA_USAGE_SITES_PER_DAY_HIST['du_day'] = pd.to_datetime(DATA_USAGE_SITES_PER_DAY_HIST['du_day'])


        OUG_VOICE_SITES_PER_DAY_HIST = pd.read_parquet(f"{VOICE_DIR}OUG_VOICE_SITES_PER_DAY_HIST.parquet")
        OUG_VOICE_SITES_PER_DAY_HIST['vu_day'] = pd.to_datetime(OUG_VOICE_SITES_PER_DAY_HIST['vu_day'])


        OC_SITES_PER_DAY_HIST = pd.read_parquet(f"{CASH_DIR}OC_SITES_PER_DAY_HIST.parquet")
        OC_SITES_PER_DAY_HIST['oc_day'] = pd.to_datetime(OC_SITES_PER_DAY_HIST['oc_day'])



        return RCH_PER_DAY_HIST , DATA_USAGE_PER_DAY_HIST , OUG_VOICE_PER_DAY_HIST , OC_PER_DAY_HIST , OC_SERVICES_PER_DAY_HIST           , RCH_IBRO_PER_DAY_HIST , DATA_USAGE_IBRO_PER_DAY_HIST , OUG_VOICE_IBRO_PER_DAY_HIST , OC_IBRO_PER_DAY_HIST               , RCH_SITES_PER_DAY_HIST , DATA_USAGE_SITES_PER_DAY_HIST , OUG_VOICE_SITES_PER_DAY_HIST , OC_SITES_PER_DAY_HIST
               
    

    except Exception as e:
        st.error(f"❌ Error loading': {e}")
        return pd.DataFrame()
    







# #@st.cache_data(ttl=600)
# def load_master_network_data():
#     try:
#         # قراءة ملف الباركيه الماستر الـ 18 ميجا المرفوع في الريبو
#         #RCH_SITES_PER_DAY_HIST = pd.read_parquet("network_master.parquet")
#         RCH_SITES_PER_DAY_HIST = pd.read_parquet(f"{RECHARGE_DIR}RCH_SITES_PER_DAY_HIST.parquet")
#         RCH_SITES_PER_DAY_HIST['rch_day'] = pd.to_datetime(RCH_SITES_PER_DAY_HIST['rch_day'])
#         return RCH_SITES_PER_DAY_HIST
#     except Exception as e:
#         st.error(f"❌ Error loading 'RCH_SITES_PER_DAY_HIST.parquet': {e}")
#         return pd.DataFrame()
    



#==========SUMMARY HEADER CARDS

# #@st.cache_data(ttl=600)
# def load_data():
#     try:
#         # قراءة ملف الباركيه الماستر الـ 18 ميجا المرفوع في الريبو
#         # DATA_USAGE_PER_DAY_HIST      = pd.read_parquet("DATA_USAGE_PER_DAY_HIST.parquet")
#         # OUG_VOICE_PER_DAY_HIST = pd.read_parquet("OUG_VOICE_PER_DAY_HIST.parquet")
#         # OC_PER_DAY_HIST        = pd.read_parquet("OC_PER_DAY_HIST.parquet")

#         DATA_USAGE_PER_DAY_HIST  = pd.read_parquet(f"{DATA_DIR}DATA_USAGE_PER_DAY_HIST.parquet")
#         OUG_VOICE_PER_DAY_HIST   = pd.read_parquet(f"{VOICE_DIR}OUG_VOICE_PER_DAY_HIST.parquet")
#         OC_PER_DAY_HIST          = pd.read_parquet(f"{CASH_DIR}OC_PER_DAY_HIST.parquet")
#         OC_SERVICES_PER_DAY_HIST = pd.read_parquet(f"{CASH_DIR}OC_SERVICES_PER_DAY_HIST.parquet")



#         DATA_USAGE_PER_DAY_HIST['data_usage_day'] = pd.to_datetime(DATA_USAGE_PER_DAY_HIST['data_usage_day'])
#         OUG_VOICE_PER_DAY_HIST['voice_usage_day'] = pd.to_datetime(OUG_VOICE_PER_DAY_HIST['voice_usage_day'])
#         OC_PER_DAY_HIST['oc_usage_day']           = pd.to_datetime(OC_PER_DAY_HIST['oc_usage_day'])
#         OC_SERVICES_PER_DAY_HIST['oc_usage_day']  = pd.to_datetime(OC_SERVICES_PER_DAY_HIST['oc_usage_day'])



#         return DATA_USAGE_PER_DAY_HIST , OUG_VOICE_PER_DAY_HIST , OC_PER_DAY_HIST , OC_SERVICES_PER_DAY_HIST
#     except Exception as e:
#         st.error(f"❌ Error loading SUMMARY_data': {e}")
#         return pd.DataFrame()



















# استخدام Spinner يظهر بوضوح أثناء التحميل
with st.spinner('Fetching Data...'):
    try:
        #RCH_PER_DAY_HIST = load_data()
        # RCH_PER_DAY_HIST, RCH_IBRO_PER_DAY_HIST = load_data()
        # DATA_USAGE_PER_DAY_HIST , OUG_VOICE_PER_DAY_HIST , OC_PER_DAY_HIST , OC_SERVICES_PER_DAY_HIST = load_data()
        RCH_PER_DAY_HIST , DATA_USAGE_PER_DAY_HIST , OUG_VOICE_PER_DAY_HIST , OC_PER_DAY_HIST , OC_SERVICES_PER_DAY_HIST , RCH_IBRO_PER_DAY_HIST , DATA_USAGE_IBRO_PER_DAY_HIST , OUG_VOICE_IBRO_PER_DAY_HIST , OC_IBRO_PER_DAY_HIST , RCH_SITES_PER_DAY_HIST , DATA_USAGE_SITES_PER_DAY_HIST , OUG_VOICE_SITES_PER_DAY_HIST , OC_SITES_PER_DAY_HIST =  load_data()
    except Exception as e:
        st.error(f'Error connecting to database: {e}')
        st.stop()





#===========================
# daily summary
#===========================


rch_daily_summary = RCH_PER_DAY_HIST.groupby('RCH_DAY').agg({
        'DAILY_UNQ_SUBS': 'max',
        'DAILY_TRX_COUNTS': 'max',
        'DAILY_TRX_AMOUNTS': 'max'
    }).reset_index()

rch_daily_summary["avg_recharge"] = rch_daily_summary["DAILY_TRX_AMOUNTS"] / rch_daily_summary["DAILY_UNQ_SUBS"]


rch_daily_summary = rch_daily_summary.sort_values('RCH_DAY')









oc_daily_summary = OC_PER_DAY_HIST.groupby('oc_usage_day').agg({
        'total_unq_subs': 'max',
        'total_oc_trx_cnts': 'max',
        'total_oc_trx_amts': 'max'
    }).reset_index()

oc_daily_summary["avg_oc_amt"] = oc_daily_summary["total_oc_trx_amts"] / oc_daily_summary["total_unq_subs"]


oc_daily_summary = oc_daily_summary.sort_values('oc_usage_day')










data_daily_summary = DATA_USAGE_PER_DAY_HIST.groupby('data_usage_day').agg({
        'total_unq_subs': 'max',
        'total_mb': 'max',
        'total_gb': 'max'
    }).reset_index()

data_daily_summary["avg_mb"] = data_daily_summary["total_mb"] / data_daily_summary["total_unq_subs"]
data_daily_summary["avg_gb"] = data_daily_summary["total_gb"] / data_daily_summary["total_unq_subs"]


data_daily_summary = data_daily_summary.sort_values('data_usage_day')






voice_daily_summary = OUG_VOICE_PER_DAY_HIST.groupby('voice_usage_day').agg({
        'total_unq_subs': 'max',
        'total_oug_cnts': 'max',
        'total_oug_mous': 'max'
    }).reset_index()

voice_daily_summary["avg_calls_cnts"] = voice_daily_summary["total_oug_cnts"] / voice_daily_summary["total_unq_subs"]
voice_daily_summary["avg_calls_mnts"] = voice_daily_summary["total_oug_mous"] / voice_daily_summary["total_unq_subs"]


voice_daily_summary = voice_daily_summary.sort_values('voice_usage_day')













# العناوين والمدخلات
st.markdown('<div class="main-title">📊 All Products Behavior Monitoring</div>', unsafe_allow_html=True)

# 1. تحديد التاريخ من المدخلات وحساب اليوم المختار
max_date = rch_daily_summary['RCH_DAY'].max().date()
selected_date_input = st.date_input("Select Monitoring Date", value=max_date)
selected_day = pd.to_datetime(selected_date_input)

# 2. حساب تفاصيل اليوم المختار واليوم السابق (D-1) للمقارنة
weekday_name = selected_day.day_name()
month_phase = get_month_phase(selected_day)
prev_day = selected_day - timedelta(days=1)

# تاريخ حدث زيادة الأسعار المحوري
price_update_date = pd.to_datetime("2026-05-05")

# دالة ذكية لتحديد حالة السعر لكل تاريخ
def get_price_status_html(target_date):
    if target_date < price_update_date:
        return '<span style="color: #238636; font-weight: 800;">🟢 Pre-Price Update</span>'
    elif target_date == price_update_date:
        return '<span style="color: #F2CC60; font-weight: 800;">🟡 Price Update Day (5/5)</span>'
    else:
        return '<span style="color: #DA3633; font-weight: 800;">🔴 Post-Price Update</span>'

# جلب الحالة لليومين
current_status = get_price_status_html(selected_day)
prev_status = get_price_status_html(prev_day)

# 3. عرض الهيدر الرئيسي الأصلي النظيف كما كان تماماً
#st.markdown(f'<div class="header-bar"><div>📅 {selected_day.date()}</div><div>📆 {weekday_name}</div><div>🗓️ {month_phase}</div></div>', unsafe_allow_html=True)
st.markdown(f'<div class="header-bar"><div>📅 {selected_day.date()}</div><div>📆 <span style="color: #F2CC60;">{weekday_name}</span></div><div>🗓️ <span style="color: #238636;">{month_phase}</span></div></div>', unsafe_allow_html=True)


# 4. عرض الهيدر الصغير الجديد المتسنتر للمقارنة بين زون الأسعار لليومين
st.markdown(f"""
<div style="text-align: center; margin-top: -10px; margin-bottom: 25px; font-size: 14px; font-weight: 700; background-color: #161B22; border: 1px solid #30363D; border-radius: 10px; padding: 6px 25px; width: fit-content; margin-left: auto; margin-right: auto; color: #8B949E;">
    Selected Day: {current_status} &nbsp; &nbsp; &nbsp; &nbsp;  | &nbsp; &nbsp; &nbsp; &nbsp; Compared Day (D-1): {prev_status}
</div>
""", unsafe_allow_html=True)







# =========================================================
# 🌍 GLOBAL EXECUTIVE SUMMARY CARDS
# =========================================================



# 1. Summary Cards (Multi-Source High-Level Dashboard)
prev_day = selected_day - timedelta(days=1)

# فلاتر اليوم الحالي واليوم السابق للأربع خدمات (كل واحدة من الداتا فريم بتاعتها)
curr_rch = rch_daily_summary[rch_daily_summary["RCH_DAY"] == selected_day]
prev_rch = rch_daily_summary[rch_daily_summary["RCH_DAY"] == prev_day]

curr_data = DATA_USAGE_PER_DAY_HIST[DATA_USAGE_PER_DAY_HIST["data_usage_day"] == selected_day]
prev_data = DATA_USAGE_PER_DAY_HIST[DATA_USAGE_PER_DAY_HIST["data_usage_day"] == prev_day]

curr_voice = OUG_VOICE_PER_DAY_HIST[OUG_VOICE_PER_DAY_HIST["voice_usage_day"] == selected_day]
prev_voice = OUG_VOICE_PER_DAY_HIST[OUG_VOICE_PER_DAY_HIST["voice_usage_day"] == prev_day]

curr_cash = OC_PER_DAY_HIST[OC_PER_DAY_HIST["oc_usage_day"] == selected_day]
prev_cash = OC_PER_DAY_HIST[OC_PER_DAY_HIST["oc_usage_day"] == prev_day]


# 🛡️ حارس البوابة الذكي (الفرملة المبكرة للأربع خدمات معاً):
if (curr_rch.empty or prev_rch.empty or 
    curr_data.empty or prev_data.empty or 
    curr_voice.empty or prev_voice.empty or 
    curr_cash.empty or prev_cash.empty):
    
    st.warning(f"⚠️ Historical data is incomplete for the selected date range around: **{selected_day.date()}**. Please ensure all master files (Recharge, Data, Voice, Orange Cash) are updated.")
    st.stop() # 🪄 فرملة سحرية تمنع أي إيرور أحمر يظهر لليوزر


# 💡 إعداد الـ Configuration الجديد (اسم الكارت، الداتا فريم الحالية، الداتا فريم السابقة، واسم عمود الـ Unique Subs)
kpis_multi_config = [
    ("Recharge Users", curr_rch, prev_rch, "DAILY_UNQ_SUBS"),
    ("Data Users", curr_data, prev_data, "total_unq_subs"),     # تأكد من اسم العمود عندك في ملف الديتا لو مختلف
    ("Voice Users", curr_voice, prev_voice, "total_unq_subs"),   # تأكد من اسم العمود عندك في ملف الفويس لو مختلف
    ("Orange Cash Users", curr_cash, prev_cash, "total_unq_subs") # تأكد من اسم العمود عندك في ملف الكاش لو مختلف
]


# رسم الـ 4 كروت جنب بعض شياكة من المصادر المتعددة
cols = st.columns(4)
for i, (name, df_c, df_p, col_name) in enumerate(kpis_multi_config):
    curr_val = df_c[col_name].values[0]
    p_val = df_p[col_name].values[0]
    
    # حسبة نسبة النمو أو الهبوط مقارنة بامبارح (D-1)
    if p_val != 0:
        diff = ((curr_val - p_val) / p_val) * 100
    else:
        diff = 0
    
    status_label, status_color = get_status_details(diff)
    delta_class = "green" if diff >= 0 else "red"
    symbol = "+" if diff >= 0 else ""
    
    with cols[i]:
        st.markdown(f"""
        <div class="summary-card" style="border-left: 6px solid {status_color};">
            <div class="summary-label">{name}</div>
            <div class="summary-value">{round(curr_val, 0):,}</div>
            <div class="summary-delta {delta_class}">{symbol}{round(diff, 1)}% vs D-1</div>
            <div class="status-tag" style="background-color: {status_color};">{status_label}</div>
        </div>
        """, unsafe_allow_html=True)

st.write("")






# بيسيب مسافة سطرين (تقدر تزود أو تقلل)
st.markdown("<br>", unsafe_allow_html=True)

# بيعمل بلوك فاضي يعمل مسافة
#st.empty()

#st.markdown("---") # بيعمل خط فاصل شيك وبيدي مسافة تلقائية تحت الهيدر












#========OVERALL TAB 




def RCH_tab_overall():
    rch_kpis = [
        ("Recharge Users", "DAILY_UNQ_SUBS"),
        ("Transactions", "DAILY_TRX_COUNTS"),
        ("Recharge Amount", "DAILY_TRX_AMOUNTS"),
        ("Avg Recharge"  , "avg_recharge")
    ]
    render_dynamic_detailed_cards(df=rch_daily_summary, date_col="RCH_DAY", kpis_config=rch_kpis)



def OC_tab_overall():
    oc_kpis = [
        ("Wallet Users"       , "total_unq_subs"),
        ("Transactions"       , "total_oc_trx_cnts"),
        ("Total Volume (EGP)" , "total_oc_trx_amts"),
        ("Avg AMT / SUB"      , "avg_oc_amt")
    ]
    render_dynamic_detailed_cards(df=oc_daily_summary, date_col="oc_usage_day", kpis_config=oc_kpis)  




def DATA_USAGE_tab_overall():
    data_kpis = [
        ("DATA Users"    , "total_unq_subs"),
        ("Total MB"      , "total_mb"),
        ("Total GB"      , "total_gb"),
        ("Avg MB / SUB"  , "avg_mb")
    ]
    render_dynamic_detailed_cards(df=data_daily_summary, date_col="data_usage_day", kpis_config=data_kpis)   





def OUG_VOICE_tab_overall():
    data_kpis = [
        ("OUG VOICE Users"    , "total_unq_subs"),
        ("Total CALLS"        , "total_oug_cnts"),
        ("Total Minutes"      , "total_oug_mous"),
        ("Avg CALLS / SUB"    , "avg_calls_cnts"),
        ("Avg Minutes / SUB"  , "avg_calls_mnts")
    ]
    render_dynamic_detailed_cards(df=voice_daily_summary, date_col="voice_usage_day", kpis_config=data_kpis)   











#============ALERTS TAB

def RCH_tab_alerts():

    df = get_dynamic_alerts(
        df_raw = RCH_PER_DAY_HIST, 
        date_col="RCH_DAY", 
        dimensions=["RCH_TYPE", "recharge_type_description", "RCH_HOUR_TIERS"], 
        metrics_map={"RCH_AMT": "Amount", "TRX_COUNTS": "Transactions", "UNQ_SUBS": "Subscribers"},
        thresholds=[3, 5, 10, 20] # سلم الريتشارج المخصص
    )

    render_alerts_center_ui(df)




def OC_tab_alerts():

    df = get_dynamic_alerts(
        df_raw=OC_SERVICES_PER_DAY_HIST, 
        date_col="oc_usage_day", 
        dimensions=["service_group"],
        metrics_map={"total_oc_trx_amts": "Volume (EGP)", "total_oc_trx_cnts": "Transactions", "total_unq_subs": "Users"},
        thresholds=[2, 4, 8, 15] # سلم أورانج كاش مخصص وحساس أكتر
    )


    render_alerts_center_ui(df)





def DATA_USAGE_tab_alerts():

    df = get_dynamic_alerts(
        df_raw=DATA_USAGE_SITES_PER_DAY_HIST, 
        date_col="du_day", 
        dimensions=["market_zone" , "governorate"],
        metrics_map={"total_mb": "Total DATA USAGE", "total_5g_mb": "5G DATA USAGE", "unq_subs": "Users"},
        thresholds=[2, 4, 8, 15] # سلم أورانج كاش مخصص وحساس أكتر
    )


    render_alerts_center_ui(df)






def OUG_VOICE_tab_alerts():

    df = get_dynamic_alerts(
        df_raw=OUG_VOICE_SITES_PER_DAY_HIST, 
        date_col="vu_day", 
        dimensions=["market_zone" , "governorate"],
        metrics_map={"total_oug_mous": "Minutes", "total_oug_cnts": "Calls", "unq_subs": "Users"},
        thresholds=[2, 4, 8, 15] # سلم أورانج كاش مخصص وحساس أكتر
    )


    render_alerts_center_ui(df)















#======    ALERTS_contribution


def RCH_ALERTS_contribution():
    
        
        # 🧠 هنا بنعرف الخريطة اللي بتربط عواميد الـ Raw بعواميد الـ Global الحقيقية اللي في الصورة
        recharge_global_mapping = {
            "UNQ_SUBS": "DAILY_UNQ_SUBS",       # بيربط اليوزرز
            "TRX_COUNTS": "DAILY_TRX_COUNTS",   # بيربط الترانزاكشنز
            "RCH_AMT": "DAILY_TRX_AMOUNTS"      # بيربط المبالغ
        }
        
        render_contribution_section(
            df_raw=RCH_PER_DAY_HIST, 
            df_global=rch_daily_summary, 
            date_col="RCH_DAY", 
            dimensions=["RCH_TYPE", "recharge_type_description", "RCH_HOUR_TIERS"], 
            metrics_map={"UNQ_SUBS": "Subscribers", "TRX_COUNTS": "Transactions", "RCH_AMT": "Amount"},
            global_metrics_map=recharge_global_mapping, # البارامتر الذكي الجديد المانع للأخطاء!
            thresholds=[5, 15, 30],
            selected_day=selected_day,
            prefix="RCH"
        )





# def OC_ALERTS_contribution():
    
#     # 🕵️‍♂️ اكتب السطرين دول مؤقتاً عشان تقفش أسامي العواميد الحقيقية
#     st.write("Real Columns in Orange Cash RAW:", list(OC_SERVICES_PER_DAY_HIST.columns))
#     st.write("Real Columns in Orange Cash GLOBAL:", list(OC_PER_DAY_HIST.columns))
    
    





def OC_ALERTS_contribution():
    
    # 🧠 الماب الذكي: بما إن أسامي الـ RAW والـ GLOBAL متطابقة، الـ Key والـ Value هيبقوا زي بعض بالظبط!
    recharge_global_mapping = {
        "total_unq_subs": "total_unq_subs",       # بيربط اليوزرز
        "total_oc_trx_cnts": "total_oc_trx_cnts",   # بيربط الترانزاكشنز
        "total_oc_trx_amts": "total_oc_trx_amts"    # بيربط المبالغ (استخدمنا total عشان دي الإجمالي)
    }
    
    render_contribution_section(
        df_raw=OC_SERVICES_PER_DAY_HIST, 
        df_global=oc_daily_summary, 
        date_col="oc_usage_day", 
        dimensions=["service_group"], 
        # 🚨 الـ Keys هنا بقت مطابقة لأعمدة الـ RAW الحقيقية (total_...) عشان الباندا تفرح ومتقفش
        metrics_map={
            "total_unq_subs": "Subscribers", 
            "total_oc_trx_cnts": "Transactions", 
            "total_oc_trx_amts": "Amount"
        },
        global_metrics_map=recharge_global_mapping, 
        thresholds=[5, 15, 30],
        selected_day=selected_day,
        prefix="OC"
    )









def DATA_USAGE_ALERTS_contribution():
    
    # 🧠 الماب الذكي: بما إن أسامي الـ RAW والـ GLOBAL متطابقة، الـ Key والـ Value هيبقوا زي بعض بالظبط!
    recharge_global_mapping = {
        "unq_subs": "total_unq_subs",       # بيربط اليوزرز
        "total_mb": "total_mb"   # بيربط الترانزاكشنز
        # "total_oc_trx_amts": "total_oc_trx_amts"    # بيربط المبالغ (استخدمنا total عشان دي الإجمالي)
    }
    
    render_contribution_section(
        df_raw=DATA_USAGE_SITES_PER_DAY_HIST, 
        df_global=data_daily_summary, 
        date_col="du_day", 
        dimensions=["market_zone" , "governorate"],
        # 🚨 الـ Keys هنا بقت مطابقة لأعمدة الـ RAW الحقيقية (total_...) عشان الباندا تفرح ومتقفش
        metrics_map={
            "unq_subs": "Subscribers", 
            "total_mb": "DU MB"
            # "total_oc_trx_amts": "Amount"
        },
        global_metrics_map=recharge_global_mapping, 
        thresholds=[5, 15, 30],
        selected_day=selected_day,
        prefix="DATA_USAGE"
    )









def OUG_VOICE_ALERTS_contribution():
    
    # 🧠 الماب الذكي: بما إن أسامي الـ RAW والـ GLOBAL متطابقة، الـ Key والـ Value هيبقوا زي بعض بالظبط!
    recharge_global_mapping = {
        "unq_subs"      : "total_unq_subs",       # بيربط اليوزرز
        "total_oug_cnts": "total_oug_cnts",   # بيربط الترانزاكشنز
        "total_oug_mous": "total_oug_mous"    # بيربط المبالغ (استخدمنا total عشان دي الإجمالي)
    }
    
    render_contribution_section(
        df_raw=OUG_VOICE_SITES_PER_DAY_HIST, 
        df_global=voice_daily_summary, 
        date_col="vu_day", 
        dimensions=["market_zone" , "governorate"], 
        # 🚨 الـ Keys هنا بقت مطابقة لأعمدة الـ RAW الحقيقية (total_...) عشان الباندا تفرح ومتقفش
        metrics_map={
            "unq_subs"      : "Subscribers", 
            "total_oug_cnts": "CALLS", 
            "total_oug_mous": "Minutes"
        },
        global_metrics_map=recharge_global_mapping, 
        thresholds=[5, 15, 30],
        selected_day=selected_day,
        prefix="OUG_VOICE"
    )














#==========================
# IBRO
#==========================


def RCH_IBRO_tab():

    f_tab_dynamic_dashboard(
        tab_title="🚀 RCH IBRO Behavioral Data Center",
        df_source = RCH_IBRO_PER_DAY_HIST,
        dimensions=['mode', 'tariff_sub_category_2', 'no_of_multisim'],
        prefix="ibro_tab",
        waterfall_dim="market_zone",
        mirror_dim="governorate"
    )





def OC_IBRO_tab():

    f_tab_dynamic_dashboard(
        tab_title="🚀 WALLET IBRO Behavioral Data Center",
        df_source = OC_IBRO_PER_DAY_HIST,
        dimensions=['mode', 'tariff_sub_category_2', 'no_of_multisim'],
        prefix="ibro_tab",
        waterfall_dim="market_zone",
        mirror_dim="governorate"
    )








def DATA_USAGE_IBRO_tab():

    f_tab_dynamic_dashboard(
        tab_title="🚀 DATA_USAGE IBRO Behavioral Data Center",
        df_source = DATA_USAGE_IBRO_PER_DAY_HIST,
        dimensions=['mode', 'tariff_sub_category_2', 'no_of_multisim'],
        prefix="ibro_tab",
        waterfall_dim="market_zone",
        mirror_dim="governorate"
    )








def OUG_VOICE_IBRO_tab():

    f_tab_dynamic_dashboard(
        tab_title="🚀 OUG_VOICE IBRO Behavioral Data Center",
        df_source = OUG_VOICE_IBRO_PER_DAY_HIST,
        dimensions=['mode', 'tariff_sub_category_2', 'no_of_multisim'],
        prefix="ibro_tab",
        waterfall_dim="market_zone",
        mirror_dim="governorate"
    )














#=============================
# Network
#==============================


# هذا الكود يوضع في الـ RCH_SITES_TAB أو المكان المخصص للتاب في تطبيقك
# def RCH_SITES_TAB(global_selected_date):
#     df_net = load_master_network_data()
#     target_day = pd.to_datetime(global_selected_date)
    
#     # الإعدادات
#     dims = ['market_zone', 'governorate']
#     metrics = {
#         'unq_subs': 'Subs', 
#         'total_rch_cnt': 'Trx', 
#         'total_rch_amt': 'Amt'
#     }
    
#     # الاستدعاء
#     f_tab_network_dynamic(df_net, dims, target_day, metrics)




def RCH_SITES_TAB():

    f_tab_network("RCH", selected_day)



def OC_SITES_TAB():

    f_tab_network("OC", selected_day)




def DATA_USAGE_SITES_TAB():

    f_tab_network("DATA_USAGE", selected_day)



        
def OUG_VOICE_SITES_TAB():

    f_tab_network("OUG_VOICE", selected_day)



    



















# =========================================================
# 🚀 MAIN MONITORING MODULES
# =========================================================

main_tab_welcome ,main_tab_recharge, main_tab_data, main_tab_voice, main_tab_oc = st.tabs([
    "Monitoring Products",
    "🔋 Recharge Monitoring",
    "📶 Data Monitoring",
    "📞 Voice Monitoring",
    "💰 Orange Cash Monitoring"
])







# =========================================================
# 🔋 main_tab_welcome
# =========================================================




with main_tab_welcome:

    st.info("Welcome to Monitoring Product ")

    st.info("Select Any Product To view details ")








# =========================================================
# 🔋 RECHARGE TAB
# =========================================================




with main_tab_recharge:

    st.markdown("<br>", unsafe_allow_html=True)



    st.markdown('<div class="main-title">📊 Recharge Behavior Monitoring</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)


    # 1. Summary Cards
    prev_day = selected_day - timedelta(days=1)
    curr_row = rch_daily_summary[rch_daily_summary["RCH_DAY"] == selected_day]
    prev_row = rch_daily_summary[rch_daily_summary["RCH_DAY"] == prev_day]


    # 🛡️ حارس البوابة الذكي (الفرملة المبكرة):
    if curr_row.empty or prev_row.empty:
        # لو أي يوم فيهم فاضي، هيطلع الرسالة ويقفل الأبلكيشن في ثانية
        st.warning(f"⚠️ No data available for the selected date: **{selected_day.date()}**. Please check your data source or select another day.")
        st.stop() # 🪄 الفرملة السحرية.. الكود اللي تحت مستحيل يشتغل ومستحيل يضرب إيرور!

    RCH_kpis_config = [
        ("Recharge Users", "DAILY_UNQ_SUBS"),
        ("Transactions", "DAILY_TRX_COUNTS"),
        ("Recharge Amount", "DAILY_TRX_AMOUNTS"),
        ("Avg Recharge", "avg_recharge")
    ]

    if not curr_row.empty and not prev_row.empty:
        cols = st.columns(4)
        for i, (name, col_name) in enumerate(RCH_kpis_config):
            curr_val = curr_row[col_name].values[0]
            p_val = prev_row[col_name].values[0]
            diff = ((curr_val - p_val) / p_val) * 100
            
            status_label, status_color = get_status_details(diff)
            delta_class = "green" if diff >= 0 else "red"
            symbol = "+" if diff >= 0 else ""
            
            with cols[i]:
                st.markdown(f"""
                <div class="summary-card" style="border-left: 6px solid {status_color};">
                    <div class="summary-label">{name}</div>
                    <div class="summary-value">{round(curr_val, 1):,}</div>
                    <div class="summary-delta {delta_class}">{symbol}{round(diff, 1)}% vs D-1</div>
                    <div class="status-tag" style="background-color: {status_color};">{status_label}</div>
                </div>
                """, unsafe_allow_html=True)

    st.write("") 






    tab_overall, tab_alerts, tab_alerts_v2 , tab_ibro , tab_network = st.tabs(["🌐 Overall View", "🔔 Alerts Center", "🎯 Contribution Alerts (V2)" , "🚀 IBRO" , "📡 Network Performance"])



    with tab_overall:
        # 🔑 لو أدمن.. رن الفانكشن القديمة علطول ومفيش أيرورز هتظهر
        if st.session_state.get("user_role") == "admin":
            RCH_tab_overall()
            
        # 🚫 العكس: لو مش أدمن (نتورك يوزر مثلاً).. اظهر له الأيرور بس والفانكشن مش هترن
        if st.session_state.get("user_role") != "admin":
            st.error("❌ Wrong Password / No Permission to view this tab.")


    with tab_alerts:
        # 🔑 لو أدمن.. رن الفانكشن القديمة علطول ومفيش أيرورز هتظهر
        if st.session_state.get("user_role") == "admin":
            
           #render_alerts_center_ui(df_rch_alerts)
           RCH_tab_alerts() 

            
        # 🚫 العكس: لو مش أدمن (نتورك يوزر مثلاً).. اظهر له الأيرور بس والفانكشن مش هترن
        if st.session_state.get("user_role") != "admin":
            st.error("❌ Wrong Password / No Permission to view this tab.")



    with tab_alerts_v2:
        # 🔑 لو أدمن.. رن الفانكشن القديمة علطول ومفيش أيرورز هتظهر
        if st.session_state.get("user_role") == "admin":
            
            RCH_ALERTS_contribution()
            
            
        # 🚫 العكس: لو مش أدمن (نتورك يوزر مثلاً).. اظهر له الأيرور بس والفانكشن مش هترن
        if st.session_state.get("user_role") != "admin":
            st.error("❌ Wrong Password / No Permission to view this tab.")



    with tab_ibro:
        # 🔑 لو أدمن.. رن الفانكشن القديمة علطول ومفيش أيرورز هتظهر
        if st.session_state.get("user_role") == "admin":
        
            RCH_IBRO_tab()
            
            
        # 🚫 العكس: لو مش أدمن (نتورك يوزر مثلاً).. اظهر له الأيرور بس والفانكشن مش هترن
        if st.session_state.get("user_role") != "admin":
            st.error("❌ Wrong Password / No Permission to view this tab.")
        
        

    with tab_network:
        
        RCH_SITES_TAB()
















# =========================================================
# 📶 DATA TAB
# =========================================================

# with main_tab_data:
#     st.info("📶 Data Monitoring Module - Coming Soon")




with main_tab_data:

    st.markdown("<br>", unsafe_allow_html=True)



    st.markdown('<div class="main-title">📊 Data Usage Monitoring Dashboard</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

 
    # 1. Summary Cards
    prev_day = selected_day - timedelta(days=1)
    curr_row = data_daily_summary[data_daily_summary["data_usage_day"] == selected_day]
    prev_row = data_daily_summary[data_daily_summary["data_usage_day"] == prev_day]


    # 🛡️ حارس البوابة الذكي (الفرملة المبكرة):
    if curr_row.empty or prev_row.empty:
        # لو أي يوم فيهم فاضي، هيطلع الرسالة ويقفل الأبلكيشن في ثانية
        st.warning(f"⚠️ No data available for the selected date: **{selected_day.date()}**. Please check your data source or select another day.")
        st.stop() # 🪄 الفرملة السحرية.. الكود اللي تحت مستحيل يشتغل ومستحيل يضرب إيرور!

    DATA_kpis_config = [
        ("Total Active Subscribers" , "total_unq_subs"),
        ("Total MB"                 , "total_mb"),
        ("Total GB"                 , "total_gb"),
        ("Avg MB / SUB"             , "avg_mb")
    ]

    if not curr_row.empty and not prev_row.empty:
        cols = st.columns(4)
        for i, (name, col_name) in enumerate(DATA_kpis_config):
            curr_val = curr_row[col_name].values[0]
            p_val = prev_row[col_name].values[0]
            diff = ((curr_val - p_val) / p_val) * 100
            
            status_label, status_color = get_status_details(diff)
            delta_class = "green" if diff >= 0 else "red"
            symbol = "+" if diff >= 0 else ""
            
            with cols[i]:
                st.markdown(f"""
                <div class="summary-card" style="border-left: 6px solid {status_color};">
                    <div class="summary-label">{name}</div>
                    <div class="summary-value">{round(curr_val, 1):,}</div>
                    <div class="summary-delta {delta_class}">{symbol}{round(diff, 1)}% vs D-1</div>
                    <div class="status-tag" style="background-color: {status_color};">{status_label}</div>
                </div>
                """, unsafe_allow_html=True)

    st.write("") 






    tab_overall, tab_alerts, tab_alerts_v2 , tab_ibro , tab_network = st.tabs(["🌐 Overall View", "🔔 Alerts Center", "🎯 Contribution Alerts (V2)" , "🚀 IBRO" , "📡 Network Performance"])



    with tab_overall:
        # 🔑 لو أدمن.. رن الفانكشن القديمة علطول ومفيش أيرورز هتظهر
        if st.session_state.get("user_role") == "admin":
            DATA_USAGE_tab_overall()
            
        # 🚫 العكس: لو مش أدمن (نتورك يوزر مثلاً).. اظهر له الأيرور بس والفانكشن مش هترن
        if st.session_state.get("user_role") != "admin":
            st.error("❌ Wrong Password / No Permission to view this tab.")


    with tab_alerts:
        # 🔑 لو أدمن.. رن الفانكشن القديمة علطول ومفيش أيرورز هتظهر
        if st.session_state.get("user_role") == "admin":
            
           #render_alerts_center_ui(df_rch_alerts)
           DATA_USAGE_tab_alerts() 
        #    st.info("💰 DATA USAGE Monitoring Module - Coming Soon") 

            
        # 🚫 العكس: لو مش أدمن (نتورك يوزر مثلاً).. اظهر له الأيرور بس والفانكشن مش هترن
        if st.session_state.get("user_role") != "admin":
            st.error("❌ Wrong Password / No Permission to view this tab.")



    with tab_alerts_v2:
        # 🔑 لو أدمن.. رن الفانكشن القديمة علطول ومفيش أيرورز هتظهر
        if st.session_state.get("user_role") == "admin":
            
            DATA_USAGE_ALERTS_contribution()
            # st.info("💰 DATA USAGE Monitoring Module - Coming Soon") 
            
            
        # 🚫 العكس: لو مش أدمن (نتورك يوزر مثلاً).. اظهر له الأيرور بس والفانكشن مش هترن
        if st.session_state.get("user_role") != "admin":
            st.error("❌ Wrong Password / No Permission to view this tab.")



    with tab_ibro:
        # 🔑 لو أدمن.. رن الفانكشن القديمة علطول ومفيش أيرورز هتظهر
        if st.session_state.get("user_role") == "admin":
        
            DATA_USAGE_IBRO_tab()
            # st.info("💰 DATA USAGE Monitoring Module - Coming Soon") 
            
            
        # 🚫 العكس: لو مش أدمن (نتورك يوزر مثلاً).. اظهر له الأيرور بس والفانكشن مش هترن
        if st.session_state.get("user_role") != "admin":
            st.error("❌ Wrong Password / No Permission to view this tab.")
        
        

    with tab_network:
        
        DATA_USAGE_SITES_TAB() 
        # st.info("💰 DATA USAGE Monitoring Module - Coming Soon") 





























# =========================================================
# 📞 VOICE TAB
# =========================================================

with main_tab_voice:
    st.info("📞 Voice Monitoring Module - Coming Soon")    


































# =========================================================
# 💰 ORANGE CASH TAB
# =========================================================


with main_tab_oc:

    st.markdown("<br>", unsafe_allow_html=True)



    st.markdown('<div class="main-title">📊🍊 Orange Cash Monitoring Dashboard</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

 
    # 1. Summary Cards
    prev_day = selected_day - timedelta(days=1)
    curr_row = oc_daily_summary[oc_daily_summary["oc_usage_day"] == selected_day]
    prev_row = oc_daily_summary[oc_daily_summary["oc_usage_day"] == prev_day]


    # 🛡️ حارس البوابة الذكي (الفرملة المبكرة):
    if curr_row.empty or prev_row.empty:
        # لو أي يوم فيهم فاضي، هيطلع الرسالة ويقفل الأبلكيشن في ثانية
        st.warning(f"⚠️ No data available for the selected date: **{selected_day.date()}**. Please check your data source or select another day.")
        st.stop() # 🪄 الفرملة السحرية.. الكود اللي تحت مستحيل يشتغل ومستحيل يضرب إيرور!

    OC_kpis_config = [
        ("Total Active Subscribers"      , "total_unq_subs"),
        ("Total Transactions Count"      , "total_oc_trx_cnts"),
        ("Total Transaction Volume (EGP)", "total_oc_trx_amts"),
        ("Avg Transaction Volume (EGP)"  , "avg_oc_amt")
    ]

    if not curr_row.empty and not prev_row.empty:
        cols = st.columns(4)
        for i, (name, col_name) in enumerate(OC_kpis_config):
            curr_val = curr_row[col_name].values[0]
            p_val = prev_row[col_name].values[0]
            diff = ((curr_val - p_val) / p_val) * 100
            
            status_label, status_color = get_status_details(diff)
            delta_class = "green" if diff >= 0 else "red"
            symbol = "+" if diff >= 0 else ""
            
            with cols[i]:
                st.markdown(f"""
                <div class="summary-card" style="border-left: 6px solid {status_color};">
                    <div class="summary-label">{name}</div>
                    <div class="summary-value">{round(curr_val, 1):,}</div>
                    <div class="summary-delta {delta_class}">{symbol}{round(diff, 1)}% vs D-1</div>
                    <div class="status-tag" style="background-color: {status_color};">{status_label}</div>
                </div>
                """, unsafe_allow_html=True)

    st.write("") 






    tab_overall, tab_alerts, tab_alerts_v2 , tab_ibro , tab_network = st.tabs(["🌐 Overall View", "🔔 Alerts Center", "🎯 Contribution Alerts (V2)" , "🚀 IBRO" , "📡 Network Performance"])



    with tab_overall:
        # 🔑 لو أدمن.. رن الفانكشن القديمة علطول ومفيش أيرورز هتظهر
        if st.session_state.get("user_role") == "admin":
            OC_tab_overall()
            
        # 🚫 العكس: لو مش أدمن (نتورك يوزر مثلاً).. اظهر له الأيرور بس والفانكشن مش هترن
        if st.session_state.get("user_role") != "admin":
            st.error("❌ Wrong Password / No Permission to view this tab.")


    with tab_alerts:
        # 🔑 لو أدمن.. رن الفانكشن القديمة علطول ومفيش أيرورز هتظهر
        if st.session_state.get("user_role") == "admin":
            
           #render_alerts_center_ui(df_rch_alerts)
           OC_tab_alerts() 

            
        # 🚫 العكس: لو مش أدمن (نتورك يوزر مثلاً).. اظهر له الأيرور بس والفانكشن مش هترن
        if st.session_state.get("user_role") != "admin":
            st.error("❌ Wrong Password / No Permission to view this tab.")



    with tab_alerts_v2:
        # 🔑 لو أدمن.. رن الفانكشن القديمة علطول ومفيش أيرورز هتظهر
        if st.session_state.get("user_role") == "admin":
            
            OC_ALERTS_contribution()
            
            
        # 🚫 العكس: لو مش أدمن (نتورك يوزر مثلاً).. اظهر له الأيرور بس والفانكشن مش هترن
        if st.session_state.get("user_role") != "admin":
            st.error("❌ Wrong Password / No Permission to view this tab.")



    with tab_ibro:
        # 🔑 لو أدمن.. رن الفانكشن القديمة علطول ومفيش أيرورز هتظهر
        if st.session_state.get("user_role") == "admin":
        
            #OC_IBRO_tab()
            st.info("💰 Orange Cash Monitoring Module - Coming Soon")
            
            
        # 🚫 العكس: لو مش أدمن (نتورك يوزر مثلاً).. اظهر له الأيرور بس والفانكشن مش هترن
        if st.session_state.get("user_role") != "admin":
            st.error("❌ Wrong Password / No Permission to view this tab.")
        
        

    with tab_network:
        
        #OC_SITES_TAB() 
        st.info("💰 Orange Cash Monitoring Module - Coming Soon") 
