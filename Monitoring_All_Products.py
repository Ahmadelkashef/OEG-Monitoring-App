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






#===========RCH ALERTS


# =========================================================
# 3. ALERTS LOGIC FUNCTIONS
# =========================================================


def get_alerts_logic(df_raw, target_date):
    prev_date = target_date - timedelta(days=1)
    curr = df_raw[df_raw["RCH_DAY"] == target_date]
    prev = df_raw[df_raw["RCH_DAY"] == prev_date]
    
    if curr.empty or prev.empty: return pd.DataFrame()

    # تعديل: تعريف كافة الاحتمالات (فردي، ثنائي، ثلاثي)
    combinations = [
        ["RCH_TYPE"], ["recharge_type_description"], ["RCH_HOUR_TIERS"],
        ["RCH_TYPE", "recharge_type_description"],
        ["RCH_TYPE", "RCH_HOUR_TIERS"],
        ["recharge_type_description", "RCH_HOUR_TIERS"],
        ["RCH_TYPE", "recharge_type_description", "RCH_HOUR_TIERS"]
    ]
    
    m_map = {"RCH_AMT": "Amount", "TRX_COUNTS": "Transactions", "UNQ_SUBS": "Subscribers"}
    results = []

    for cols in combinations:
        curr_g = curr.groupby(cols)[["TRX_COUNTS", "RCH_AMT", "UNQ_SUBS"]].sum().reset_index()
        prev_g = prev.groupby(cols)[["TRX_COUNTS", "RCH_AMT", "UNQ_SUBS"]].sum().reset_index()
        
        merged = curr_g.merge(prev_g, on=cols, suffixes=('_c', '_p'))
        
        for _, row in merged.iterrows():
            segment_name = " | ".join([str(row[c]) for c in cols])
            for col_key, name in m_map.items():
                p_val = row[f"{col_key}_p"]
                c_val = row[f"{col_key}_c"]
                if p_val > 0:
                    growth = ((c_val - p_val) / p_val) * 100
                    abs_g = abs(growth)
                    
                    if abs_g >= 3: # الحد الأدنى للظهور
                        # تطبيق سلم التنبيهات الجديد الخاص بك
                        if abs_g < 5: level = "Normal"
                        elif 5 <= abs_g < 10: level = "Watch"
                        elif 10 <= abs_g < 20: level = "Warning"
                        else: level = "Critical"
                        
                        results.append({
                            "segment": segment_name,
                            "metric": name, 
                            "growth": round(growth, 1),
                            "current_val": round(c_val, 1),
                            "previous_val": round(p_val, 1),
                            "level": level, 
                            "direction": "Drop" if growth < 0 else "Up"
                        })
    return pd.DataFrame(results)



# =========================================================
# 3. UI RENDERERS ALERTS
# =========================================================

def show_alerts(data, is_drop):
    # إضافة Normal للتبويبات حسب السلم الجديد
    levels = ["Critical", "Warning", "Watch", "Normal"]
    tabs = st.tabs([f"{l} ({len(data[data['level']==l])})" for l in levels])
    
    for i, l in enumerate(levels):
        with tabs[i]:
            subset = data[data["level"] == l]
            if subset.empty: 
                st.info(f"No {l} alerts found.")
            else:
                for _, r in subset.iterrows():
                    color = "#DA3633" if is_drop else "#238636"
                    arrow = "▼" if is_drop else "▲"
                    
                    st.markdown(f"""
                    <div class="alert-card {'drop-card' if is_drop else 'up-card'}">
                        <span style="float:right; color:{color}; font-weight:800; font-size:18px;">
                            {arrow} {abs(r['growth'])}%
                        </span>
                        <div style="font-weight:700; margin-bottom:5px;">{r['segment']}</div>
                        <div style="font-size:13px; color:#8B949E; margin-bottom:8px;">
                            Current: <b>{r['current_val']:,}</b> | Previous: <b>{r['previous_val']:,}</b>
                        </div>
                        <span class="metric-tag">Metric: {r['metric']}</span>
                    </div>
                    """, unsafe_allow_html=True)








# =========================================================
# 3. contribution_alerts LOGIC FUNCTIONS
# =========================================================


def get_alerts_logic_v2(df_raw, target_date, comp_mode="vs Yesterday (D-1)"):
    """
    الدالة العبقرية الشاملة (V3) لدعم المقارنة اليومية، الأسبوعية، 
    ومقارنة المراحل الشهرية الذكية (Phase-to-Phase Matching) بناءً على اسم اليوم ومرحلة الشهر.
    """
    # جلب دالة تحديد المرحلة من الكود الأصلي للتأكد من التطابق
    def get_phase(dt):
        day = dt.day
        if 1 <= day <= 7: return "Salary Period"
        elif 8 <= day <= 15: return "Mid-Month"
        elif 16 <= day <= 22: return "Late-Mid"
        else: return "End-Month"

    # تحديد يوم المقارنة (prev_date) بناءً على الفلتر المختار
    if comp_mode == "vs Yesterday (D-1)":
        prev_date = target_date - timedelta(days=1)
        
    elif comp_mode == "vs Same Day Last Week (D-7)":
        prev_date = target_date - timedelta(days=7)
        
    else:  # الخيار الذكي: vs Same Weekday & Month Phase (Smart Match)
        target_weekday = target_date.weekday() # معرفة اسم اليوم (خميس، جمعة...)
        target_phase = get_phase(target_date) # معرفة مرحلة الشهر
        
        # اللف لورا في الزمن بزيادة 7 أيام في كل خطوة للبحث عن نفس اليوم ونفس المرحلة
        found = False
        weeks_back = 1
        # الأمان: مش هنرجع أكتر من 6 أسابيع لورا عشان الأداء
        while weeks_back <= 6:
            check_date = target_date - timedelta(days=7 * weeks_back)
            if check_date.weekday() == target_weekday and get_phase(check_date) == target_phase:
                prev_date = check_date
                found = True
                break
            weeks_back += 1
            
        # حماية: لو ملعقش يوم يطابق (نادر الحدوث)، يرجع أوتوماتيك للشهر اللي قبله بـ 28 يوم
        if not found:
            prev_date = target_date - timedelta(days=28)

    # تصفية البيانات لليوم الحالي ويوم المقارنة المستخرج
    curr = df_raw[df_raw["RCH_DAY"] == target_date]
    prev = df_raw[df_raw["RCH_DAY"] == prev_date]
    
    if curr.empty or prev.empty: return pd.DataFrame()

    # حساب التغيير المطلق الكلي على مستوى الشبكة بالكامل (النهاردة ضد يوم المقارنة الذكي)
    global_curr = df_daily[df_daily["RCH_DAY"] == target_date]
    global_prev = df_daily[df_daily["RCH_DAY"] == prev_date]
    
    if global_curr.empty or global_prev.empty: return pd.DataFrame()
    
    global_diffs = {
        "Subscribers": global_curr["DAILY_UNQ_SUBS"].values[0] - global_prev["DAILY_UNQ_SUBS"].values[0],
        "Transactions": global_curr["DAILY_TRX_COUNTS"].values[0] - global_prev["DAILY_TRX_COUNTS"].values[0],
        "Amount": global_curr["DAILY_TRX_AMOUNTS"].values[0] - global_prev["DAILY_TRX_AMOUNTS"].values[0],
        "Avg Recharge": global_curr["avg_recharge"].values[0] - global_prev["avg_recharge"].values[0]
    }

    # الـ 7 احتمالات والتباديل والتوافيق للأبعاد الثلاثة
    combinations = [
        ["RCH_TYPE"], ["recharge_type_description"], ["RCH_HOUR_TIERS"],
        ["RCH_TYPE", "recharge_type_description"],
        ["RCH_TYPE", "RCH_HOUR_TIERS"],
        ["recharge_type_description", "RCH_HOUR_TIERS"],
        ["RCH_TYPE", "recharge_type_description", "RCH_HOUR_TIERS"]
    ]
    
    m_map = {"RCH_AMT": "Amount", "TRX_COUNTS": "Transactions", "UNQ_SUBS": "Subscribers"}
    results = []

    for cols in combinations:
        curr_g = curr.groupby(cols)[["TRX_COUNTS", "RCH_AMT", "UNQ_SUBS"]].sum().reset_index()
        prev_g = prev.groupby(cols)[["TRX_COUNTS", "RCH_AMT", "UNQ_SUBS"]].sum().reset_index()
        
        merged = curr_g.merge(prev_g, on=cols, suffixes=('_c', '_p'))
        
        for _, row in merged.iterrows():
            segment_name = " | ".join([str(row[c]) for c in cols])
            
            for col_key, name in m_map.items():
                p_val = row[f"{col_key}_p"]
                c_val = row[f"{col_key}_c"]
                
                seg_diff = c_val - p_val
                tot_diff = global_diffs[name]
                
                if tot_diff == 0: continue
                
                contribution_pct = round((seg_diff / abs(tot_diff)) * 100, 1)
                
                if abs(contribution_pct) >= 5.0:
                    if abs(contribution_pct) < 15.0:
                        level = "Minor Contributor"
                    elif 15.0 <= abs(contribution_pct) < 30.0:
                        level = "Major Contributor"
                    else:
                        level = "Primary Driver"
                    
                    segment_direction = "Increase" if seg_diff > 0 else "Decline"
                    
                    results.append({
                        "segment": segment_name,
                        "metric": name, 
                        "contribution": abs(contribution_pct),
                        "seg_diff": round(seg_diff, 1),
                        "tot_diff": round(tot_diff, 1),
                        "current_val": round(c_val, 1),
                        "previous_val": round(p_val, 1),
                        "level": level, 
                        "network_direction": segment_direction,
                        "compared_to_date": prev_date.strftime('%Y-%m-%d') # بنسجل التاريخ اللي قارن بيه عشان نظهره شياكة لليوزر
                    })
                        
    return pd.DataFrame(results)




# =========================================================
# 3. UI RENDERERS contribution_alerts
# =========================================================


def show_contribution_alerts(data):
    """
    دالة الـ UI المخصصة لعرض كروت المساهمة بشكل أنيق ومنظم حسب السلم الجديد
    """
    levels = ["Primary Driver", "Major Contributor", "Minor Contributor"]
    tabs = st.tabs([f"🎯 {l} ({len(data[data['level']==l])})" for l in levels])
    
    for i, l in enumerate(levels):
        with tabs[i]:
            subset = data[data["level"] == l]
            if subset.empty: 
                st.info(f"No {l} found for this view.")
            else:
                for _, r in subset.iterrows():
                    # تحديد الألوان بناءً على السلم والتاغات الجديدة
                    if l == "Primary Driver":
                        color = "#DA3633" if r['network_direction'] == "Decline" else "#238636"
                        bg_style = "border-left: 6px solid " + color + ";"
                    elif l == "Major Contributor":
                        color = "#E36209"
                        bg_style = "border-left: 4px solid #E36209;"
                    else:
                        color = "#F2CC60"
                        bg_style = "border-left: 4px solid #F2CC60;"
                        
                    arrow = "▼" if r['seg_diff'] < 0 else "▲"
                    
                    st.markdown(f"""
                    <div class="alert-card" style="{bg_style}">
                        <span style="float:right; color:{color}; font-weight:800; font-size:18px;">
                            Share: {r['contribution']}%
                        </span>
                        <div style="font-weight:700; font-size:15px; margin-bottom:5px;">{r['segment']}</div>
                        <div style="font-size:13px; color:#8B949E; margin-bottom:8px;">
                            Segment Move: <b>{arrow} {abs(r['seg_diff']):,}</b> &nbsp;|&nbsp; Total Network Move: <b>{r['tot_diff']:,}</b>
                        </div>
                        <span class="metric-tag" style="color:white; background-color:#30363D;">Metric: {r['metric']}</span>
                        <span class="metric-tag" style="color:{color}; font-weight:bold;">{l}</span>
                    </div>
                    """, unsafe_allow_html=True)









def process_behavioral_data_v2(df_day_filtered, selected_mode, selected_segment, selected_multisim):
    """
    دالة مطورة لفلترة داتا IBRO بناءً على المود، الشريحة، والـ Multi-Sim وحساب المؤشرات
    """
    # حماية: لو الداتا الأساسية فاضية من الأول
    if df_day_filtered.empty:
        return 0, 0, 0, "N/A", pd.DataFrame()

    # 1. فلترة بناءً على المود (7_DAYS or 14_DAYS)
    df_res = df_day_filtered[df_day_filtered['mode'] == selected_mode]
    
    # 2. فلترة بناءً على الشريحة لو مش مختار الكل
    if selected_segment != "All Segments":
        df_res = df_res[df_res['tariff_sub_category_2'] == selected_segment]
        
    # 3. فلترة بناءً على الـ Multi-Sim
    if selected_multisim != "All Multi-Sim Status":
        df_res = df_res[df_res['no_of_multisim'] == selected_multisim]
        
    # لو الداتا طلعت فاضية بعد الفلاتر دي كلها
    if df_res.empty:
        return 0, 0, 0, "N/A", pd.DataFrame()
        
    # 4. حساب المؤشرات الرئيسية (KPIs)
    inflow_subs = df_res[df_res['movement_type'] == 'INFLOW']['unq_subs'].sum()
    outflow_subs = df_res[df_res['movement_type'] == 'OUTFLOW']['unq_subs'].sum()
    net_change = inflow_subs - outflow_subs
    
    # 5. معرفة أكثر محافظة تأثراً
    gov_summary = df_res.groupby('governorate')['unq_subs'].sum().reset_index()
    if not gov_summary.empty:
        top_gov = gov_summary.sort_values(by='unq_subs', ascending=False).iloc[0]['governorate']
    else:
        top_gov = "N/A"
        
    return int(inflow_subs), int(outflow_subs), int(net_change), top_gov, df_res










#========== site logic

#=========== ABS RANKING LAST


#=========GPT RANKING BY ABS

def get_top_10_analysis(df_net, target_day, past_dates_list, selected_zone, selected_gov):
    
    all_needed_dates = [target_day] + list(past_dates_list)
    df_filtered = df_net[df_net['rch_day'].isin(all_needed_dates)].copy()

    if selected_zone != "All":
        df_filtered = df_filtered[df_filtered['market_zone'] == selected_zone]
    if selected_gov != "All":
        df_filtered = df_filtered[df_filtered['governorate'] == selected_gov]

    if df_filtered.empty:
        return None

    df_curr = df_filtered[df_filtered['rch_day'] == target_day]
    df_past = df_filtered[df_filtered['rch_day'].isin(past_dates_list)]

    if df_curr.empty or df_past.empty:
        return None

    # past benchmark
    past_avg = df_past.groupby('site_code')[['unq_subs', 'total_rch_cnt', 'total_rch_amt']].mean().reset_index()
    past_avg.columns = ['site_code', 'past_subs_avg', 'past_cnt_avg', 'past_amt_avg']

    merged = pd.merge(df_curr, past_avg, on='site_code', how='inner')
    if merged.empty:
        return None

    # =========================
    # ABSOLUTE IMPACT (NEW)
    # =========================
    merged['Subs Diff'] = merged['unq_subs'] - merged['past_subs_avg']
    merged['Count Diff'] = merged['total_rch_cnt'] - merged['past_cnt_avg']
    merged['Amount Diff'] = merged['total_rch_amt'] - merged['past_amt_avg']

    # =========================
    # PERCENTAGE CHANGE (DISPLAY ONLY)
    # =========================
    merged['Subs Change %'] = (merged['Subs Diff'] / merged['past_subs_avg']) * 100
    merged['Count Change %'] = (merged['Count Diff'] / merged['past_cnt_avg']) * 100
    merged['Amount Change %'] = (merged['Amount Diff'] / merged['past_amt_avg']) * 100

    merged = merged.replace([np.inf, -np.inf], np.nan).fillna(0)

    return merged[
        [
            'site_code',
            'Subs Diff', 'Subs Change %',
            'Count Diff', 'Count Change %',
            'Amount Diff', 'Amount Change %'
        ]
    ]


# def get_top_10_analysis(df_net, target_day, past_dates_list, selected_zone, selected_gov):
#     all_needed_dates = [target_day] + list(past_dates_list)
#     df_filtered = df_net[df_net['rch_day'].isin(all_needed_dates)].copy()

