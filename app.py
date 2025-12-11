import streamlit as st
import os
import sys
import subprocess
import asyncio
import json
import nest_asyncio
import time
import shutil
import zipfile
import re
from datetime import datetime
from gtts import gTTS

# ==========================================
# 1. 準備：ライブラリの強制ロード
# ==========================================
# 必要なライブラリをリストアップ
required_packages = [
    ("google-generativeai", "0.8.3"),
    ("requests", "2.31.0"),
    ("beautifulsoup4", "4.12.0")
]

for package, version in required_packages:
    try:
        __import__(package.replace("-", "_").split(">")[0]) # 簡易チェック
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", f"{package}>={version}"])

import google.generativeai as genai
from google.api_core import exceptions
import requests
from bs4 import BeautifulSoup
import edge_tts

nest_asyncio.apply()
st.set_page_config(page_title="Menu Player Generator", layout="wide")

# ==========================================
# 2. サイドバー設定
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
        # Flashモデルを優先
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
# 3. メイン画面
# ==========================================
st.title("🎧 Menu Player Generator")
st.markdown("##### 視覚障害のある方のための「聴くメニュー」生成アプリ")

# --- 店舗情報の入力フォーム ---
col1, col2 = st.columns(2)
with col1:
    store_name = st.text_input("🏠 店舗名（必須）", placeholder="例：カフェタナカ")
with col2:
    menu_title = st.text_input("📖 今回のメニュー名（任意）", placeholder="例：冬のランチメニュー")

# --- 入力モードの切り替えタブ ---
tab1, tab2 = st.tabs(["📸 画像から作成", "🌐 Webリンクから作成"])

uploaded_files = None
target_url = None

with tab1:
    uploaded_files = st.file_uploader(
        "メニューの写真をアップロード", 
        type=['png', 'jpg', 'jpeg'], 
        accept_multiple_files=True
    )
    if uploaded_files:
        st.image(uploaded_files, width=150, caption=[f"{f.name}" for f in uploaded_files])

with tab2:
    st.info("お店のホームページや、食べログ等のメニューページのURLを入力してください。")
    target_url = st.text_input("URLを入力", placeholder="https://...")

# ==========================================
# 4. 音声生成ロジック
# ==========================================
async def generate_audio_safe(text, filename, voice_code, rate_value):
    # 3回リトライ
    for attempt in range(3):
        try:
            comm = edge_tts.Communicate(text, voice_code, rate=rate_value)
            await comm.save(filename)
            if os.path.exists(filename) and os.path.getsize(filename) > 0:
                return "EdgeTTS"
        except Exception as e:
            time.sleep(1)
            
    # 予備音声
    try:
        tts = gTTS(text=text, lang='ja')
        tts.save(filename)
        return "GoogleTTS"
    except:
        return "Error"

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name).replace(" ", "_").replace("　", "_")

# URLからテキストを抽出する関数
def fetch_text_from_url(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = response.apparent_encoding # 文字化け対策
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 不要なタグ（スクリプトやスタイル）を削除
        for script in soup(["script", "style", "header", "footer", "nav"]):
            script.extract()
            
        # テキストのみ取得
        text = soup.get_text(separator="\n")
        
        # 空白行を整理
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)
    except Exception as e:
        return None

