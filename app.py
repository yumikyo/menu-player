import streamlit as st
import os
import asyncio
import json
import nest_asyncio
import time
import shutil
import zipfile
import re
from datetime import datetime
from gtts import gTTS
import google.generativeai as genai
from google.api_core import exceptions
import requests
from bs4 import BeautifulSoup
import edge_tts

# 非同期処理の適用
nest_asyncio.apply()

# ページ設定
st.set_page_config(page_title="Menu Player Generator", layout="wide")

# ==========================================
# 1. サイドバー設定
# ==========================================
with st.sidebar:
    st.header("🔧 設定")
    
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
        st.success("🔑 APIキー認証済み")
    else:
        api_key = st.text_input("Gemini APIキー", type="password")
    
    valid_models = []
    target_model_name = None
    
    if api_key:
        try:
            genai.configure(api_key=api_key)
            all_models = list(genai.list_models())
            valid_models = [m.name for m in all_models if 'generateContent' in m.supported_generation_methods]
        except:
            pass
    
    if valid_models:
        default_idx = next((i for i, n in enumerate(valid_models) if "flash" in n), 0)
        target_model_name = st.selectbox("使用するAIモデル", valid_models, index=default_idx)
    elif api_key:
        st.error("有効なモデルが見つかりません")

    st.divider()
    
    st.subheader("🗣️ 音声設定")
    voice_options = {"女性（七海）": "ja-JP-NanamiNeural", "男性（慶太）": "ja-JP-KeitaNeural"}
    selected_voice = st.selectbox("声の種類", list(voice_options.keys()))
    voice_code = voice_options[selected_voice]
    
    speed_options = {
        "標準 (±0%)": "+0%", 
        "少し速く (1.2倍)": "+20%", 
        "サクサク (1.4倍/推奨)": "+40%", 
        "爆速 (2.0倍)": "+100%"
    }
    selected_speed_label = st.selectbox("読み上げ速度", list(speed_options.keys()), index=2)
    rate_value = speed_options[selected_speed_label]

# ==========================================
# 2. メイン画面
# ==========================================
st.title("🎧 Menu Player Generator")
st.markdown("##### 視覚障害のある方のための「聴くメニュー」生成アプリ")

# --- 店舗情報の入力フォーム ---
col1, col2 = st.columns(2)
with col1:
    store_name = st.text_input("🏠 店舗名（必須）", placeholder="例：カフェタナカ")
with col2:
    menu_title = st.text_input("📖 今回のメニュー名（任意）", placeholder="例：冬のランチメニュー")

# --- セッション状態の初期化（カメラ画像の保存用） ---
if 'captured_images' not in st.session_state:
    st.session_state.captured_images = []
if 'camera_key' not in st.session_state:
    st.session_state.camera_key = 0

# --- 入力モードの切り替えタブ ---
tab1, tab2 = st.tabs(["📸 画像・カメラ", "🌐 Webリンク"])

# 最終的にAIに渡す画像リスト
final_image_list = []
target_url = None

with tab1:
    st.markdown("### 1. アルバムから選択")
    uploaded_files = st.file_uploader(
        "スマホ内の写真を選択", 
        type=['png', 'jpg', 'jpeg'], 
        accept_multiple_files=True
    )
    
    st.markdown("### 2. その場で撮影（連続撮影可能）")
    
    # カメラ入力（keyを変えることでリセットを実現）
    camera_file = st.camera_input("カメラを起動", key=f"camera_{st.session_state.camera_key}")

    if camera_file:
        # 写真が撮られたら「追加ボタン」を表示
        if st.button("⬇️ この写真を追加して次を撮る", type="primary"):
            st.session_state.captured_images.append(camera_file)
            st.session_state.camera_key += 1 # キーを変えてカメラをリセット
            st.rerun() # 画面更新

    # --- 現在セットされている画像の確認エリア ---
    
    # 1. アップロードされた画像
    if uploaded_files:
        final_image_list.extend(uploaded_files)
    
    # 2. カメラで撮りためた画像
    if st.session_state.captured_images:
        final_image_list.extend(st.session_state.captured_images)
    
    # リセットボタン
    if st.session_state.captured_images:
        if st.button("🗑️ 撮影した写真を全てクリア"):
            st.session_state.captured_images = []
            st.rerun()

    # プレビュー表示
    if final_image_list:
        st.success(f"現在 {len(final_image_list)} 枚の画像がセットされています")
        # 横に並べて表示
        cols = st.columns(len(final_image_list))
        for idx, img in enumerate(final_image_list):
            if idx < 5: # 画面幅的に5枚くらいまで表示
                with cols[idx]:
                    st.image(img, caption=f"No.{idx+1}", use_container_width=True)

with tab2:
    st.info("お店のホームページや