#     if selected_zone != "All":
#         df_filtered = df_filtered[df_filtered['market_zone'] == selected_zone]
#     if selected_gov != "All":
#         df_filtered = df_filtered[df_filtered['governorate'] == selected_gov]

#     if df_filtered.empty:
#         return None

#     df_curr = df_filtered[df_filtered['rch_day'] == target_day]
#     df_past = df_filtered[df_filtered['rch_day'].isin(past_dates_list)]

#     if df_curr.empty or df_past.empty:
#         return None

#     # past benchmark
#     past_avg = df_past.groupby('site_code')[['unq_subs', 'total_rch_cnt', 'total_rch_amt']].mean().reset_index()
#     past_avg.columns = ['site_code', 'past_subs_avg', 'past_cnt_avg', 'past_amt_avg']

#     merged = pd.merge(df_curr, past_avg, on='site_code', how='inner')
#     if merged.empty:
#         return None

#     # =========================
#     # ABSOLUTE IMPACT (NEW)
#     # =========================
#     merged['Subs Diff'] = merged['unq_subs'] - merged['past_subs_avg']
#     merged['Count Diff'] = merged['total_rch_cnt'] - merged['past_cnt_avg']
#     merged['Amount Diff'] = merged['total_rch_amt'] - merged['past_amt_avg']

#     # =========================
#     # PERCENTAGE CHANGE (DISPLAY ONLY)
#     # =========================
#     merged['Subs Change %'] = (merged['Subs Diff'] / merged['past_subs_avg']) * 100
#     merged['Count Change %'] = (merged['Count Diff'] / merged['past_cnt_avg']) * 100
#     merged['Amount Change %'] = (merged['Amount Diff'] / merged['past_amt_avg']) * 100

#     merged = merged.replace([np.inf, -np.inf], np.nan).fillna(0)

#     return merged[
#         [
#             'site_code',
#             'Subs Diff', 'Subs Change %',
#             'Count Diff', 'Count Change %',
#             'Amount Diff', 'Amount Change %'
#         ]
#     ]




#========= % RANKING

# ب) الفانكشن الحسابية للـ Top 10 (توضع برة خالص وتستقبل المتغيرات العامة)
# def get_top_10_analysis(df_net, target_day, past_dates_list, selected_zone, selected_gov):
#     # تجهيز لستة التواريخ المطلوبة للحسبة
#     all_needed_dates = [target_day] + list(past_dates_list)
#     df_filtered = df_net[df_net['rch_day'].isin(all_needed_dates)].copy()
    
#     # تطبيق الفلاتر المترابطة الممررة من التاب
#     if selected_zone != "All":
#         df_filtered = df_filtered[df_filtered['market_zone'] == selected_zone]
#     if selected_gov != "All":
#         df_filtered = df_filtered[df_filtered['governorate'] == selected_gov]
        
#     if df_filtered.empty:
#         return None

#     # فصل اليوم الحالي عن الأيام السابقة
#     df_curr = df_filtered[df_filtered['rch_day'] == target_day]
#     df_past = df_filtered[df_filtered['rch_day'].isin(past_dates_list)]
    
#     # إذا كان اليوم الحالي أو الماضي مش موجود في الداتا شياكة مش هيضرب أيرور
#     if df_curr.empty or df_past.empty:
#         return None

#     # حساب متوسط الفترة السابقة لكل سايت كود كـ Benchmark
#     past_avg = df_past.groupby('site_code')[['unq_subs', 'total_rch_cnt', 'total_rch_amt']].mean().reset_index()
#     past_avg.columns = ['site_code', 'past_subs_avg', 'past_cnt_avg', 'past_amt_avg']
    
#     # دمج اليوم الحالي مع المتوسطات السابقة
#     merged = pd.merge(df_curr, past_avg, on='site_code', how='inner')
#     if merged.empty:
#         return None

#     # معادلات الـ Delta % للـ 3 مقاييس
#     merged['Subs Change %'] = ((merged['unq_subs'] - merged['past_subs_avg']) / merged['past_subs_avg']) * 100
#     merged['Count Change %'] = ((merged['total_rch_cnt'] - merged['past_cnt_avg']) / merged['past_cnt_avg']) * 100
#     merged['Amount Change %'] = ((merged['total_rch_amt'] - merged['past_amt_avg']) / merged['past_amt_avg']) * 100
    
#     # شيل السطرين القدام واستبدلهم بدول:
#     merged = merged.replace([np.inf, -np.inf], np.nan)
#     merged = merged.fillna(0)
    
#     return merged[['site_code', 'Subs Change %', 'Count Change %', 'Amount Change %']]

    # تنظيف من قيم الما لانهاية والأصفار
    # merged.replace([np.inf, -np.inf], np.nan, inplace=True)
    # merged.fillna(0, inplace=True)
    
    # return merged[['site_code', 'Subs Change %', 'Count Change %', 'Amount Change %']]













#===============RCH MONITORING


# --- TAB: OVERALL VIEW ---


def f_tab_overall():
    st.write("") # Spacer