# --- 生成ボタン処理 ---
if st.button("🎙️ 音声メニューを作成する"):
    # エラーチェック
    if not api_key or not target_model_name:
        st.error("設定を確認してください（APIキーまたはモデル）")
        st.stop()
    
    if not store_name:
        st.warning("⚠️ 店舗名を入力してください（ファイル名に使用します）")
        st.stop()

    # モード判定
    mode = "image" if uploaded_files else "url"
    
    if mode == "url" and not target_url:
        st.warning("⚠️ 画像をアップロードするか、URLを入力してください")
        st.stop()

    # フォルダのリセット
    output_dir = os.path.abspath("menu_audio_album")
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir)

    with st.spinner('AIが情報を解析し、台本を作成中...'):
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(target_model_name)
            
            content_parts = []
            
            # 共通プロンプト
            base_prompt = """
            あなたは視覚障害者のためのレストランメニュー読み上げのプロです。
            提供された情報を解析し、以下のJSON形式のみを出力してください。
            Markdown記法（```jsonなど）は不要です。生データのみ返してください。
            
            ルール:
            1. 価格は「円」まで読み上げる形式にする。
            2. カテゴリーごとにトラックを分ける。
            3. URLからの情報の場合、メニューと関係ないナビゲーション文字などは無視する。
            
            出力例:
            [
                {"title": "前菜", "text": "まずは前菜のメニューです。シーザーサラダ、800円。..."},
                {"title": "メイン料理", "text": "続いてメイン料理のご紹介です。..."}
            ]
            """
            
            if mode == "image":
                content_parts.append(base_prompt + "\n\n以下はメニューの画像です。")
                for f in uploaded_files:
                    content_parts.append({"mime_type": f.type, "data": f.getvalue()})
            else:
                # URLモード
                web_text = fetch_text_from_url(target_url)
                if not web_text:
                    st.error("URLから情報を読み取れませんでした。アクセス制限があるか、無効なURLの可能性があります。")
                    st.stop()
                
                content_parts.append(base_prompt + f"\n\n以下はWebサイトから抽出したテキスト情報です。\n\n{web_text[:30000]}") # 長すぎるとエラーになるので制限

            # --- リトライ処理 ---
            response = None
            retry_count = 0
            max_retries = 3
            
            while retry_count < max_retries:
                try:
                    response = model.generate_content(content_parts)
                    break
                except exceptions.ResourceExhausted:
                    st.warning(f"⚠️ 混雑中のため待機しています... ({retry_count+1}/{max_retries})")
                    time.sleep(10)
                    retry_count += 1
                except Exception as e:
                    raise e

            if response is None:
                st.error("❌ 混雑が激しいため、時間を置いて再度お試しください。")
                st.stop()
            # ---------------------

            text_resp = response.text
            
            # JSON部分の抽出（余計な文字が含まれる場合の対策）
            start = text_resp.find('[')
            end = text_resp.rfind(']') + 1
            if start == -1 or end == 0:
                 st.error("AIが有効なデータを返しませんでした。別の画像やURLで試してください。")
                 st.write(text_resp) # デバッグ用
                 st.stop()
                 
            menu_data = json.loads(text_resp[start:end])

            # --- イントロダクション自動生成 ---
            intro_title = "はじめに・目次"
            intro_text = f"こんにちは、{store_name}です。"
            if menu_title:
                intro_text += f"ただいまより、{menu_title}をご紹介します。"
            
            intro_text += "今回の内容は以下の通りです。"
            for i, track in enumerate(menu_data):
                intro_text += f"トラック{i+2}は、{track['title']}。"
            intro_text += "それでは、ごゆっくりお聴きください。"
            
            menu_data.insert(0, {"title": intro_title, "text": intro_text})
            
            st.success(f"✅ 台本完成！ 全{len(menu_data)}トラック（イントロ含む）を生成します。")
            
            progress_bar = st.progress(0)
            
            # 音声生成ループ
            for i, track in enumerate(menu_data):
                track_number = f"{i+1:02}"
                safe_title = sanitize_filename(track['title'])
                filename = f"{track_number}_{safe_title}.mp3"
                save_path = os.path.join(output_dir, filename)
                
                st.subheader(f"🎵 Track {track_number}: {track['title']}")
                st.write(track['text'])
                
                method = asyncio.run(generate_audio_safe(track['text'], save_path, voice_code, rate_value))
                
                if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
                    pass # 成功
                else:
                    st.error(f"Track {i+1} の生成に失敗しました")
                
                progress_bar.progress((i + 1) / len(menu_data))
                time.sleep(0.5)

            # ZIP作成
            date_str = datetime.now().strftime('%Y%m%d')
            safe_store_name = sanitize_filename(store_name)
            zip_filename = f"{safe_store_name}_{date_str}.zip"
            
            with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(output_dir):
                    for file in files:
                        zipf.write(os.path.join(root, file), file)
            
            if os.path.getsize(zip_filename) > 0:
                st.success(f"📦 ZIP作成完了: {zip_filename}")
                with open(zip_filename, "rb") as fp:
                    st.download_button(
                        label=f"📥 {zip_filename} をダウンロード",
                        data=fp,
                        file_name=zip_filename,
                        mime="application/zip"
                    )

        except Exception as e:
            st.error("エラーが発生しました")
            st.write(f"詳細: {e}")
