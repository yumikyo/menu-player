import streamlit as st
import os
import sys
import subprocess
import asyncio
import json
import nest_asyncio
import time
import shutil
from gtts import gTTS

# ==========================================
# 1. 準備：ライブラリの強制ロード
# ==========================================
try:
    import google.generativeai as genai
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "google-generativeai>=0.8.3"])
    import google.generativeai as genai

import edge_tts

nest_asyncio.apply()
st.set_page_config(page_title="Menu Player", layout="wide")

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
st.title("🎧 Menu Player")
st.markdown("##### 視覚障害のある方のための「聴くメニュー」生成アプリ")
st.info("メニューの写真をアップロードすると、AIが内容を読み取り、カテゴリーごとに再生できる音声ガイドを作成します。")

uploaded_files = st.file_uploader(
    "📸 メニューの写真を撮る / アップロード", 
    type=['png', 'jpg', 'jpeg'], 
    accept_multiple_files=True
)

if uploaded_files:
    st.image(uploaded_files, width=150, caption=[f"{f.name}" for f in uploaded_files])

# ==========================================
# 4. 音声生成ロジック
# ==========================================
async def generate_audio_safe(text, filename, voice_code, rate_value):
    for attempt in range(3):
        try:
            comm = edge_tts.Communicate(text, voice_code, rate=rate_value)
            await comm.save(filename)
            return "EdgeTTS"
        except Exception as e:
            time.sleep(2)
            
    try:
        tts = gTTS(text=text, lang='ja')
        tts.save(filename)
        return "GoogleTTS"
    except:
        return "Error"

if st.button("🎙️ 音声メニューを作成する"):
    if not api_key or not target_model_name:
        st.error("設定を確認してください（APIキーまたはモデル）")
    else:
        # 保存用の一時フォルダを作成
        output_dir = "menu_audio_album"
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        os.makedirs(output_dir)

        with st.spinner('AIがメニューを読んでいます...（完了後にダウンロードボタンが出ます）'):
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel(target_model_name)
                
                content_parts = []
                prompt = """
                あなたは視覚障害者のためのレストランメニュー読み上げのプロです。
                提供された画像を解析し、以下のJSON形式のみを出力してください。
                価格は「円」まで読み上げ、カテゴリー分けをしてください。
                Markdown記法は不要です。
                [{"title": "はじめに", "text": "..."}] 
                """
                # ↑タイトルに「トラック1」と入れなくてOK（後で自動で番号を振ります）
                
                content_parts.append(prompt)
                for f in uploaded_files:
                    content_parts.append({"mime_type": f.type, "data": f.getvalue()})

                response = model.generate_content(content_parts)
                text_resp = response.text
                
                start = text_resp.find('[')
                end = text_resp.rfind(']') + 1
                menu_data = json.loads(text_resp[start:end])
                
                st.success(f"✅ 完成！ {len(menu_data)}個のトラックを作成しました。")
                
                progress_bar = st.progress(0)
                
                for i, track in enumerate(menu_data):
                    # ファイル名を "01_はじめに.mp3" のように整形して、並び順を保証する
                    track_number = f"{i+1:02}" # 01, 02...
                    safe_title = track['title'].replace("/", "_").replace(" ", "_") # ファイル名に使えない文字を消す
                    filename = f"{track_number}_{safe_title}.mp3"
                    save_path = os.path.join(output_dir, filename)
                    
                    st.subheader(f"🎵 Track {i+1}: {track['title']}")
                    st.write(track['text'])
                    
                    method = asyncio.run(generate_audio_safe(track['text'], save_path, voice_code, rate_value))
                    
                    st.audio(save_path)
                    
                    time.sleep(1)
                    progress_bar.progress((i + 1) / len(menu_data))

                # ==========================================
                # ZIPファイルの作成とダウンロードボタン
                # ==========================================
                shutil.make_archive("menu_album", 'zip', output_dir)
                
                with open("menu_album.zip", "rb") as fp:
                    st.download_button(
                        label="📥 アルバムをまとめてダウンロード (ZIP)",
                        data=fp,
                        file_name="menu_audio_album.zip",
                        mime="application/zip"
                    )
                
                st.info("👆 このボタンを押してZIPファイルをダウンロードし、スマホなどで解凍すると、CDのように連続再生できます。")

            except Exception as e:
                st.error("エラーが発生しました")
                st.write(f"詳細: {e}")