# 2. Detailed Cards
    for kpi_name, kpi_col in dict(kpis_config).items():
        current_val = curr_row[kpi_col].values[0]
    
        # =========================================================
        # الـتـعـديـل الـثـقـيـل: الـمـقـارنـات الـذكـيـة والـمـلـونـة بـنـاءً عـلـى زون الأسـعـار
        # =========================================================
        price_update_date = pd.to_datetime("2026-05-05")

        # دالة داخلية سريعة لفحص زون السعر ليوم المقارنة وإعطائه تاغ ملون صغير
        def get_row_phase_tag(target_dt):
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
            prev = df_daily[df_daily["RCH_DAY"] == target_prev_date]
            if not prev.empty:
                v = prev[kpi_col].values[0]
                growth = round(((current_val - v) / v) * 100, 1)
                daily_changes.append(growth)
                color = "green" if growth >= 0 else "red"
                
                # جلب التاريخ بصيغة Month/Day وزون السعر بتاعه
                date_str = target_prev_date.strftime('%m/%d')
                phase_tag = get_row_phase_tag(target_prev_date)
                daily_text += f'<div class="movement-line">D-{d} ({date_str}) {phase_tag} : <span class="{color}">{growth}%</span></div>'
    
        # 2. صندوق نفس يوم الأسبوع (Same Weekday)
        wd_text, wd_changes = "", []
        same_wd = df_daily[(df_daily["RCH_DAY"].dt.day_name() == weekday_name) & (df_daily["RCH_DAY"] < selected_day)].sort_values("RCH_DAY", ascending=False).head(4)
        for i, (_, row) in enumerate(same_wd.iterrows(), 1):
            growth = round(((current_val - row[kpi_col]) / row[kpi_col]) * 100, 1)
            wd_changes.append(growth)
            color = "green" if growth >= 0 else "red"
            
            # جلب التاريخ وزون السعر بتاعه
            target_wd_date = pd.to_datetime(row["RCH_DAY"])
            date_str = target_wd_date.strftime('%m/%d')
            phase_tag = get_row_phase_tag(target_wd_date)
            wd_text += f'<div class="movement-line">{weekday_name[:3]}-{i} ({date_str}) {phase_tag} : <span class="{color}">{growth}%</span></div>'

        # 3. صندوق يوم الأسبوع + المرحلة (Weekday + Phase)
        df_daily["temp_phase"] = df_daily["RCH_DAY"].apply(get_month_phase)
        ph_text, ph_changes = "", []
        ph_df = df_daily[(df_daily["RCH_DAY"].dt.day_name() == weekday_name) & (df_daily["temp_phase"] == month_phase) & (df_daily["RCH_DAY"] < selected_day)].sort_values("RCH_DAY", ascending=False).head(4)
        for i, (_, row) in enumerate(ph_df.iterrows(), 1):
            growth = round(((current_val - row[kpi_col]) / row[kpi_col]) * 100, 1)
            ph_changes.append(growth)
            color = "green" if growth >= 0 else "red"
            
            # جلب التاريخ وزون السعر بتاعه
            target_ph_date = pd.to_datetime(row["RCH_DAY"])
            date_str = target_ph_date.strftime('%m/%d')
            phase_tag = get_row_phase_tag(target_ph_date)
            ph_text += f'<div class="movement-line">{month_phase[:3]}. {weekday_name[:3]}-{i} ({date_str}) {phase_tag} : <span class="{color}">{growth}%</span></div>'

        # عرض الكروت والتقسيمات المرئية بنفس التنسيق الأصلي تماماً
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        m_left, m_right = st.columns([1, 3])
        with m_left:
            st.markdown(f'<div class="left-panel"><div class="metric-title">{kpi_name}</div><div class="metric-value">{round(current_val,1):,}</div></div>', unsafe_allow_html=True)
        with m_right:
            s1, s2, s3 = st.columns(3)
            with s1: st.markdown(f'<div class="text-box"><div class="section-title">Daily Movement</div>{daily_text}<div class="trend-text">{detect_trend(daily_changes)}</div></div>', unsafe_allow_html=True)
            with s2: st.markdown(f'<div class="text-box"><div class="section-title">Same Weekday</div>{wd_text}<div class="trend-text">{detect_trend(wd_changes)}</div></div>', unsafe_allow_html=True)
            with s3: st.markdown(f'<div class="text-box"><div class="section-title">Weekday + Phase</div>{ph_text}<div class="trend-text">{detect_trend(ph_changes)}</div></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)











# ----------------- TAB 2: ALERTS -----------------



def f_tab_alerts():
    alerts_df = get_alerts_logic(df_raw, selected_day)
    
    if alerts_df.empty:
        st.success("✅ System is Stable - All metrics within normal range.")
    else:
        st.warning(f"⚠️ System detected {len(alerts_df)} deviations for the selected date.")
        
        drops = alerts_df[alerts_df["direction"] == "Drop"].sort_values("growth")
        ups = alerts_df[alerts_df["direction"] == "Up"].sort_values("growth", ascending=False)

        st.markdown(f"""
        <div class="alert-summary-container">
            <div style="text-align:center; flex:1;">
                <span style="font-size:38px; font-weight:800; color:#DA3633;">{len(drops)}</span><br/>
                <small style="color:#8B949E;">DROPS DETECTED</small>
            </div>
            <div style="text-align:center; flex:1; border-left:1px solid #30363D;">
                <span style="font-size:38px; font-weight:800; color:#238636;">{len(ups)}</span><br/>
                <small style="color:#8B949E;">UPS DETECTED</small>
            </div>
        </div>
        """, unsafe_allow_html=True)

        t_drops_main, t_ups_main = st.tabs(["📉 DROPS ANALYSIS", "📈 UPS ANALYSIS"])
        
        with t_drops_main:
            show_alerts(drops, True)
        with t_ups_main:
            show_alerts(ups, False)









# ----------------- TAB 3: ALERTS V2 (CONTRIBUTION WITH DUAL INTERNAL FILTERS) -----------------


def f_tab_alerts_v2():
    st.markdown('<div class="section-header">🎯 Contribution Alerts Center (V2)</div>', unsafe_allow_html=True)
    st.write("Advanced analysis using absolute changes and smart seasonality matching to identify actual business drivers.")
    
    # عمل صف فيه فلاتر التحكم الداخلي جنب بعض شياكة
    col_filt1, col_filt2 = st.columns(2)
    
    with col_filt1:
        # 1. فلتر وضع المقارنة (الـ 3 خيارات بتوعك)
        selected_comp_mode = st.selectbox(
            "📅 Select Comparison Basis (Seasonality):",
            options=[
                "vs Yesterday (D-1)", 
                "vs Same Day Last Week (D-7)", 
                "vs Same Weekday & Month Phase (Smart Match)"
            ],
            key="v2_comp_mode_filter"
        )
        
    # استدعاء الداتا من المطبخ وتمرير وضع المقارنة المختار
    alerts_v2_df = get_alerts_logic_v2(df_raw, selected_day, selected_comp_mode)
    
    if alerts_v2_df.empty:
        st.success(f"✅ No major contribution spikes detected for the selected mode: {selected_comp_mode}.")
    else:
        with col_filt2:
            # 2. فلتر الـ KPIs
            available_metrics = ["All KPIs"] + list(alerts_v2_df["metric"].unique())
            selected_metric_filter = st.selectbox(
                "🔍 Filter Alerts by KPI:",
                options=available_metrics,
                key="v2_internal_kpi_filter"
            )
            
        # إظهار تاريخ اليوم اللي السيستم لقطه وقارن بيه عشان اليوزر يبقى مطمئن وعارف هو بيبص على إيه
        matched_date_str = alerts_v2_df["compared_to_date"].iloc[0]
        st.caption(f"💡 *Currently matching data of **{selected_day.strftime('%Y-%m-%d')}** against historical baseline date: **{matched_date_str}** ({selected_comp_mode})*")

        # تطبيق فلتر الـ KPI لو اليوزر اختار مؤشر معين
        if selected_metric_filter != "All KPIs":
            filtered_alerts_df = alerts_v2_df[alerts_v2_df["metric"] == selected_metric_filter]
        else:
            filtered_alerts_df = alerts_v2_df

        # إعادة تقسيم التنبيهات المفلترة بناءً على اتجاه الحركة
        decline_drivers = filtered_alerts_df[filtered_alerts_df["network_direction"] == "Decline"].sort_values("contribution", ascending=False)
        increase_drivers = filtered_alerts_df[filtered_alerts_df["network_direction"] == "Increase"].sort_values("contribution", ascending=False)

        # عرض العدادات المجمعة الذكية
        st.markdown(f"""
        <div class="alert-summary-container">
            <div style="text-align:center; flex:1;">
                <span style="font-size:38px; font-weight:800; color:#DA3633;">{len(decline_drivers)}</span><br/>
                <small style="color:#8B949E;">DRIVERS OF DECLINE ({selected_metric_filter})</small>
            </div>
            <div style="text-align:center; flex:1; border-left:1px solid #30363D;">
                <span style="font-size:38px; font-weight:800; color:#238636;">{len(increase_drivers)}</span><br/>
                <small style="color:#8B949E;">DRIVERS OF INCREASE ({selected_metric_filter})</small>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # عرض الكروت المفلترة جوه الـ Tabs الداخلية
        t_decline, t_increase = st.tabs(["📉 DRIVERS OF DECLINE ANALYSIS", "📈 DRIVERS OF INCREASE ANALYSIS"])
        
        with t_decline:
            if decline_drivers.empty:
                st.info(f"No segments detected as drivers for decline under ({selected_metric_filter}).")
            else:
                show_contribution_alerts(decline_drivers)
                
        with t_increase:
            if increase_drivers.empty:
                st.info(f"No segments detected as drivers for increase under ({selected_metric_filter}).")
            else:
                show_contribution_alerts(increase_drivers)








# ----------------- TAB 4: IBRO BEHAVIORAL DATA CENTER (EXECUTIVE PREMIUM) -----------------
def f_tab_ibro():
    st.markdown('<div class="section-header">🚀 IBRO Behavioral Data Center</div>', unsafe_allow_html=True)
    
    # 1. الحماية الأولى: التأكد أن الداتا فريم مش فاضي وقادم من الجوجل شيت بنجاح
    if 'df_ibro' in globals() and not df_ibro.empty:
    #if 'df_ibro' in locals() and not df_ibro.empty:

        
        # تحويل عمود التاريخ لنصوص لضمان دقة المقارنة
        df_ibro_clean = df_ibro.copy()
        df_ibro_clean['reported_date_str'] = pd.to_datetime(df_ibro_clean['reported_date']).dt.strftime('%Y-%m-%d')
        target_date_str = pd.to_datetime(selected_day).strftime('%Y-%m-%d')
        
        # تصفية البيانات المبدئية لليوم المختار فقط
        df_day_base = df_ibro_clean[df_ibro_clean['reported_date_str'] == target_date_str]
        
        # 2. اللوجيك الذكي للعرض لو اليوم ده جواه داتا فعلاً
        if not df_day_base.empty:
            
            st.markdown("#### 🎛️ Dashboard Controls")
            # 3 فلاتر تكتيكية في صف واحد
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                mode_options = sorted(list(df_day_base['mode'].unique()))
                chosen_mode = st.selectbox("🔄 Time Window (Mode):", options=mode_options, index=0, key="apro_mode_v9")
            with col_f2:
                segment_options = ["All Segments"] + sorted(list(df_day_base['tariff_sub_category_2'].unique()))
                chosen_segment = st.selectbox("👥 Customer Segment:", options=segment_options, index=0, key="apro_seg_v9")
            with col_f3:
                multisim_options = ["All Multi-Sim Status"] + sorted(list(df_day_base['no_of_multisim'].unique()))
                chosen_multisim = st.selectbox("📱 Multi-Sim Status:", options=multisim_options, index=0, key="apro_multi_v9")
            
            st.write("---") # خط فاصل
            
            # 🚀 3. استدعاء الفانكشن التحليلية لتجهيز البيانات
            inflow, outflow, net, _, df_final_chart = process_behavioral_data_v2(
                df_day_base, chosen_mode, chosen_segment, chosen_multisim
            )
            
            # 🧠 💡 لوجيك الـ Most Affected Gov الجديد والمطور:
            # بنحسب الصافي لكل محافظة عشان نطلع أكتر واحدة بتنزف صافي خطوط فعلياً (أعلى رقم سالب)
            if not df_final_chart.empty:
                df_gov_calc = df_final_chart.copy()
                df_gov_calc['signed_subs'] = df_gov_calc.apply(
                    lambda r: r['unq_subs'] if r['movement_type'] == 'INFLOW' else -r['unq_subs'], axis=1
                )
                df_gov_net_sum = df_gov_calc.groupby('governorate')['signed_subs'].sum().reset_index()
                
                # المحافظات اللي بتخسر (صافي سالب)
                df_only_losers = df_gov_net_sum[df_gov_net_sum['signed_subs'] < 0]
                if not df_only_losers.empty:
                    # اختيار المحافظة صاحبة أصغر رقم (أعلى خسارة في النزيف الصافي)
                    worst_row = df_only_losers.sort_values(by='signed_subs', ascending=True).iloc[0]
                    executive_affected_gov = f"📍 {worst_row['governorate']} ({worst_row['signed_subs']:,})"
                else:
                    executive_affected_gov = "No Net Leakage"
            else:
                executive_affected_gov = "No Data"
            
            # 📊 4. فرش كروت الـ KPIs بتصميم ناصع وواضح جداً (Bold وخطوط واضحة)
            st.markdown(f"##### 📈 KPIs Overview for **{target_date_str}**")
            
            # كود CSS لحقن ستايل الكروت وتفتيح الكلام وتكبير الأرقام
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
                st.metric(label="⚖️ Net Growth / Leakage", value=f"{net:,}", delta=f"{net:,}", delta_color=delta_color)
            # with kpi_4:
            #     st.metric(label="🚨 Most Affected Gov (Highest Leakage)", value=executive_affected_gov)
            #     #st.metric(label="🚨 Most Affected Gov (Highest Leakage)", value=f"{executive_affected_gov:,}")


            with kpi_4:
                # 🪄 التعديل السحري: فصل اسم المحافظة عن رقم الخسارة عشان يظهر تحتها علطول بالأحمر من غير قص
                if 'df_only_losers' in locals() and not df_only_losers.empty:
                    st.metric(
                        label="🚨 Most Affected Gov (Highest Leakage)", 
                        value=f"📍 {worst_row['governorate']}", 
                        delta=f"{worst_row['signed_subs']:,} Subs",
                        delta_color= "normal"  #"inverse"  # '#c0392b'
                        
                    )
                else:
                    st.metric(label="🚨 Most Affected Gov (Highest Leakage)", value="No Net Leakage")
 
                
            st.write("---") # Spacer
            
            import plotly.express as px
            import plotly.graph_objects as go
            
            if not df_final_chart.empty:
                
                # ==================== [رقم 1: الشلال - Waterfall Chart] ====================
                st.markdown("##### 🌊 Subscriber Net Flow Breakdown (Geographic Waterfall Analysis)")
                df_zone = df_final_chart.copy()
                df_zone['subs_signed'] = df_zone.apply(
                    lambda row: row['unq_subs'] if row['movement_type'] == 'INFLOW' else -row['unq_subs'], axis=1
                )
                df_zone_agg = df_zone.groupby('market_zone')['subs_signed'].sum().reset_index()
                
                x_data = ["Base (0)"]
                y_data = [0]
                measure_data = ["relative"]
                for idx, row in df_zone_agg.iterrows():
                    x_data.append(row['market_zone'])
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
                    font=dict(color="white", size=12) # إجبار الخطوط على اللون الأبيض
                )
                st.plotly_chart(fig_waterfall, use_container_width=True)
                
                st.write("---") # Spacer
                
                # ==================== [رقم 2: المحافظات مـرآة - Mirror Top 5 Gainers vs Losers] ====================
                st.markdown("##### 🎯 Net Flow Focus: Top 5 Gainers vs Top 5 Losers (Governorate Level)")
                col_net1, col_net2 = st.columns(2)
                
                df_gov_net = df_final_chart.copy()
                df_gov_net['signed_subs'] = df_gov_net.apply(
                    lambda r: r['unq_subs'] if r['movement_type'] == 'INFLOW' else -r['unq_subs'], axis=1
                )
                df_gov_summary = df_gov_net.groupby('governorate')['signed_subs'].sum().reset_index()
                
                with col_net1:
                    st.markdown("<p style='color: #2ecc71; font-weight: bold; font-size:14px;'>📈 Top 5 Net Gainers </p>", unsafe_allow_html=True)
                    df_gainers = df_gov_summary[df_gov_summary['signed_subs'] > 0].sort_values(by='signed_subs', ascending=True).tail(5)
                    
                    if not df_gainers.empty:
                        fig_gainers = px.bar(
                            df_gainers, x='signed_subs', y='governorate', orientation='h',
                            text_auto='+,', template='plotly_dark'
                        )
                        fig_gainers.update_traces(marker_color='#2ecc71', textposition='outside', textfont=dict(color="white", size=11))
                        fig_gainers.update_layout(
                            margin=dict(l=10, r=10, t=10, b=10), height=250,
                            xaxis_title="Net Subs Gained", yaxis_title=None,
                            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                            font=dict(color="white") # تفتيح خطوط أسماء المحافظات والمحاور
                        )
                        st.plotly_chart(fig_gainers, use_container_width=True)
                    else:
                        st.caption("No positive net gainers for this selection.")
                        
                with col_net2:
                    st.markdown("<p style='color: #e74c3c; font-weight: bold; font-size:14px; text-align: right;'>📉 Top 5 Net Losers </p>", unsafe_allow_html=True)
                    df_losers = df_gov_summary[df_gov_summary['signed_subs'] < 0].sort_values(by='signed_subs', ascending=False).tail(5)
                    
                    if not df_losers.empty:
                        # تكتيك المراية السحري: نقل الأسماء والمحور لليمين خالص
                        fig_losers = px.bar(
                            df_losers, x='signed_subs', y='governorate', orientation='h',
                            text_auto=',', template='plotly_dark'
                        )
                        fig_losers.update_traces(marker_color='#e74c3c', textposition='outside', textfont=dict(color="white", size=11))
                        fig_losers.update_layout(
                            margin=dict(l=10, r=10, t=10, b=10), height=250,
                            xaxis_title="Net Subs Lost", yaxis_title=None,
                            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                            font=dict(color="white"),
                            yaxis=dict(side='right') # 🪄 نقل أسماء المحافظات لليمين لعمل تأثير المراية
                        )
                        st.plotly_chart(fig_losers, use_container_width=True)
                    else:
                        st.caption("No negative net losers for this selection.")
                        
                st.write("---") # Spacer
                
                # ==================== [رقم 3: الدونات والـ Legend الناصعة - Behavioral Donut Charts] ====================
                st.markdown("##### 🍰 Behavioral Mix Analysis (Inflow vs Outflow Profiles)")
                col_pie1, col_pie2 = st.columns(2)
                
                behavior_colors = {
                    'MIX': '#7f8c8d',          # جري (رمادي غامق)
                    'BC_ONLY': '#f39c12',      # أورنج
                    'NORMAL_ONLY': '#c0392b',  # أحمر
                    'SILENT': '#34495e'        # رمادي مائل للأسود
                }
                
                with col_pie1:
                    st.markdown("<p style='text-align: center; color: #2ecc71; font-weight: bold;'>🟢 INFLOW Profile (What they recharge NOW)</p>", unsafe_allow_html=True)
                    df_in = df_final_chart[df_final_chart['movement_type'] == 'INFLOW']
                    
                    if not df_in.empty:
                        df_in_pie = df_in.groupby('rch_behaviour_current_period')['unq_subs'].sum().reset_index()
                        fig_in_pie = px.pie(
                            df_in_pie, values='unq_subs', names='rch_behaviour_current_period',
                            hole=0.4, color='rch_behaviour_current_period', color_discrete_map=behavior_colors,
                            template='plotly_dark'
                        )
                        # تفتيح وتكبير خط الـ Legend ليكون ناصع البياض وواضح جداً للمدير
                        fig_in_pie.update_layout(
                            margin=dict(l=10, r=10, t=10, b=10), height=250, showlegend=True, 
                            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                            legend=dict(font=dict(color="white", size=12)), # 💡 تفتيح خط الـ Legend هنا
                        )
                        fig_in_pie.update_traces(textposition='inside', textinfo='percent', textfont=dict(color="white", size=12, weight="bold"))
                        st.plotly_chart(fig_in_pie, use_container_width=True)
                    else:
                        st.caption("No Inflow data available.")
                        
                with col_pie2:
                    st.markdown("<p style='text-align: center; color: #e74c3c; font-weight: bold;'>🔴 OUTFLOW Profile (What they used to recharge BEFORE)</p>", unsafe_allow_html=True)
                    df_out = df_final_chart[df_final_chart['movement_type'] == 'OUTFLOW']
                    
                    if not df_out.empty:
                        df_out_pie = df_out.groupby('rch_behaviour_previous_period')['unq_subs'].sum().reset_index()
                        fig_out_pie = px.pie(
                            df_out_pie, values='unq_subs', names='rch_behaviour_previous_period',
                            hole=0.4, color='rch_behaviour_previous_period', color_discrete_map=behavior_colors,
                            template='plotly_dark'
                        )
                        # تفتيح وتكبير خط الـ Legend ليكون ناصع البياض
                        fig_out_pie.update_layout(
                            margin=dict(l=10, r=10, t=10, b=10), height=250, showlegend=True, 
                            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                            legend=dict(font=dict(color="white", size=12)), # 💡 تفتيح خط الـ Legend هنا
                        )
                        fig_out_pie.update_traces(textposition='inside', textinfo='percent', textfont=dict(color="white", size=12, weight="bold"))
                        st.plotly_chart(fig_out_pie, use_container_width=True)
                    else:
                        st.caption("No Outflow data available.")
            else:
                st.info("💡 No active data found matching the selected combination of filters.")
            
        else:
            # 8. الحماية الديناميكية لو اليوم المختار بره المدى
            df_ibro_clean['reported_date_pure'] = pd.to_datetime(df_ibro_clean['reported_date']).dt.date
            min_available_date = df_ibro_clean['reported_date_pure'].min()
            max_available_date = df_ibro_clean['reported_date_pure'].max()
            st.warning(f"⚠️ No behavior data available for the selected date: **{target_date_str}**.")








def f_tab_network(global_selected_date):
    st.subheader("📡 Network Sites Performance & Top 10 Analysis")

    # 1. مناداة فانكشن تحميل الداتا اللي برة
    df_net = load_master_network_data()

    if df_net.empty:
        return

    # 2. تحويل التاريخ الموحد الممرر من برة لـ datetime للحسبات
    target_day = pd.to_datetime(global_selected_date)

    # 3. الفلاتر المترابطة الشلالية (Cascading Filters) جوه التاب
    col_f1, col_f2 = st.columns(2)
    
    with col_f1:
        zones_options = ["All"] + list(df_net['market_zone'].dropna().unique())
        selected_zone = st.selectbox("🌐 Select Market Zone:", options=zones_options, key="net_zone_sb")

    with col_f2:
        if selected_zone != "All":
            available_govs = df_net[df_net['market_zone'] == selected_zone]['governorate'].dropna().unique()
        else:
            available_govs = df_net['governorate'].dropna().unique()
            
        govs_options = ["All"] + list(available_govs)
        selected_gov = st.selectbox("📍 Select Governorate:", options=govs_options, key="net_gov_sb")

    # ✨ التعديل الجديد: زرار تحديد الرؤية (موجب أو سالب) في مكان واضح
    st.markdown("---")
    analysis_mode = st.radio(
        "📊 Select Analysis View:",
        options=["📈 Top 10 Growth (Highest Gain)", "📉 Top 10 Drop (Highest Loss)"],
        horizontal=True,
        key="net_analysis_mode"
    )
    st.markdown("---")

    # 4. تجهيز تواريخ الأبعاد الثلاثة لورا بناءً على اليوم الموحد
    daily_past = [target_day - timedelta(days=i) for i in range(1, 7)]
    weekly_past = [target_day - timedelta(days=7*i) for i in range(1, 5)]
    monthly_past = [target_day - timedelta(days=30*i) for i in range(1, 5)]

    # 5. مناداة الفانكشن الحسابية اللي برة لتجهيز البيانات للأبعاد الـ 3
    df_daily_res = get_top_10_analysis(df_net, target_day, daily_past, selected_zone, selected_gov)
    df_weekly_res = get_top_10_analysis(df_net, target_day, weekly_past, selected_zone, selected_gov)
    df_monthly_res = get_top_10_analysis(df_net, target_day, monthly_past, selected_zone, selected_gov)

    # 6. تصميم واجهة العرض الأمامية (Sub-tabs) والـ 3 عواميد
    sub_tab1, sub_tab2, sub_tab3 = st.tabs([
        "📆 Daily Trend (vs Past 6 Days)", 
        "🗓️ Weekly Trend (vs Same Day - Past 4 Weeks)", 
        "🌙 Monthly Trend (vs Same Stage - Past 4 Months)"
    ])

    #============== ABS RANKING WITH MODE SWITCH & INT FORMAT
    def render_top_10_columns(df_res):
        if df_res is None or df_res.empty:
            st.warning("⚠️ No historical data found in the master file for this specific date range/filter.")
            return

        col1, col2, col3 = st.columns(3)
        
        def color_delta(val):
            color = '#123819' if val >= 0 else '#5c1d1d'
            return f'background-color: {color}; color: white; font-weight: bold;'

        # تحديد الفانكشن الحسابية للترتيب بناءً على اختيارات الزرار
        if "Growth" in analysis_mode:
            # لو نمو نجيب القيم الكبيرة من فوق (الموجب)
            get_ranked_data = lambda df, col_name: df.nlargest(10, col_name)
            title_suffix = "Growth"
        else:
            # لو هبوط نجيب أصغر القيم من تحت (السالب الكبير)
            get_ranked_data = lambda df, col_name: df.nsmallest(10, col_name)
            title_suffix = "Drop"

        with col1:
            st.markdown(f"<h4 style='text-align: center; color: #4A90E2;'>🔝 Top 10 Unique Subs {title_suffix}</h4>", unsafe_allow_html=True)
            top_subs = get_ranked_data(df_res, 'Subs Diff')[['site_code', 'Subs Diff', 'Subs Change %']]
            top_subs.columns = ['Site Code', 'Subs Added' if "Growth" in analysis_mode else 'Subs Lost', 'Growth %']
            st.dataframe(
                # 🔥 التعديل السحري: استخدام :+.0f لعمل راوند أوتوماتيكي بصفر وإخفاء الكسور المستفزة
                top_subs.style.format({'Subs Added': '{:+.0f}', 'Subs Lost': '{:+.0f}', 'Growth %': '{:+.1f}%'}).map(color_delta, subset=['Growth %']),
                use_container_width=True, hide_index=True
            )

        with col2:
            st.markdown(f"<h4 style='text-align: center; color: #4A90E2;'>🔝 Top 10 TRX {title_suffix}</h4>", unsafe_allow_html=True)
            top_count = get_ranked_data(df_res, 'Count Diff')[['site_code', 'Count Diff', 'Count Change %']]
            top_count.columns = ['Site Code', 'Trx Added' if "Growth" in analysis_mode else 'Trx Lost', 'Growth %']
            st.dataframe(
                top_count.style.format({'Trx Added': '{:+.0f}', 'Trx Lost': '{:+.0f}', 'Growth %': '{:+.1f}%'}).map(color_delta, subset=['Growth %']),
                use_container_width=True, hide_index=True
            )

        with col3:
            st.markdown(f"<h4 style='text-align: center; color: #4A90E2;'>🔝 Top 10 Amount {title_suffix}</h4>", unsafe_allow_html=True)
            top_amt = get_ranked_data(df_res, 'Amount Diff')[['site_code', 'Amount Diff', 'Amount Change %']]
            top_amt.columns = ['Site Code', 'Amt Added' if "Growth" in analysis_mode else 'Amt Lost', 'Growth %']
            st.dataframe(
                top_amt.style.format({'Amt Added': '{:+.0f}', 'Amt Lost': '{:+.0f}', 'Growth %': '{:+.1f}%'}).map(color_delta, subset=['Growth %']),
                use_container_width=True, hide_index=True
            )

    # عرض الجداول جوه التابات الفرعية
    with sub_tab1:
        st.caption(f"Showing Top 10 sites with highest change on {target_day.strftime('%Y-%m-%d')} compared to the average of the last 6 days.")
        render_top_10_columns(df_daily_res)

    with sub_tab2:
        st.caption(f"Showing Top 10 sites with highest change compared to the average of the same day in the past 4 weeks.")
        render_top_10_columns(df_weekly_res)

    with sub_tab3:
        st.caption(f"Showing Top 10 sites with highest change compared to the average of the same stage in the past 4 months.")
        render_top_10_columns(df_monthly_res)





#============== DATA MONITORING






#============== VOICE MONITORING









#============== OC MONITORING











# =========================================================
# 2. Password
# =========================================================

# 🔒 دالة للتحقق من الباسورد
# def check_password():
#     """بتفرمل الأبلكيشن وتطلع شاشة تسجيل الدخول لو الباسورد مش مظبوطة"""
#     if "password_correct" not in st.session_state:
#         st.session_state.password_correct = False

#     # لو اليوزر كتبها صح قبل كده، عدي علطول
#     if st.session_state.password_correct:
#         return True

#     # رسم شاشة الدخول الشيك في نص الصفحة
#     st.title("🔒 Orange Internal Dashboard")
#     user_password = st.text_input("Enter Password to Access the Dashboard:", type="password")
    
#     if st.button("Login"):
#         # بيقارن اللي اليوزر كتبه باللي إنت مخبيه في الـ secrets
#         if user_password == st.secrets["password"]:
#             st.session_state.password_correct = True
#             st.rerun() # يعمل ريفريش عشان يفتح الأبلكيشن
#         else:
#             st.error("❌ Incorrect Password. Please try again.")
            
#     return False

# # 🛑 تشغيل حارس البوابة (لو رجع False الكود اللي تحته مش هيتنفذ والأبلكيشن هيفضل مقفول)
# if not check_password():
#     st.stop()




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





    


#==============DATA LOADING



# @st.cache_data(ttl=600)
# #@st.cache_data(ttl=60)
# def load_data():

#     scope = [
#         "https://spreadsheets.google.com/feeds",
#         "https://www.googleapis.com/auth/drive"
#     ]

#     # =====================================================
#     # Read Credentials
#     # =====================================================

#     # لو ملف JSON موجود
#     if os.path.exists("credentials.json"):

#         creds = ServiceAccountCredentials.from_json_keyfile_name(
#             "credentials.json",
#             scope
#         )

#     # لو مش موجود يقرأ من Streamlit Secrets
#     else:

#         creds_text = st.secrets["google_credentials"]

#         creds_info = json.loads(
#             creds_text,
#             strict=False
#         )

#         creds = ServiceAccountCredentials.from_json_keyfile_dict(
#             creds_info,
#             scope
#         )

#     # =====================================================
#     # Google Sheets Connection
#     # =====================================================

#     client = gspread.authorize(creds)

#     # 1. سحب بيانات الشيت الأول والأساسي (زي ما هو بالملي)
#     sheet = client.open("Recharge_Monitoring_Data").sheet1
#     all_records = sheet.get_all_records()
#     df_raw = pd.DataFrame(all_records)
#     df_raw['RCH_DAY'] = pd.to_datetime(df_raw['RCH_DAY'])

#     # 2. سحب بيانات الشيت الجديد (IBRO_RCH_PER_DAY)
#     # ملاحظة: لو اسم الشيت على جوجل درايف مختلف عن "IBRO_RCH_PER_DAY"، اكتب الاسم الصح بين القوسين
#     try:
#         # بيفتح الملف الجديد وبياخد أول تاب فيه (sheet1)
#         sheet_apro = client.open("IBRO_RCH_PER_DAY").sheet1
#         records_apro = sheet_apro.get_all_records()
#         df_ibro = pd.DataFrame(records_apro)
        
#         # لو الشيت الجديد جواه عمود تواريخ وعايز تحوله، تقدر تفك الكومنت عن السطر اللي تحت
#         # df_ibro['RCH_DAY'] = pd.to_datetime(df_ibro['RCH_DAY'])
        
#         print("✅ IBRO_RCH_PER_DAY loaded successfully! Shape:", df_ibro.shape)
#     except Exception as e:
#         # حماية: لو الشيت الجديد لسه مضافش أو فيه مشكلة في الصلاحيات، الكود مش هيقفل وهيطلع داتا فريم فاضي
#         print("❌ Error loading IBRO_RCH_PER_DAY sheet:", e)
#         df_ibro = pd.DataFrame()

#     # الدالة دلوقتي بترجع ملفين داتا فريم مع بعض كـ Tuple
#     return df_raw, df_ibro








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
        # قراءة ملف الباركيه الماستر الـ 18 ميجا المرفوع في الريبو
        #df_raw = pd.read_parquet("Recharge_Monitoring_Data_HIST.parquet")
        df_raw = pd.read_parquet(f"{RECHARGE_DIR}Recharge_Monitoring_Data_HIST.parquet")
        df_raw['RCH_DAY'] = pd.to_datetime(df_raw['RCH_DAY'])


        #df_ibro = pd.read_parquet("IBRO_RCH_PER_DAY_HIST.parquet")
        df_ibro = pd.read_parquet(f"{RECHARGE_DIR}IBRO_RCH_PER_DAY_HIST.parquet")
        df_ibro['reported_date'] = pd.to_datetime(df_ibro['reported_date'])



        return df_raw , df_ibro
    

    except Exception as e:
        st.error(f"❌ Error loading': {e}")
        return pd.DataFrame()
    







#@st.cache_data(ttl=600)
def load_master_network_data():
    try:
        # قراءة ملف الباركيه الماستر الـ 18 ميجا المرفوع في الريبو
        #df = pd.read_parquet("network_master.parquet")
        df = pd.read_parquet(f"{RECHARGE_DIR}network_master.parquet")
        df['rch_day'] = pd.to_datetime(df['rch_day'])
        return df
    except Exception as e:
        st.error(f"❌ Error loading 'network_master.parquet': {e}")
        return pd.DataFrame()
    



#==========SUMMARY HEADER CARDS

#@st.cache_data(ttl=600)
def load_master_SUMMARY_data():
    try:
        # قراءة ملف الباركيه الماستر الـ 18 ميجا المرفوع في الريبو
        # DATA_PER_DAY_HIST      = pd.read_parquet("DATA_PER_DAY_HIST.parquet")
        # OUG_VOICE_PER_DAY_HIST = pd.read_parquet("OUG_VOICE_PER_DAY_HIST.parquet")
        # OC_PER_DAY_HIST        = pd.read_parquet("OC_PER_DAY_HIST.parquet")

        DATA_PER_DAY_HIST        = pd.read_parquet(f"{DATA_DIR}DATA_PER_DAY_HIST.parquet")
        OUG_VOICE_PER_DAY_HIST   = pd.read_parquet(f"{VOICE_DIR}OUG_VOICE_PER_DAY_HIST.parquet")
        OC_PER_DAY_HIST          = pd.read_parquet(f"{CASH_DIR}OC_PER_DAY_HIST.parquet")
        OC_SERVICES_PER_DAY_HIST = pd.read_parquet(f"{CASH_DIR}OC_SERVICES_PER_DAY_HIST.parquet")



        DATA_PER_DAY_HIST['data_usage_day']       = pd.to_datetime(DATA_PER_DAY_HIST['data_usage_day'])
        OUG_VOICE_PER_DAY_HIST['voice_usage_day'] = pd.to_datetime(OUG_VOICE_PER_DAY_HIST['voice_usage_day'])
        OC_PER_DAY_HIST['oc_usage_day']           = pd.to_datetime(OC_PER_DAY_HIST['oc_usage_day'])
        OC_SERVICES_PER_DAY_HIST['oc_usage_day']  = pd.to_datetime(OC_SERVICES_PER_DAY_HIST['oc_usage_day'])



        return DATA_PER_DAY_HIST , OUG_VOICE_PER_DAY_HIST , OC_PER_DAY_HIST , OC_SERVICES_PER_DAY_HIST
    except Exception as e:
        st.error(f"❌ Error loading SUMMARY_data': {e}")
        return pd.DataFrame()









# استخدام Spinner يظهر بوضوح أثناء التحميل
with st.spinner('Fetching Data...'):
    try:
        #df_raw = load_data()
        df_raw, df_ibro = load_data()
        DATA_PER_DAY_HIST , OUG_VOICE_PER_DAY_HIST , OC_PER_DAY_HIST , OC_SERVICES_PER_DAY_HIST = load_master_SUMMARY_data()
    except Exception as e:
        st.error(f'Error connecting to database: {e}')
        st.stop()




df_daily = df_raw.groupby('RCH_DAY').agg({
        'DAILY_UNQ_SUBS': 'max',
        'DAILY_TRX_COUNTS': 'max',
        'DAILY_TRX_AMOUNTS': 'max'
    }).reset_index()

df_daily["avg_recharge"] = df_daily["DAILY_TRX_AMOUNTS"] / df_daily["DAILY_UNQ_SUBS"]


df_daily = df_daily.sort_values('RCH_DAY')



# #-------DATA

# df_daily_data = DATA_PER_DAY_HIST.groupby('data_usage_day').agg({
#         'total_unq_subs': 'max'
#     }).reset_index()


# df_daily_data = df_daily_data.sort_values('data_usage_day')





# #-------VOICE

# df_daily_voice = OUG_VOICE_PER_DAY_HIST.groupby('voice_usage_day').agg({
#         'total_unq_subs': 'max'
#     }).reset_index()


# df_daily_voice = df_daily_voice.sort_values('voice_usage_day')



# #-------OC

# df_daily_cash = OC_PER_DAY_HIST.groupby('oc_usage_day').agg({
#         'total_unq_subs': 'max'
#     }).reset_index()


# df_daily_cash = df_daily_cash.sort_values('oc_usage_day')













# العناوين والمدخلات
st.markdown('<div class="main-title">📊 All Products Behavior Monitoring</div>', unsafe_allow_html=True)

# 1. تحديد التاريخ من المدخلات وحساب اليوم المختار
max_date = df_daily['RCH_DAY'].max().date()
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
st.markdown(f'<div class="header-bar"><div>📅 {selected_day.date()}</div><div>📆 {weekday_name}</div><div>🗓️ {month_phase}</div></div>', unsafe_allow_html=True)

# 4. عرض الهيدر الصغير الجديد المتسنتر للمقارنة بين زون الأسعار لليومين
st.markdown(f"""
<div style="text-align: center; margin-top: -10px; margin-bottom: 25px; font-size: 14px; font-weight: 700; background-color: #161B22; border: 1px solid #30363D; border-radius: 10px; padding: 6px 25px; width: fit-content; margin-left: auto; margin-right: auto; color: #8B949E;">
    Selected Day: {current_status} &nbsp; &nbsp; &nbsp; &nbsp;  | &nbsp; &nbsp; &nbsp; &nbsp; Compared Day (D-1): {prev_status}
</div>
""", unsafe_allow_html=True)







# 1. Summary Cards
# prev_day = selected_day - timedelta(days=1)
# curr_row = df_daily[df_daily["RCH_DAY"] == selected_day]
# prev_row = df_daily[df_daily["RCH_DAY"] == prev_day]


# # 🛡️ حارس البوابة الذكي (الفرملة المبكرة):
# if curr_row.empty or prev_row.empty:
#     # لو أي يوم فيهم فاضي، هيطلع الرسالة ويقفل الأبلكيشن في ثانية
#     st.warning(f"⚠️ No data available for the selected date: **{selected_day.date()}**. Please check your data source or select another day.")
#     st.stop() # 🪄 الفرملة السحرية.. الكود اللي تحت مستحيل يشتغل ومستحيل يضرب إيرور!

# kpis_config = [
#     ("Recharge Users", "DAILY_UNQ_SUBS"),
#     ("Transactions", "DAILY_TRX_COUNTS"),
#     ("Recharge Amount", "DAILY_TRX_AMOUNTS"),
#     ("Avg Recharge", "avg_recharge")
# ]

# if not curr_row.empty and not prev_row.empty:
#     cols = st.columns(4)
#     for i, (name, col_name) in enumerate(kpis_config):
#         curr_val = curr_row[col_name].values[0]
#         p_val = prev_row[col_name].values[0]
#         diff = ((curr_val - p_val) / p_val) * 100
        
#         status_label, status_color = get_status_details(diff)
#         delta_class = "green" if diff >= 0 else "red"
#         symbol = "+" if diff >= 0 else ""
        
#         with cols[i]:
#             st.markdown(f"""
#             <div class="summary-card" style="border-left: 6px solid {status_color};">
#                 <div class="summary-label">{name}</div>
#                 <div class="summary-value">{round(curr_val, 1):,}</div>
#                 <div class="summary-delta {delta_class}">{symbol}{round(diff, 1)}% vs D-1</div>
#                 <div class="status-tag" style="background-color: {status_color};">{status_label}</div>
#             </div>
#             """, unsafe_allow_html=True)

# st.write("") 









# =========================================================
# 1. Summary Cards (Multi-Source High-Level Dashboard) - Direct Version
# =========================================================
# prev_day = selected_day - timedelta(days=1)

# # دالة داخلية ذكية وسريعة بتجيب القيمة دايركت لليوم من غير أي groupby وبأعلى حماية
# def get_direct_day_value(df_source, target_date, default_col="DAILY_UNQ_SUBS"):
#     if df_source is not None and not df_source.empty:
#         # 1. البحث عن عمود التاريخ أوتوماتيك (سواء اسمه RCH_DAY أو أي اسم تاني)
#         date_col = "RCH_DAY" if "RCH_DAY" in df_source.columns else df_source.columns[0]
        
#         # 2. فلترة سطر اليوم المستهدف
#         df_filtered = df_source[df_source[date_col] == target_date]
        
#         if not df_filtered.empty:
#             # 3. تحديد اسم عمود الـ Unique Subs (لو DAILY_UNQ_SUBS مش موجود هياخد العمود التاني في الملف)
#             actual_col = default_col if default_col in df_source.columns else df_source.columns[1]
#             return df_filtered[actual_col].values[0]
#     return 0

# # سحب القيم دايركت بأمان تام للنهاردة وامبارح
# val_rch_curr = get_direct_day_value(df_daily, selected_day)
# val_rch_prev = get_direct_day_value(df_daily, prev_day)

# val_data_curr = get_direct_day_value(df_daily_data, selected_day)
# val_data_prev = get_direct_day_value(df_daily_data, prev_day)

# val_voice_curr = get_direct_day_value(df_daily_voice, selected_day)
# val_voice_prev = get_direct_day_value(df_daily_voice, prev_day)

# val_cash_curr = get_direct_day_value(df_daily_cash, selected_day)
# val_cash_prev = get_direct_day_value(df_daily_cash, prev_day)

# # الـ Configuration المباشر للكروت
# kpis_multi_config = [
#     ("Recharge Users", val_rch_curr, val_rch_prev),
#     ("Data Users", val_data_curr, val_data_prev),     
#     ("Voice Users", val_voice_curr, val_voice_prev),   
#     ("Orange Cash Users", val_cash_curr, val_cash_prev) 
# ]

# cols = st.columns(4)
# for i, (name, curr_val, p_val) in enumerate(kpis_multi_config):
#     # حسبة النسبة المئوية للنمو أو الهبوط مقارنة بامبارح
#     if p_val != 0:
#         diff = ((curr_val - p_val) / p_val) * 100
#     else:
#         diff = 0

#     status_label, status_color = get_status_details(diff)
#     delta_class = "green" if diff >= 0 else "red"
#     symbol = "+" if diff >= 0 else ""
    
#     with cols[i]:
#         st.markdown(f"""
#         <div class="summary-card" style="border-left: 6px solid {status_color};">
#             <div class="summary-label">{name}</div>
#             <div class="summary-value">{round(curr_val, 0):,}</div>
#             <div class="summary-delta {delta_class}">{symbol}{round(diff, 1)}% vs D-1</div>
#             <div class="status-tag" style="background-color: {status_color};">{status_label}</div>
#         </div>
#         """, unsafe_allow_html=True)

# st.write("")







# =========================================================
# 🌍 GLOBAL EXECUTIVE SUMMARY CARDS
# =========================================================



# 1. Summary Cards (Multi-Source High-Level Dashboard)
prev_day = selected_day - timedelta(days=1)

# فلاتر اليوم الحالي واليوم السابق للأربع خدمات (كل واحدة من الداتا فريم بتاعتها)
curr_rch = df_daily[df_daily["RCH_DAY"] == selected_day]
prev_rch = df_daily[df_daily["RCH_DAY"] == prev_day]

curr_data = DATA_PER_DAY_HIST[DATA_PER_DAY_HIST["data_usage_day"] == selected_day]
prev_data = DATA_PER_DAY_HIST[DATA_PER_DAY_HIST["data_usage_day"] == prev_day]

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
    curr_row = df_daily[df_daily["RCH_DAY"] == selected_day]
    prev_row = df_daily[df_daily["RCH_DAY"] == prev_day]


    # 🛡️ حارس البوابة الذكي (الفرملة المبكرة):
    if curr_row.empty or prev_row.empty:
        # لو أي يوم فيهم فاضي، هيطلع الرسالة ويقفل الأبلكيشن في ثانية
        st.warning(f"⚠️ No data available for the selected date: **{selected_day.date()}**. Please check your data source or select another day.")
        st.stop() # 🪄 الفرملة السحرية.. الكود اللي تحت مستحيل يشتغل ومستحيل يضرب إيرور!

    kpis_config = [
        ("Recharge Users", "DAILY_UNQ_SUBS"),
        ("Transactions", "DAILY_TRX_COUNTS"),
        ("Recharge Amount", "DAILY_TRX_AMOUNTS"),
        ("Avg Recharge", "avg_recharge")
    ]

    if not curr_row.empty and not prev_row.empty:
        cols = st.columns(4)
        for i, (name, col_name) in enumerate(kpis_config):
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
            f_tab_overall()
            
        # 🚫 العكس: لو مش أدمن (نتورك يوزر مثلاً).. اظهر له الأيرور بس والفانكشن مش هترن
        if st.session_state.get("user_role") != "admin":
            st.error("❌ Wrong Password / No Permission to view this tab.")


    with tab_alerts:
        # 🔑 لو أدمن.. رن الفانكشن القديمة علطول ومفيش أيرورز هتظهر
        if st.session_state.get("user_role") == "admin":
            f_tab_alerts()
            
        # 🚫 العكس: لو مش أدمن (نتورك يوزر مثلاً).. اظهر له الأيرور بس والفانكشن مش هترن
        if st.session_state.get("user_role") != "admin":
            st.error("❌ Wrong Password / No Permission to view this tab.")



    with tab_alerts_v2:
        # 🔑 لو أدمن.. رن الفانكشن القديمة علطول ومفيش أيرورز هتظهر
        if st.session_state.get("user_role") == "admin":
            f_tab_alerts_v2()
            
        # 🚫 العكس: لو مش أدمن (نتورك يوزر مثلاً).. اظهر له الأيرور بس والفانكشن مش هترن
        if st.session_state.get("user_role") != "admin":
            st.error("❌ Wrong Password / No Permission to view this tab.")



    with tab_ibro:
        # 🔑 لو أدمن.. رن الفانكشن القديمة علطول ومفيش أيرورز هتظهر
        if st.session_state.get("user_role") == "admin":
            f_tab_ibro()
            
        # 🚫 العكس: لو مش أدمن (نتورك يوزر مثلاً).. اظهر له الأيرور بس والفانكشن مش هترن
        if st.session_state.get("user_role") != "admin":
            st.error("❌ Wrong Password / No Permission to view this tab.")
        
        

    with tab_network:
        # هنا بتمرر اسم متغير التاريخ الموحد بتاع الأبلكيشن بتاعك بين القوسين
        # (لو التاريخ عندك متخزن في متغير اسمه selected_date مثلاً، اكتبه مكانه)
        f_tab_network(selected_day)









# =========================================================
# 📶 DATA TAB
# =========================================================

with main_tab_data:
    st.info("📶 Data Monitoring Module - Coming Soon")

# =========================================================
# 📞 VOICE TAB
# =========================================================

with main_tab_voice:
    st.info("📞 Voice Monitoring Module - Coming Soon")



















# =========================================================
# 💰 ORANGE CASH TAB
# =========================================================

# with main_tab_oc:
#     st.info("💰 Orange Cash Monitoring Module - Coming Soon")






#==========OC ALERTS


# =========================================================
# 3. ALERTS LOGIC FUNCTIONS
# =========================================================


# def OC_get_alerts_logic(OC_SERVICES_PER_DAY_HIST, target_date):
#     prev_date = target_date - timedelta(days=1)
#     curr = OC_SERVICES_PER_DAY_HIST[OC_SERVICES_PER_DAY_HIST["oc_usage_day"] == target_date]
#     prev = OC_SERVICES_PER_DAY_HIST[OC_SERVICES_PER_DAY_HIST["oc_usage_day"] == prev_date]
    
#     if curr.empty or prev.empty: return pd.DataFrame()

#     # # تعديل: تعريف كافة الاحتمالات (فردي، ثنائي، ثلاثي)
#     # combinations = [ 
#     #     ["RCH_TYPE"], ["recharge_type_description"], ["RCH_HOUR_TIERS"],
#     #     ["RCH_TYPE", "recharge_type_description"],
#     #     ["RCH_TYPE", "RCH_HOUR_TIERS"],
#     #     ["recharge_type_description", "RCH_HOUR_TIERS"],
#     #     ["RCH_TYPE", "recharge_type_description", "RCH_HOUR_TIERS"]
#     # ]


#     # تعديل: تعريف كافة الاحتمالات (فردي، ثنائي، ثلاثي)
#     combinations = [  ["service_group"] ]
        
    
#     m_map = {"total_oc_trx_amts": "Amount", "total_oc_trx_cnts": "Transactions", "total_unq_subs": "Subscribers"}
#     results = []

#     for cols in combinations:
#         curr_g = curr.groupby(cols)[["total_oc_trx_cnts", "total_oc_trx_amts", "total_unq_subs"]].sum().reset_index()
#         prev_g = prev.groupby(cols)[["total_oc_trx_cnts", "total_oc_trx_amts", "total_unq_subs"]].sum().reset_index()
        
#         merged = curr_g.merge(prev_g, on=cols, suffixes=('_c', '_p'))
        
#         for _, row in merged.iterrows():
#             segment_name = " | ".join([str(row[c]) for c in cols])
#             for col_key, name in m_map.items():
#                 p_val = row[f"{col_key}_p"]
#                 c_val = row[f"{col_key}_c"]
#                 if p_val > 0:
#                     growth = ((c_val - p_val) / p_val) * 100
#                     abs_g = abs(growth)
                    
#                     if abs_g >= 3: # الحد الأدنى للظهور
#                         # تطبيق سلم التنبيهات الجديد الخاص بك
#                         if abs_g < 5: level = "Normal"
#                         elif 5 <= abs_g < 10: level = "Watch"
#                         elif 10 <= abs_g < 20: level = "Warning"
#                         else: level = "Critical"
                        
#                         results.append({
#                             "segment": segment_name,
#                             "metric": name, 
#                             "growth": round(growth, 1),
#                             "current_val": round(c_val, 1),
#                             "previous_val": round(p_val, 1),
#                             "level": level, 
#                             "direction": "Drop" if growth < 0 else "Up"
#                         })
#     return pd.DataFrame(results)



# # =========================================================
# # 3. UI RENDERERS ALERTS
# # =========================================================

# def OC_show_alerts(data, is_drop):
#     # إضافة Normal للتبويبات حسب السلم الجديد
#     levels = ["Critical", "Warning", "Watch", "Normal"]
#     tabs = st.tabs([f"{l} ({len(data[data['level']==l])})" for l in levels])
    
#     for i, l in enumerate(levels):
#         with tabs[i]:
#             subset = data[data["level"] == l]
#             if subset.empty: 
#                 st.info(f"No {l} alerts found.")
#             else:
#                 for _, r in subset.iterrows():
#                     color = "#DA3633" if is_drop else "#238636"
#                     arrow = "▼" if is_drop else "▲"
                    
#                     st.markdown(f"""
#                     <div class="alert-card {'drop-card' if is_drop else 'up-card'}">
#                         <span style="float:right; color:{color}; font-weight:800; font-size:18px;">
#                             {arrow} {abs(r['growth'])}%
#                         </span>
#                         <div style="font-weight:700; margin-bottom:5px;">{r['segment']}</div>
#                         <div style="font-size:13px; color:#8B949E; margin-bottom:8px;">
#                             Current: <b>{r['current_val']:,}</b> | Previous: <b>{r['previous_val']:,}</b>
#                         </div>
#                         <span class="metric-tag">Metric: {r['metric']}</span>
#                     </div>
#                     """, unsafe_allow_html=True)





# # ----------------- TAB 2: ALERTS -----------------



# def OC_f_tab_alerts():
#     alerts_df = OC_get_alerts_logic(OC_SERVICES_PER_DAY_HIST, selected_day)
    
#     if alerts_df.empty:
#         st.success("✅ System is Stable - All metrics within normal range.")
#     else:
#         st.warning(f"⚠️ System detected {len(alerts_df)} deviations for the selected date.")
        
#         drops = alerts_df[alerts_df["direction"] == "Drop"].sort_values("growth")
#         ups = alerts_df[alerts_df["direction"] == "Up"].sort_values("growth", ascending=False)

#         st.markdown(f"""
#         <div class="alert-summary-container">
#             <div style="text-align:center; flex:1;">
#                 <span style="font-size:38px; font-weight:800; color:#DA3633;">{len(drops)}</span><br/>
#                 <small style="color:#8B949E;">DROPS DETECTED</small>
#             </div>
#             <div style="text-align:center; flex:1; border-left:1px solid #30363D;">
#                 <span style="font-size:38px; font-weight:800; color:#238636;">{len(ups)}</span><br/>
#                 <small style="color:#8B949E;">UPS DETECTED</small>
#             </div>
#         </div>
#         """, unsafe_allow_html=True)

#         t_drops_main, t_ups_main = st.tabs(["📉 DROPS ANALYSIS", "📈 UPS ANALYSIS"])
        
#         with t_drops_main:
#             OC_show_alerts(drops, True)
#         with t_ups_main:
#             OC_show_alerts(ups, False) 

















#================ALERTS FN V2





# OC_SERVICES_PER_DAY_HIST_ALERT = OC_SERVICES_PER_DAY_HIST.groupby([ "oc_usage_day" , "service_group"])[["total_oc_trx_cnts", "total_oc_trx_amts", "total_unq_subs"]].sum().reset_index()

# # =========================================================
# # 3. ALERTS LOGIC FUNCTIONS (المطبخ الخلفي مع الـ 3 أبعاد)
# # =========================================================

# def OC_get_alerts_logic(OC_SERVICES_PER_DAY_HIST_ALERT, target_date, comparison_mode="Yesterday (D-1)"):
#     # داتا اليوم الحالي
#     curr = OC_SERVICES_PER_DAY_HIST_ALERT[OC_SERVICES_PER_DAY_HIST_ALERT["oc_usage_day"] == target_date]
#     if curr.empty: return pd.DataFrame()

#     # 1. المطبخ الخلفي: تحديد جدول الـ Baseline (prev) بناءً على المقارنة المختارة
#     if comparison_mode == "Yesterday (D-1)":
#         prev_date = target_date - timedelta(days=1)
#         prev = OC_SERVICES_PER_DAY_HIST_ALERT[OC_SERVICES_PER_DAY_HIST_ALERT["oc_usage_day"] == prev_date]
#         if prev.empty: return pd.DataFrame()
        
#     elif comparison_mode == "Same Day - Last 4 Weeks Avg":
#         # حساب تواريخ نفس اليوم في الـ 4 أسابيع الماضية
#         past_dates = [target_date - timedelta(weeks=i) for i in range(1, 5)]
#         past_data = OC_SERVICES_PER_DAY_HIST_ALERT[OC_SERVICES_PER_DAY_HIST_ALERT["oc_usage_day"].isin(past_dates)]
#         if past_data.empty: return pd.DataFrame()
#         # عمل Groupby وحساب المتوسط (mean) ليكون هو الـ Baseline
#         prev = past_data.groupby(["service_group"])[["total_oc_trx_cnts", "total_oc_trx_amts", "total_unq_subs"]].mean().reset_index()
        
#     elif comparison_mode == "Same Month Phase - Last 4 Months Avg":
#         # فرضاً إن الدالة دي متوفرة في الكود الماستر عندك وتسمى get_month_phase
#         try:
#             curr_phase = get_month_phase(target_date) # دالة مرحلة الشهر اللي عندك فوق
#             # فلترة جدول الهيستري بالكامل ليأخذ الأيام التي تقع في نفس الـ Phase لآخر 4 شهور
#             # (الكود بيرجع بالزمن ويسحب داتا الـ Phase المتطابقة)
#             start_history = target_date - timedelta(days=120)
#             past_phase_data = OC_SERVICES_PER_DAY_HIST_ALERT[
#                 (OC_SERVICES_PER_DAY_HIST_ALERT["oc_usage_day"] >= start_history) & 
#                 (OC_SERVICES_PER_DAY_HIST_ALERT["oc_usage_day"] < target_date)
#             ].copy()
            
#             # فلترة الأيام اللي ليها نفس الـ Phase (ونفس اسم اليوم إذا كنت تفضل ذلك)
#             past_phase_data["phase"] = past_phase_data["oc_usage_day"].apply(get_month_phase)
#             past_phase_data["day_name"] = pd.to_datetime(past_phase_data["oc_usage_day"]).dt.day_name()
#             target_day_name = pd.to_datetime(target_date).dt.day_name()
            
#             filtered_history = past_phase_data[
#                 (past_phase_data["phase"] == curr_phase) & 
#                 (past_phase_data["day_name"] == target_day_name)
#             ]
#             if filtered_history.empty: return pd.DataFrame()
            
#             # حساب المتوسط
#             prev = filtered_history.groupby(["service_group"])[["total_oc_trx_cnts", "total_oc_trx_amts", "total_unq_subs"]].mean().reset_index()
#         except:
#             # Fallback في حالة حدوث أي خطأ في ربط دالة الـ Phase يرجع لـ امبارح منعا لضرب الشاشة
#             prev_date = target_date - timedelta(days=1)
#             prev = OC_SERVICES_PER_DAY_HIST_ALERT[OC_SERVICES_PER_DAY_HIST_ALERT["oc_usage_day"] == prev_date]
#             if prev.empty: return pd.DataFrame()

#     # 2. اللوجيك الأصلي بتاعك للف وبناء الـ Metrics (فابريكا بدون تغيير)
#     combinations = [ ["service_group"] ]
#     m_map = {"total_oc_trx_amts": "Amount", "total_oc_trx_cnts": "Transactions", "total_unq_subs": "Subscribers"}
#     results = []

#     for cols in combinations:
#         # لو كنا شغالين أسبوعي أو شهري فالـ prev معمول لها groupby بالفعل، فنهندل ده بسلاسة
#         if "oc_usage_day" in prev.columns:
#             prev_g = prev.groupby(cols)[["total_oc_trx_cnts", "total_oc_trx_amts", "total_unq_subs"]].sum().reset_index()
#         else:
#             prev_g = prev[cols + ["total_oc_trx_cnts", "total_oc_trx_amts", "total_unq_subs"]]
            
#         curr_g = curr.groupby(cols)[["total_oc_trx_cnts", "total_oc_trx_amts", "total_unq_subs"]].sum().reset_index()
#         merged = curr_g.merge(prev_g, on=cols, suffixes=('_c', '_p'))
        
#         for _, row in merged.iterrows():
#             segment_name = " | ".join([str(row[c]) for c in cols])
#             for col_key, name in m_map.items():
#                 p_val = row[f"{col_key}_p"]
#                 c_val = row[f"{col_key}_c"]
#                 if p_val > 0:
#                     growth = ((c_val - p_val) / p_val) * 100
#                     abs_g = abs(growth)
                    
#                     if abs_g >= 3: # الحد الأدنى الأصلي بتاعك للظهور
#                         if abs_g < 5: level = "Normal"
#                         elif 5 <= abs_g < 10: level = "Watch"
#                         elif 10 <= abs_g < 20: level = "Warning"
#                         else: level = "Critical"
                        
#                         results.append({
#                             "segment": segment_name,
#                             "metric": name, 
#                             "growth": round(growth, 1),
#                             "current_val": round(c_val, 1),
#                             "previous_val": round(p_val, 1),
#                             "level": level, 
#                             "direction": "Drop" if growth < 0 else "Up"
#                         })
#     return pd.DataFrame(results)


# # =========================================================
# # 3. UI RENDERERS ALERTS (تظل مستقرة كما هي تماماً)
# # =========================================================

# def OC_show_alerts(data, is_drop):
#     levels = ["Critical", "Warning", "Watch", "Normal"]
#     tabs = st.tabs([f"{l} ({len(data[data['level']==l])})" for l in levels])
    
#     for i, l in enumerate(levels):
#         with tabs[i]:
#             subset = data[data["level"] == l]
#             if subset.empty: 
#                 st.info(f"No {l} alerts found.")
#             else:
#                 for _, r in subset.iterrows():
#                     color = "#DA3633" if is_drop else "#238636"
#                     arrow = "▼" if is_drop else "▲"
                    
#                     st.markdown(f"""
#                     <div class="alert-card {'drop-card' if is_drop else 'up-card'}">
#                         <span style="float:right; color:{color}; font-weight:800; font-size:18px;">
#                             {arrow} {abs(r['growth'])}%
#                         </span>
#                         <div style="font-weight:700; margin-bottom:5px;">{r['segment']}</div>
#                         <div style="font-size:13px; color:#8B949E; margin-bottom:8px;">
#                             Current: <b>{r['current_val']:,}</b> | Previous: <b>{r['previous_val']:,}</b>
#                         </div>
#                         <span class="metric-tag">Metric: {r['metric']}</span>
#                     </div>
#                     """, unsafe_allow_html=True)


# # =========================================================
# # 3. MASTER ALERTS TAB (الدالة الكبيرة مع الفلاتر والترتيب الحديد)
# # =========================================================

# def OC_f_tab_alerts():
#     # 🟢 خطوة 1: رسم فلاتر التحكم شياكة جنب بعض في الأعلى مع الديفولتس
#     col_f1, col_f2 = st.columns(2)
    
#     with col_f1:
#         selected_comparison = st.selectbox(
#             "🎯 Select Baseline Comparison:",
#             options=["Yesterday (D-1)", "Same Day - Last 4 Weeks Avg", "Same Month Phase - Last 4 Months Avg"],
#             index=0, # الديفولت يفتح على امبارح أوتوماتيك
#             key="oc_baseline_comparison_filter"
#         )
        
#     with col_f2:
#         selected_metric = st.selectbox(
#             "🔍 View Alerts By Metric Type:",
#             options=["All", "Amount", "Transactions", "Subscribers"],
#             index=0, # الديفولت يفتح على All للـ 3 مؤشرات معاً
#             key="oc_metric_type_filter"
#         )
        
#     # نداء دالة اللوجيك مع تمرير البعد المختار ديناميكياً
#     alerts_df = OC_get_alerts_logic(OC_SERVICES_PER_DAY_HIST_ALERT, selected_day, comparison_mode=selected_comparison)
    
#     if alerts_df.empty:
#         st.success("✅ System is Stable - All metrics within normal range.")
#     else:
#         st.warning(f"⚠️ System detected {len(alerts_df)} deviations using [{selected_comparison}].")
        
#         # 🟢 خطوة 2: فصل الـ Drops والـ Ups الإجمالية من أجل الـ Counters الثابتة (All)
#         all_drops = alerts_df[alerts_df["direction"] == "Drop"]
#         all_ups = alerts_df[alerts_df["direction"] == "Up"]

#         # رسم الـ Summary Container بالعدد الإجمالي الصافي للسيستم
#         st.markdown(f"""
#         <div class="alert-summary-container">
#             <div style="text-align:center; flex:1;">
#                 <span style="font-size:38px; font-weight:800; color:#DA3633;">{len(all_drops)}</span><br/>
#                 <small style="color:#8B949E;">TOTAL DROPS</small>
#             </div>
#             <div style="text-align:center; flex:1; border-left:1px solid #30363D;">
#                 <span style="font-size:38px; font-weight:800; color:#238636;">{len(all_ups)}</span><br/>
#                 <small style="color:#8B949E;">TOTAL UPS</small>
#             </div>
#         </div>
#         """, unsafe_allow_html=True)

#         # 🟢 خطوة 3: تطبيق الفلترة على الكروت بناءً على نوع الـ Metric المختار
#         if selected_metric != "All":
#             filtered_drops = all_drops[all_drops["metric"] == selected_metric]
#             filtered_ups = all_ups[all_ups["metric"] == selected_metric]
#         else:
#             filtered_drops = all_drops
#             filtered_ups = all_ups

#         # 🟢 خطوة 4: الترتيب الحديد (من الكبير للصغير بناءً على حجم الانحراف)
#         # للـ Drops: بنرتب تصاعدي لأن الأرقام سالبة، فالسالب الكبير جداً (زي -50%) بيطلع فوق الأول كأخطر انحراف
#         final_drops = filtered_drops.sort_values(by="growth", ascending=True)
#         # للـ Ups: بنرتب تنازلي لأن الأرقام موجبة، فالرقم الكبير جداً (زي +80%) بيطلع فوق الأول كأعلى قفزة
#         final_ups = filtered_ups.sort_values(by="growth", ascending=False)

#         # فرز وعرض التابات الكبيرة
#         t_drops_main, t_ups_main = st.tabs(["📉 DROPS ANALYSIS", "📈 UPS ANALYSIS"])
        
#         with t_drops_main:
#             OC_show_alerts(final_drops, True)
#         with t_ups_main:
#             OC_show_alerts(final_ups, False)












#===============LAST VERSION



# =========================================================
# 3. ALERTS LOGIC FUNCTIONS (المطبخ الخلفي المطور)
# =========================================================

# def OC_get_alerts_logic(OC_SERVICES_PER_DAY_HIST, target_date, comparison_mode="Yesterday (D-1)"):
#     # 🟢 خطوة 1: التجميع المسبق النظيف (Pre-aggregation) لمنع خفض المتوسطات
#     # بنجمع الداتا على مستوى اليوم والخدمة أولاً بالـ Sum عشان نفرشها صح
#     clean_hist = OC_SERVICES_PER_DAY_HIST.groupby(["oc_usage_day", "service_group"])[
#         ["total_oc_trx_cnts", "total_oc_trx_amts", "total_unq_subs"]
#     ].sum().reset_index()

#     # داتا اليوم الحالي من الجدول النظيف
#     curr = clean_hist[clean_hist["oc_usage_day"] == target_date]
#     if curr.empty: 
#         return pd.DataFrame(), "No data available for today."

#     compared_dates_str = ""

#     # 🟢 خطوة 2: تحديد الـ Baseline (prev) والتواريخ بناءً على وضع المقارنة
#     if comparison_mode == "Yesterday (D-1)":
#         prev_date = target_date - timedelta(days=1)
#         prev_day_name = pd.to_datetime(prev_date).day_name()
#         compared_dates_str = f"({prev_day_name}: {prev_date.strftime('%Y-%m-%d')})"
        
#         prev = clean_hist[clean_hist["oc_usage_day"] == prev_date]
#         if prev.empty: return pd.DataFrame(), f"No data found for yesterday {compared_dates_str}"
        
#     elif comparison_mode == "Same Day - Last 4 Weeks Avg":
#         # حساب تواريخ آخر 4 أسابيع لورا بالملي (1, 2, 3, 4)
#         past_dates = [target_date - timedelta(weeks=i) for i in range(1, 5)]
#         compared_dates_str = " | ".join([d.strftime('%Y-%m-%d') for d in past_dates])
#         compared_dates_str = f"({compared_dates_str})"
        
#         past_data = clean_hist[clean_hist["oc_usage_day"].isin(past_dates)]
#         if past_data.empty: return pd.DataFrame(), f"No history found for weeks: {compared_dates_str}"
        
#         # بما أن الداتا مفرودة (يوم/خدمة)، الـ mean هنا هيطلع صح 100% ومطابق للمانيوال
#         prev = past_data.groupby(["service_group"])[["total_oc_trx_cnts", "total_oc_trx_amts", "total_unq_subs"]].mean().reset_index()
        
#     elif comparison_mode == "Same Month Phase - Last 4 Months Avg":
#         try:
#             curr_phase = get_month_phase(target_date) # دالة الـ Phase اللي عندك فوق
#             target_day_name = pd.to_datetime(target_date).day_name()
            
#             # فتح نافذة زمنية 120 يوم لورا كصنارة تجميع
#             start_history = target_date - timedelta(days=120)
#             past_phase_data = clean_hist[
#                 (clean_hist["oc_usage_day"] >= start_history) & 
#                 (clean_hist["oc_usage_day"] < target_date)
#             ].copy()
            
#             # تطبيق الفلترة الذكية بناءً على الـ Phase واسم اليوم
#             past_phase_data["phase"] = past_phase_data["oc_usage_day"].apply(get_month_phase)
#             past_phase_data["day_name"] = pd.to_datetime(past_phase_data["oc_usage_day"]).day_name()
            
#             filtered_history = past_phase_data[
#                 (past_phase_data["phase"] == curr_phase) & 
#                 (past_phase_data["day_name"] == target_day_name)
#             ]
            
#             if filtered_history.empty:
#                 return pd.DataFrame(), f"No matching month phases found in the last 4 months."
            
#             # استخراج التواريخ الفريدة اللي دخلت في الحسبة لعرضها للمدير
#             unique_dates = filtered_history["oc_usage_day"].unique()
#             compared_dates_str = " | ".join([pd.to_datetime(d).strftime('%Y-%m-%d') for d in unique_dates])
#             compared_dates_str = f"({compared_dates_str})"
            
#             # حساب المتوسط الصافي
#             prev = filtered_history.groupby(["service_group"])[["total_oc_trx_cnts", "total_oc_trx_amts", "total_unq_subs"]].mean().reset_index()
            
#         except:
#             # Fallback أمان في حالة حدوث أي خطأ في دالة الـ Phase الخارجية
#             prev_date = target_date - timedelta(days=1)
#             compared_dates_str = f"({pd.to_datetime(prev_date).strftime('%Y-%m-%d')})"
#             prev = clean_hist[clean_hist["oc_usage_day"] == prev_date]
#             if prev.empty: return pd.DataFrame(), "No data available."

#     # 3. اللوجيك الأصلي لبناء الـ Metrics (فابريكا شغال حديد على الداتا النظيفة)
#     combinations = [ ["service_group"] ]
#     m_map = {"total_oc_trx_amts": "Amount", "total_oc_trx_cnts": "Transactions", "total_unq_subs": "Subscribers"}
#     results = []

#     for cols in combinations:
#         # الداتا أوريدي مفرودة ونظيفة فمش هتضرب من الـ sum ولا الـ groupby هنا
#         prev_g = prev.groupby(cols)[["total_oc_trx_cnts", "total_oc_trx_amts", "total_unq_subs"]].sum().reset_index()
#         curr_g = curr.groupby(cols)[["total_oc_trx_cnts", "total_oc_trx_amts", "total_unq_subs"]].sum().reset_index()
        
#         merged = curr_g.merge(prev_g, on=cols, suffixes=('_c', '_p'))
        
#         for _, row in merged.iterrows():
#             segment_name = " | ".join([str(row[c]) for c in cols])
#             for col_key, name in m_map.items():
#                 p_val = row[f"{col_key}_p"]
#                 c_val = row[f"{col_key}_c"]
#                 if p_val > 0:
#                     growth = ((c_val - p_val) / p_val) * 100
#                     abs_g = abs(growth)
                    
#                     if abs_g >= 3:
#                         if abs_g < 5: level = "Normal"
#                         elif 5 <= abs_g < 10: level = "Watch"
#                         elif 10 <= abs_g < 20: level = "Warning"
#                         else: level = "Critical"
                        
#                         results.append({
#                             "segment": segment_name,
#                             "metric": name, 
#                             "growth": round(growth, 1),
#                             "current_val": round(c_val, 1),
#                             "previous_val": round(p_val, 1),
#                             "level": level, 
#                             "direction": "Drop" if growth < 0 else "Up"
#                         })
                        
#     return pd.DataFrame(results), compared_dates_str






def OC_get_alerts_logic(OC_SERVICES_PER_DAY_HIST, target_date, comparison_mode="Yesterday (D-1)"):
    # 🟢 خطوة 1: التجميع المسبق النظيف (Pre-aggregation) لضمان دقة المتوسطات (الـ 3 هتبقى 280)
    clean_hist = OC_SERVICES_PER_DAY_HIST.groupby(["oc_usage_day", "service_group"])[
        ["total_oc_trx_cnts", "total_oc_trx_amts", "total_unq_subs"]
    ].sum().reset_index()

    # ضمان إن عمود التاريخ في الـ DataFrame نوعه datetime صافي 100%
    clean_hist["oc_usage_day"] = pd.to_datetime(clean_hist["oc_usage_day"])
    target_dt = pd.to_datetime(target_date)

    # داتا اليوم الحالي من الجدول النظيف
    curr = clean_hist[clean_hist["oc_usage_day"] == target_dt]
    if curr.empty: 
        return pd.DataFrame(), "No data available for today."

    compared_dates_str = ""

    # 🟢 خطوة 2: تحديد الـ Baseline (prev) والتواريخ بناءً على المقارنة المختارة
    if comparison_mode == "Yesterday (D-1)":
        prev_date = target_dt - timedelta(days=1)
        prev_day_name = prev_date.day_name()
        compared_dates_str = f"({prev_day_name}: {prev_date.strftime('%Y-%m-%d')})"
        
        prev = clean_hist[clean_hist["oc_usage_day"] == prev_date]
        if prev.empty: return pd.DataFrame(), f"No data found for yesterday {compared_dates_str}"
        
    elif comparison_mode == "Same Day - Last 4 Weeks Avg":
        # حساب تواريخ آخر 4 أسابيع لورا بالملي
        past_dates = [target_dt - timedelta(weeks=i) for i in range(1, 5)]
        compared_dates_str = " | ".join([d.strftime('%Y-%m-%d') for d in past_dates])
        compared_dates_str = f"({compared_dates_str})"
        
        past_data = clean_hist[clean_hist["oc_usage_day"].isin(past_dates)]
        if past_data.empty: return pd.DataFrame(), f"No history found for weeks: {compared_dates_str}"
        
        # حساب المتوسط الصافي النظيف
        prev = past_data.groupby(["service_group"])[["total_oc_trx_cnts", "total_oc_trx_amts", "total_unq_subs"]].mean().reset_index()
        
    elif comparison_mode == "Same Month Phase - Last 4 Months Avg":
        try:
            # هنا بنباصي لـ دالتك target_dt كـ datetime object صريح عشان يقرأ منه .day بأمان
            curr_phase = get_month_phase(target_dt) 
            target_day_name = target_dt.day_name()
            
            # فتح نافذة زمنية 130 يوم لورا كصنارة لتغطية الـ 4 شهور
            start_history = target_dt - timedelta(days=130)
            past_phase_data = clean_hist[
                (clean_hist["oc_usage_day"] >= start_history) & 
                (clean_hist["oc_usage_day"] < target_dt)
            ].copy()
            
            # 🌟 السحر هنا: بنمرر التواريخ لدالتك كـ Datetime Object صريح عشان الـ .day تشتغل فابريكا
            past_phase_data["phase"] = past_phase_data["oc_usage_day"].apply(get_month_phase)
            past_phase_data["day_name"] = past_phase_data["oc_usage_day"].dt.day_name()
            
            # الفلترة الذكية: نفس الـ Phase ونفس اسم اليوم (مثلاً: الأحد أول الشهر)
            filtered_history = past_phase_data[
                (past_phase_data["phase"] == curr_phase) & 
                (past_phase_data["day_name"] == target_day_name)
            ]
            
            if filtered_history.empty:
                # خط دفاع أول (Fallback أمان لو ملقاش داتا يرجع لآخر 4 أسابيع بدل ما يعطل)
                past_dates = [target_dt - timedelta(weeks=i) for i in range(1, 5)]
                compared_dates_str = " | ".join([d.strftime('%Y-%m-%d') for d in past_dates])
                fallback_data = clean_hist[clean_hist["oc_usage_day"].isin(past_dates)]
                return fallback_data.groupby(["service_group"])[["total_oc_trx_cnts", "total_oc_trx_amts", "total_unq_subs"]].mean().reset_index(), f"Fallback to Last 4 Weeks: ({compared_dates_str})"
            
            # استخراج التواريخ الفريدة المفرودة وعرضها للمدير في السطر الأزرق
            unique_dates = sorted(filtered_history["oc_usage_day"].unique())
            compared_dates_str = " | ".join([pd.to_datetime(d).strftime('%Y-%m-%d') for d in unique_dates])
            compared_dates_str = f"({compared_dates_str})"
            
            # حساب المتوسط الصافي الحقيقي لآخر 4 شهور متطابقة
            prev = filtered_history.groupby(["service_group"])[["total_oc_trx_cnts", "total_oc_trx_amts", "total_unq_subs"]].mean().reset_index()
            
        except Exception as e:
            # لو حصل أي خطأ، بنطبع تفاصيله في السطر الأزرق عشان نلمحه علطول
            prev_date = target_dt - timedelta(days=1)
            compared_dates_str = f"(Error Fallback D-1: {prev_date.strftime('%Y-%m-%d')} | Details: {str(e)[:40]})"
            prev = clean_hist[clean_hist["oc_usage_day"] == prev_date]

    # 3. اللوجيك الأصلي لبناء الـ Metrics وحساب الـ Growth (فابريكا زي ما هو)
    combinations = [ ["service_group"] ]
    m_map = {"total_oc_trx_amts": "Amount", "total_oc_trx_cnts": "Transactions", "total_unq_subs": "Subscribers"}
    results = []

    for cols in combinations:
        prev_g = prev.groupby(cols)[["total_oc_trx_cnts", "total_oc_trx_amts", "total_unq_subs"]].sum().reset_index()
        curr_g = curr.groupby(cols)[["total_oc_trx_cnts", "total_oc_trx_amts", "total_unq_subs"]].sum().reset_index()
        
        merged = curr_g.merge(prev_g, on=cols, suffixes=('_c', '_p'))
        
        for _, row in merged.iterrows():
            segment_name = " | ".join([str(row[c]) for c in cols])
            for col_key, name in m_map.items():
                p_val = row[f"{col_key}_p"]
                c_val = row[f"{col_key}_c"]
                if p_val > 0:
                    growth = ((c_val - p_val) / p_val) * 100
                    abs_g = abs(growth)
                    
                    if abs_g >= 3:
                        if abs_g < 5: level = "Normal"
                        elif 5 <= abs_g < 10: level = "Watch"
                        elif 10 <= abs_g < 20: level = "Warning"
                        else: level = "Critical"
                        
                        results.append({
                            "segment": segment_name,
                            "metric": name, 
                            "growth": round(growth, 1),
                            "current_val": round(c_val, 1),
                            "previous_val": round(p_val, 1),
                            "level": level, 
                            "direction": "Drop" if growth < 0 else "Up"
                        })
                        
    return pd.DataFrame(results), compared_dates_str





# =========================================================
# 3. UI RENDERERS ALERTS (مستقرة وفابريكا بدون تعديل)
# =========================================================

def OC_show_alerts(data, is_drop):
    levels = ["Critical", "Warning", "Watch", "Normal"]
    tabs = st.tabs([f"{l} ({len(data[data['level']==l])})" for l in levels])
    
    for i, l in enumerate(levels):
        with tabs[i]:
            subset = data[data["level"] == l]
            if subset.empty: 
                st.info(f"No {l} alerts found.")
            else:
                for _, r in subset.iterrows():
                    color = "#DA3633" if is_drop else "#238636"
                    arrow = "▼" if is_drop else "▲"
                    
                    st.markdown(f"""
                    <div class="alert-card {'drop-card' if is_drop else 'up-card'}">
                        <span style="float:right; color:{color}; font-weight:800; font-size:18px;">
                            {arrow} {abs(r['growth'])}%
                        </span>
                        <div style="font-weight:700; margin-bottom:5px;">{r['segment']}</div>
                        <div style="font-size:13px; color:#8B949E; margin-bottom:8px;">
                            Current: <b>{r['current_val']:,}</b> | Previous: <b>{r['previous_val']:,}</b>
                        </div>
                        <span class="metric-tag">Metric: {r['metric']}</span>
                    </div>
                    """, unsafe_allow_html=True)





# =========================================================
# 3. MASTER ALERTS TAB (لوحة التحكم مع الشفافية الكاملة والترتيب)
# =========================================================

def OC_f_tab_alerts():
    # 🟢 خطوة 1: رسم قائمة التحكم العلوية شياكة مع وضع الديفولتس الحديد
    col_f1, col_f2 = st.columns(2)
    
    with col_f1:
        selected_comparison = st.selectbox(
            "🎯 Select Baseline Comparison:",
            options=["Yesterday (D-1)", "Same Day - Last 4 Weeks Avg", "Same Month Phase - Last 4 Months Avg"],
            index=0, # الديفولت يفتح على امبارح
            key="oc_baseline_comparison_filter"
        )
        
    with col_f2:
        selected_metric = st.selectbox(
            "🔍 View Alerts By Metric Type:",
            options=["All", "Amount", "Transactions", "Subscribers"],
            index=0, # الديفولت يفتح على All لروية الصورة كاملة
            key="oc_metric_type_filter"
        )
        
    # استدعاء دالة اللوجيك واستقبال الجدول الصافي + نص التواريخ التوضيحي
    alerts_df, date_context = OC_get_alerts_logic(OC_SERVICES_PER_DAY_HIST, selected_day, comparison_mode=selected_comparison)
    
    # 🟢 خطوة 2: طباعة الجملة التوضيحية الذكية (Contextual Subtitle) بالتواريخ والمؤشرات الصريحة
    metric_display = "All metrics (Amount, Transactions, Subscribers)" if selected_metric == "All" else f"'{selected_metric}' metric only"
    st.markdown(f"""
    <p style="color: #8B949E; font-size: 14px; margin-top: -10px; margin-bottom: 20px; font-style: italic;">
        📊 <b>Current View:</b> Reviewing {metric_display} compared by <b>{selected_comparison}</b> <span style="color: #58A6FF;">{date_context}</span>
    </p>
    """, unsafe_allow_html=True)

    if alerts_df.empty:
        st.success("✅ System is Stable - All metrics within normal range.")
    else:
        # فصل البيانات من أجل العدادات الإجمالية (تظل ثابتة كاشفة للسيستم بالكامل)
        all_drops = alerts_df[alerts_df["direction"] == "Drop"]
        all_ups = alerts_df[alerts_df["direction"] == "Up"]

        # رسم شريط العدادات الإجمالية الكبير فوق
        st.markdown(f"""
        <div class="alert-summary-container">
            <div style="text-align:center; flex:1;">
                <span style="font-size:38px; font-weight:800; color:#DA3633;">{len(all_drops)}</span><br/>
                <small style="color:#8B949E;">TOTAL DROPS</small>
            </div>
            <div style="text-align:center; flex:1; border-left:1px solid #30363D;">
                <span style="font-size:38px; font-weight:800; color:#238636;">{len(all_ups)}</span><br/>
                <small style="color:#8B949E;">TOTAL UPS</small>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 🟢 خطوة 3: تطبيق فلترة المؤشر على الكروت السفلية فقط
        if selected_metric != "All":
            filtered_drops = all_drops[all_drops["metric"] == selected_metric]
            filtered_ups = all_ups[all_ups["metric"] == selected_metric]
        else:
            filtered_drops = all_drops
            filtered_ups = all_ups

        # 🟢 خطوة 4: الترتيب الحديد (من الانحراف الأكبر للأصغر) لتبكير المشاكل لعين المدير
        final_drops = filtered_drops.sort_values(by="growth", ascending=True)  # الهبوط الأقوى (مثل -40%) فوق أولاً
        final_ups = filtered_ups.sort_values(by="growth", ascending=False)     # القفزة الأعلى (مثل +70%) فوق أولاً

        # فرز التابات الكبيرة وتحميل الكروت المرتستفة
        t_drops_main, t_ups_main = st.tabs(["📉 DROPS ANALYSIS", "📈 UPS ANALYSIS"])
        
        with t_drops_main:
            OC_show_alerts(final_drops, True)
        with t_ups_main:
            OC_show_alerts(final_ups, False)

















with main_tab_oc:
    st.markdown('<div class="section-header">🍊 Orange Cash Monitoring Dashboard</div>', unsafe_allow_html=True)
    
    # 📂 1. قراءة الداتا (المسار المنظم الجديد بتاعك)
    # حماية الكود من الأخطاء في حالة عدم وجود الملف
    # try:
    #     # استبدل الاسم بملف الباركيه الحقيقي بتاعك جوه الفولدر
    #     OC_SERVICES_PER_DAY_HIST = pd.read_csv("OC_SERVICES_PER_DAY_sample.csv") 
    #     OC_SERVICES_PER_DAY_HIST['oc_usage_day'] = pd.to_datetime(OC_SERVICES_PER_DAY_HIST['oc_usage_day']).dt.date
    # except Exception as e:
    #     st.error(f"❌ Error loading Orange Cash Data: {e}")
    #     OC_SERVICES_PER_DAY_HIST = pd.DataFrame()

    if not OC_SERVICES_PER_DAY_HIST.empty:
        # تحديد التواريخ (اليوم الحالي وامبارح) بناءً على الكالندر الرئيسي للأبلكيشن
        oc_prev_day = selected_day - timedelta(days=1)
        
        # تجميع الداتا الكلية على مستوى اليوم (الشركة كلها)
        # df_oc_daily = OC_SERVICES_PER_DAY_HIST.groupby('oc_usage_day').agg({
        #     'total_oc_trx_amts': 'sum',
        #     'total_oc_trx_cnts': 'sum',
        #     'total_unq_subs': 'sum'
        # }).reset_index()


        df_oc_daily = OC_PER_DAY_HIST[['oc_usage_day' , 'total_unq_subs' , 'total_oc_trx_cnts' , 'total_oc_trx_amts']]

        # جلب قيم اليوم الحالي وامبارح للـ KPI Cards الكبار
        curr_oc = df_oc_daily[df_oc_daily['oc_usage_day'] == selected_day]
        prev_oc = df_oc_daily[df_oc_daily['oc_usage_day'] == oc_prev_day]

        # قيم افتراضية في حالة عدم وجود داتا لليوم
        val_amt_curr, val_amt_prev = (curr_oc['total_oc_trx_amts'].values[0], prev_oc['total_oc_trx_amts'].values[0]) if not curr_oc.empty and not prev_oc.empty else (0, 0)
        val_cnt_curr, val_cnt_prev = (curr_oc['total_oc_trx_cnts'].values[0], prev_oc['total_oc_trx_cnts'].values[0]) if not curr_oc.empty and not prev_oc.empty else (0, 0)
        val_sub_curr, val_sub_prev = (curr_oc['total_unq_subs'].values[0], prev_oc['total_unq_subs'].values[0]) if not curr_oc.empty and not prev_oc.empty else (0, 0)

        # ---------------------------------------------------------
        # 💳 الجزء الأول: كروت الأداء العام للأورنج كاش (Top KPI Cards)
        # ---------------------------------------------------------
        oc_kpis = [
            ("Total Transaction Volume (EGP)", val_amt_curr, val_amt_prev),
            ("Total Transactions Count", val_cnt_curr, val_cnt_prev),
            ("Total Active Subscribers", val_sub_curr, val_sub_prev)
        ]

        oc_cols = st.columns(3)
        for i, (name, c_val, p_val) in enumerate(oc_kpis):
            diff = ((c_val - p_val) / p_val * 100) if p_val != 0 else 0
            status_label, status_color = get_status_details(diff)
            delta_class = "green" if diff >= 0 else "red"
            symbol = "+" if diff >= 0 else ""
            
            with oc_cols[i]:
                st.markdown(f"""
                <div class="summary-card" style="border-left: 6px solid {status_color}; margin-bottom:20px;">
                    <div class="summary-label">{name}</div>
                    <div class="summary-value">{round(c_val, 0):,}</div>
                    <div class="summary-delta {delta_class}">{symbol}{round(diff, 1)}% vs D-1</div>
                    <div class="status-tag" style="background-color: {status_color};">{status_label}</div>
                </div>
                """, unsafe_allow_html=True)

        # ---------------------------------------------------------
        # 📑 الجزء الثاني: التابات الفرعية للـ Orange Cash (Sub-Tabs)
        # ---------------------------------------------------------
        sub_tab_performance, sub_tab_breakdown, sub_tab_alerts ,sub_tab_alerts_V2,sub_tab_alerts_V3,sub_tab_alerts_V4 = st.tabs([
            "📊 OVERALL PERFORMANCE", 
            "💼 SERVICES BREAKDOWN", 
            "⚠️ SERVICES ALERTS",
            "⚠️ SERVICES ALERTS V2",
            "⚠️ SERVICES ALERTS V3",
            "⚠️ SERVICES ALERTS V4"
        ])

        # --- 1️⃣ TAB: OVERALL PERFORMANCE ---
        with sub_tab_performance:
            st.write("")
            st.subheader("🗓️ Historical Trend Explorer")

            #OC_f_tab_overall()
            # جدول شيك يعرض أداء آخر الأيام المتوفرة في الداتا فريم المجمعة
            df_display_trend = df_oc_daily.sort_values('oc_usage_day', ascending=False).copy()
            #df_display_trend.columns = ['Date', 'Total Amount (EGP)', 'Total Transactions', 'Total Subscribers']
            df_display_trend.columns = ['Date', 'Total Subscribers', 'Total Transactions', 'Total Amount (EGP)']
            
            # تنسيق الأرقام عشان تطلع شياكة وبها فاصل آلاف
            st.dataframe(
                df_display_trend.style.format({
                    'Total Amount (EGP)': '{:,.2f}',
                    'Total Transactions': '{:,.0f}',
                    'Total Subscribers': '{:,.0f}'
                }), 
                use_container_width=True, 
                hide_index=True
            )

        # --- 2️⃣ TAB: SERVICES BREAKDOWN ---
        with sub_tab_breakdown:
            st.write("")
            # فلترة داتا اليوم الحالي لعرض تفاصيل الخدمات
            df_curr_services = OC_SERVICES_PER_DAY_HIST[OC_SERVICES_PER_DAY_HIST['oc_usage_day'] == selected_day].copy()
            
            if not df_curr_services.empty:
                col_b1, col_b2 = st.columns([2, 1])
                
                with col_b1:
                    st.subheader("🛠️ Services Detailed Matrix")
                    df_matrix = df_curr_services[['service_group', 'service_name', 'total_oc_trx_amts', 'total_oc_trx_cnts', 'total_unq_subs']].sort_values('total_oc_trx_amts', ascending=False)
                    df_matrix.columns = ['Group', 'Service Name', 'Amount (EGP)', 'Trx Count', 'Subscribers']
                    st.dataframe(df_matrix.style.format({'Amount (EGP)': '{:,.2f}', 'Trx Count': '{:,.0f}', 'Subscribers': '{:,.0f}'}), use_container_width=True, hide_index=True)
                
                with col_b2:
                    st.subheader("🏆 Top Services (By Amount)")
                    top_services = df_matrix.head(5)
                    for idx, row in top_services.iterrows():
                        st.metric(label=f"⭐ {row['Service Name']} ({row['Group']})", value=f"{row['Amount (EGP)']:,} EGP")
            else:
                st.info("No service breakdown available for the selected day.")

        # --- 3️⃣ TAB: SERVICES ALERTS ---
        with sub_tab_alerts:
            st.write("")
            st.subheader("🚨 Automatic Services Anomalies Detection")
            st.caption("Detecting any service group that dropped or jumped by more than 5% compared to yesterday.")
            
            # فلترة اليوم الحالي وامبارح للخدمات
            df_c_serv = OC_SERVICES_PER_DAY_HIST[OC_SERVICES_PER_DAY_HIST['oc_usage_day'] == selected_day]
            df_p_serv = OC_SERVICES_PER_DAY_HIST[OC_SERVICES_PER_DAY_HIST['oc_usage_day'] == oc_prev_day]
            
            if not df_c_serv.empty and not df_p_serv.empty:
                # تجميع على مستوى الـ Service Group عشان التنبيهات تكون واضحة ومش زحمة
                cg = df_c_serv.groupby('service_group')[['total_oc_trx_amts', 'total_unq_subs']].sum().reset_index()
                pg = df_p_serv.groupby('service_group')[['total_oc_trx_amts', 'total_unq_subs']].sum().reset_index()
                
                oc_merged = cg.merge(pg, on='service_group', suffixes=('_curr', '_prev'))
                
                alert_triggered = False
                
                for _, row in oc_merged.iterrows():
                    p_amt = row['total_oc_trx_amts_prev']
                    c_amt = row['total_oc_trx_amts_curr']
                    
                    if p_amt > 0:
                        g_pct = ((c_amt - p_amt) / p_amt) * 100
                        if abs(g_pct) >= 5.0: # حد التنبيه 5%
                            alert_triggered = True
                            is_drop = g_pct < 0
                            color = "#DA3633" if is_drop else "#238636"
                            arrow = "▼" if is_drop else "▲"
                            card_class = "drop-card" if is_drop else "up-card"
                            
                            st.markdown(f"""
                            <div class="alert-card {card_class}">
                                <span style="float:right; color:{color}; font-weight:800; font-size:18px;">
                                    {arrow} {abs(round(g_pct, 1))}%
                                </span>
                                <div style="font-weight:700; margin-bottom:5px;">Group: Orange Cash {row['service_group']}</div>
                                <div style="font-size:13px; color:#8B949E; margin-bottom:8px;">
                                    Today Amount: <b>{c_amt:,} EGP</b> | Yesterday: <b>{p_amt:,} EGP</b>
                                </div>
                                <span class="metric-tag">Metric: Transaction Amount</span>
                            </div>
                            """, unsafe_allow_html=True)
                
                if not alert_triggered:
                    st.success("✅ All Orange Cash Services are stable. No abnormal deviations detected!")
            else:
                st.info("Insufficient data to run anomalies detection for this day.")



        # --- 3️⃣ TAB: SERVICES ALERTS (تعديل الشياكة والمؤشرات الفابريكا) ---
        with sub_tab_alerts_V2:
            st.write("")
            st.subheader("🚨 Automatic Services Anomalies Center")
            st.caption("Real-time monitoring for automated deviations in Orange Cash service groups compared to yesterday.")
            
            if not OC_SERVICES_PER_DAY_HIST.empty:
                df_c_serv = OC_SERVICES_PER_DAY_HIST[OC_SERVICES_PER_DAY_HIST['oc_usage_day'] == selected_day]
                df_p_serv = OC_SERVICES_PER_DAY_HIST[OC_SERVICES_PER_DAY_HIST['oc_usage_day'] == oc_prev_day]
                
                if not df_c_serv.empty and not df_p_serv.empty:
                    # تجميع الداتا على مستوى الـ Service Group
                    cg = df_c_serv.groupby('service_group')[['total_oc_trx_amts']].sum().reset_index()
                    pg = df_p_serv.groupby('service_group')[['total_oc_trx_amts']].sum().reset_index()
                    oc_merged = cg.merge(pg, on='service_group', suffixes=('_curr', '_prev'))
                    
                    # 📈 1. المطبخ الخلفي: حساب العدادات والفرز قبل الرسم
                    total_drops = 0
                    critical_drops = 0
                    total_ups = 0
                    critical_ups = 0
                    
                    alerts_list = []
                    
                    for _, row in oc_merged.iterrows():
                        p_amt = row['total_oc_trx_amts_prev']
                        c_amt = row['total_oc_trx_amts_curr']
                        
                        if p_amt > 0:
                            g_pct = ((c_amt - p_amt) / p_amt) * 100
                            status_label, status_color = get_status_details(g_pct)
                            
                            # تصنيف الحالات بناءً على دالة الميزان الموحدة get_status_details
                            if g_pct < 0:
                                total_drops += 1
                                if status_label in ["Critical", "Warning"]:
                                    critical_drops += 1
                            elif g_pct > 0:
                                total_ups += 1
                                if status_label in ["Critical", "Warning"]:
                                    critical_ups += 1
                                    
                            # حفظ البيانات في لستة عشان نرسمها بعد شريط العدادات
                            alerts_list.append({
                                'group': row['service_group'],
                                'pct': g_pct,
                                'curr': c_amt,
                                'prev': p_amt,
                                'label': status_label,
                                'color': status_color
                            })
                    
                    # 📊 2. رسم الـ Executive Summary Strip (شريط العدادات العلوي الشيك)
                    badge_cols = st.columns(4)
                    
                    with badge_cols[0]:
                        st.markdown(f"""
                        <div class="metric-badge-container" style="background-color: #1F191D; border-top: 4px solid #DA3633;">
                            <div class="badge-label">TOTAL DROPS</div>
                            <div class="badge-value" style="color: #DA3633;">{total_drops}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                    with badge_cols[1]:
                        st.markdown(f"""
                        <div class="metric-badge-container" style="background-color: #241419; border-top: 4px solid #FF7B72;">
                            <div class="badge-label">🚨 CRITICAL DROPS</div>
                            <div class="badge-value" style="color: #FF7B72;">{critical_drops}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                    with badge_cols[2]:
                        st.markdown(f"""
                        <div class="metric-badge-container" style="background-color: #17221C; border-top: 4px solid #238636;">
                            <div class="badge-label">TOTAL JUMPS (UPS)</div>
                            <div class="badge-value" style="color: #238636;">{total_ups}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                    with badge_cols[3]:
                        st.markdown(f"""
                        <div class="metric-badge-container" style="background-color: #132321; border-top: 4px solid #3FB950;">
                            <div class="badge-label">⭐ CRITICAL JUMPS</div>
                            <div class="badge-value" style="color: #3FB950;">{critical_ups}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    # 🗂️ 3. فرز ورسم كروت الـ Anomalies بالتفصيل تحت العدادات
                    if len(alerts_list) > 0:
                        # ترتيب الكروت بحيث يعرض الـ Drops القوية الأول عشان تلفت الانتباه
                        alerts_list = sorted(alerts_list, key=lambda x: x['pct'])
                        
                        for alert in alerts_list:
                            # فلترة عشان ما نظهرش الـ Stable (العادي) ونركز على اللي فيه حركة أكتر من 2% أو حسب الـ Threshold
                            if abs(alert['pct']) >= 2.0:
                                is_drop = alert['pct'] < 0
                                arrow = "▼" if is_drop else "▲"
                                card_class = "drop-card" if is_drop else "up-card"
                                
                                st.markdown(f"""
                                <div class="alert-card {card_class}">
                                    <span style="float:right; color:{alert['color']}; font-weight:800; font-size:18px;">
                                        {arrow} {abs(round(alert['pct'], 1))}%
                                    </span>
                                    <div style="font-weight:700; margin-bottom:5px; font-size:16px;">Group: Orange Cash - {alert['group']}</div>
                                    <div style="font-size:13px; color:#8B949E; margin-bottom:8px;">
                                        Today Amount: <b>{alert['curr']:,} EGP</b> | Yesterday: <b>{alert['prev']:,} EGP</b>
                                    </div>
                                    <span class="status-tag" style="background-color: {alert['color']}; color:white; padding: 2px 8px; font-size:11px;">{alert['label']}</span>
                                    <span class="metric-tag" style="margin-left:5px;">Metric: Transaction Amount</span>
                                </div>
                                """, unsafe_allow_html=True)
                    else:
                        st.success("✅ All Orange Cash Services are stable. No abnormal deviations detected!")
                else:
                    st.info("Insufficient data to run anomalies detection for this day.")
            else:
                st.warning("Services raw file is empty.")  

        # --- 3️⃣ TAB: SERVICES ALERTS (الأقوى والأجمل بتحديث الـ UI الموحد) ---
        with sub_tab_alerts_V3:
            st.write("")
            st.subheader("🚨 Automatic Services Anomalies Center")
            
            if not OC_SERVICES_PER_DAY_HIST.empty:
                df_c_serv = OC_SERVICES_PER_DAY_HIST[OC_SERVICES_PER_DAY_HIST['oc_usage_day'] == selected_day]
                df_p_serv = OC_SERVICES_PER_DAY_HIST[OC_SERVICES_PER_DAY_HIST['oc_usage_day'] == oc_prev_day]
                
                if not df_c_serv.empty and not df_p_serv.empty:
                    # تجميع الداتا على مستوى الـ Service Group
                    cg = df_c_serv.groupby('service_group')[['total_oc_trx_amts']].sum().reset_index()
                    pg = df_p_serv.groupby('service_group')[['total_oc_trx_amts']].sum().reset_index()
                    oc_merged = cg.merge(pg, on='service_group', suffixes=('_curr', '_prev'))
                    
                    # 📈 المطبخ الخلفي: عدادات الحالات الـ 4 للـ Drops والـ Ups
                    drops_counters = {"Critical": 0, "Warning": 0, "Watch": 0, "Normal": 0}
                    ups_counters   = {"Critical": 0, "Warning": 0, "Watch": 0, "Normal": 0}
                    
                    drops_list = []
                    ups_list   = []
                    
                    for _, row in oc_merged.iterrows():
                        p_amt = row['total_oc_trx_amts_prev']
                        c_amt = row['total_oc_trx_amts_curr']
                        
                        if p_amt > 0:
                            g_pct = ((c_amt - p_amt) / p_amt) * 100
                            status_label, status_color = get_status_details(g_pct)
                            
                            alert_item = {
                                'group': row['service_group'],
                                'pct': g_pct,
                                'curr': c_amt,
                                'prev': p_amt,
                                'label': status_label,
                                'color': status_color
                            }
                            
                            # الفرز والتصنيف جوه العدادات
                            if g_pct < 0:
                                drops_counters[status_label] += 1
                                drops_list.append(alert_item)
                            elif g_pct > 0:
                                ups_counters[status_label] += 1
                                ups_list.append(alert_item)
                    
                    # 📊 رسم الـ Mini Badges بالشكل الملموم الرشيق للـ Drops
                    st.markdown("##### 📉 Services Volume Drops Status")
                    b_cols_drop = st.columns(4)
                    labels = ["Critical", "Warning", "Watch", "Normal"]
                    colors = ["#DA3633", "#D97706", "#FBBF24", "#238636"] # ألوان الـ Badges الملمومة الرسمية
                    
                    for idx, lbl in enumerate(labels):
                        with b_cols_drop[idx]:
                            st.markdown(f"""
                            <div class="metric-badge-container" style="background-color: #1F191D; border-top: 3px solid {colors[idx]}; padding: 4px 10px;">
                                <div style="font-size: 11px; color: #8B949E; font-weight:600;">{lbl.upper()} DROPS</div>
                                <div style="font-size: 18px; font-weight: 800; color: {colors[idx]};">{drops_counters[lbl]}</div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                    # 📊 رسم الـ Mini Badges بالشكل الملموم الرشيق للـ Ups
                    st.markdown("<div style='margin-top:15px;'></div>", unsafe_allow_html=True)
                    st.markdown("##### 📈 Services Volume Jumps (Ups) Status")
                    b_cols_ups = st.columns(4)
                    for idx, lbl in enumerate(labels):
                        with b_cols_ups[idx]:
                            st.markdown(f"""
                            <div class="metric-badge-container" style="background-color: #141F18; border-top: 3px solid {colors[idx]}; padding: 4px 10px;">
                                <div style="font-size: 11px; color: #8B949E; font-weight:600;">{lbl.upper()} JUMPS</div>
                                <div style="font-size: 18px; font-weight: 800; color: {colors[idx]};">{ups_counters[lbl]}</div>
                            </div>
                            """, unsafe_allow_html=True)

                    st.markdown("<hr style='border: 1px solid #21262D; margin: 25px 0;'>", unsafe_allow_html=True)
                    
                    # 🗂️ تقسيم الشاشة لأعمدة (Two Columns Layout)
                    col_left_drops, col_right_ups = st.columns(2)
                    
                    # --- العمود الأيسر: الـ Drops الكروت الملمومة الشيك ---
                    with col_left_drops:
                        st.markdown("### 📉 Volume Drops Details")
                        if len(drops_list) > 0:
                            # ترتيب حسب الهبوط الأشد
                            drops_list = sorted(drops_list, key=lambda x: x['pct'])
                            for alert in drops_list:
                                if abs(alert['pct']) >= 1.5: # إظهار التحركات المؤثرة
                                    st.markdown(f"""
                                    <div class="alert-card drop-card" style="margin-bottom:12px; padding:12px;">
                                        <span style="float:right; color:{alert['color']}; font-weight:800; font-size:16px;">
                                            ▼ {abs(round(alert['pct'], 1))}%
                                        </span>
                                        <div style="font-weight:700; font-size:14px; margin-bottom:4px;">{alert['group']}</div>
                                        <div style="font-size:12px; color:#8B949E; margin-bottom:8px;">
                                            Today: <b>{alert['curr']:,}</b> | Yesterday: <b>{alert['prev']:,}</b>
                                        </div>
                                        <span class="status-tag" style="background-color: {alert['color']}; color:white; padding: 1px 6px; font-size:10px;">{alert['label']}</span>
                                    </div>
                                    """, unsafe_allow_html=True)
                        else:
                            st.success("✅ No service drops detected today.")
                            
                    # --- العمود الأيمن: الـ Ups الكروت الملمومة الشيك ---
                    with col_right_ups:
                        st.markdown("### 📈 Volume Jumps Details")
                        if len(ups_list) > 0:
                            # ترتيب حسب الصعود الأقوى
                            ups_list = sorted(ups_list, key=lambda x: x['pct'], reverse=True)
                            for alert in ups_list:
                                if abs(alert['pct']) >= 1.5:
                                    st.markdown(f"""
                                    <div class="alert-card up-card" style="margin-bottom:12px; padding:12px;">
                                        <span style="float:right; color:#3FB950; font-weight:800; font-size:16px;">
                                            ▲ {abs(round(alert['pct'], 1))}%
                                        </span>
                                        <div style="font-weight:700; font-size:14px; margin-bottom:4px;">{alert['group']}</div>
                                        <div style="font-size:12px; color:#8B949E; margin-bottom:8px;">
                                            Today: <b>{alert['curr']:,}</b> | Yesterday: <b>{alert['prev']:,}</b>
                                        </div>
                                        <span class="status-tag" style="background-color: {alert['color']}; color:white; padding: 1px 6px; font-size:10px;">{alert['label']}</span>
                                    </div>
                                    """, unsafe_allow_html=True)
                        else:
                            st.info("ℹ️ No meaningful service jumps detected today.")
                else:
                    st.info("Insufficient data to run anomalies detection for this day.")
            else:
                st.warning("Services raw file is empty.")    


        with sub_tab_alerts_V4: 
            OC_f_tab_alerts()

         

                           
    else:
        st.warning("⚠️ No Orange Cash Data available to display. Please check the source file.")











#================== LAST VERSION

