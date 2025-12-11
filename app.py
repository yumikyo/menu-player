import streamlit as st
import os
import sys
import subprocess
import time

# ==========================================
# 強制アップデート（ゾンビ退治）
# ==========================================
try:
    import google.generativeai as genai
    # バージョン確認。古ければ強制インストール
    if genai.__version__ < "0.8.3":
        subprocess.check_call([sys.executable, "-m", "pip", "install", "google-generativeai>=0.8.3"])
        import google.generativeai as genai
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "google-generativeai>=0.8.3"])
    import google.generativeai as genai

import edge_tts
import asyncio
import json
import nest_asyncio

nest_asyncio.apply()
st.set_page_config(page_title="Menu Player", layout="wide")

# ==========================================
# サイドバー（設定）
# ==========================================
with st.sidebar:
    st.header("🔧 設定")
    # ここに新しいキーを入れてもらいます
    api_key = st.text_input("Gemini APIキー (AI Studioで取得)", type="password")
    st.markdown("[👉 新しいキーの取得はこちら](https://aistudio.google.com/app/apikey)")
    
    st.divider()
    
    # 【診断ツール】バージョン表示
    st.caption(f"システム情報: Python {sys.version.split()[0]} / AI Lib {genai.__version__}")
    
    voice_options = {"女性（七海）": "ja-JP-NanamiNeural", "男性（慶太）": "ja-JP-KeitaNeural"}
    selected_voice = st.selectbox("音声の声", list(voice_options.keys()))
    voice_code = voice_options[selected_voice]

# ==========================================
# メイン画面
# ==========================================
st.title("🎧 Menu Player (診断モード付)")
st.markdown("視覚障害のある方のための「聴くメニュー」アプリです。")

uploaded_files = st.file_uploader(
    "メニュー画像をアップロード（複数OK）", 
    type=['png', 'jpg', 'jpeg'], 
    accept_multiple_files=True
)

if uploaded_files:
    st.image(uploaded_files, width=150, caption=[f"{f.name}" for f in uploaded_files])

# 実行ボタン
if st.button("🎙️ 音声メニューを作成する"):
    if not api_key:
        st.warning("⚠️ 左側のサイドバーにAPIキーを入れてください")
    else:
        with st.spinner('AIに接続中...（APIキーと通信を確認しています）'):
            try:
                # 1. API設定
                genai.configure(api_key=api_key)
                
                # 2. 接続テスト（利用可能なモデル一覧を取得してみる）
                # これができればAPIキーは正常です
                try:
                    models = list(genai.list_models())
                    # モデル一覧にFlashがあるかチェック
                    flash_exists = any('gemini-1.5-flash' in m.name for m in models)
                    if not flash_exists:
                        st.warning("⚠️ 注意: このAPIキーではGemini 1.5 Flashが見つかりません。別のモデルを試します。")
                except Exception as e:
                    st.error("🚫 APIキーのエラー: キーが無効か、アクセス権がありません。")
                    st.error(f"詳細: {e}")
                    st.stop() # 処理をここで止める

                # 3. 本番処理
                # モデル名を少し変更して通りやすくする
                model = genai.GenerativeModel('gemini-1.5-flash-latest') 
                
                content_parts = []
                prompt_text = """
                あなたは視覚障害者のためのレストランメニュー読み上げのプロです。
                提供された画像を解析し、以下のJSON形式のみを出力してください。
                Markdown記法は使わないでください。
                [{"title": "トラック1：店名・挨拶", "text": "..."}]
                """
                content_parts.append(prompt_text)

                for file in uploaded_files:
                    image_data = {"mime_type": file.type, "data": file.getvalue()}
                    content_parts.append(image_data)

                # AI生成実行
                response = model.generate_content(content_parts)
                
                # JSON解析
                text = response.text
                start = text.find('[')
                end = text.rfind(']') + 1
                menu_data = json.loads(text[start:end])
                
                st.success(f"✅ 成功！ {len(menu_data)}個のトラックを作成しました。")

                # 音声生成
                async def gen_audio(t, f):
                    comm = edge_tts.Communicate(t, voice_code)
                    await comm.save(f)

                for i, track in enumerate(menu_data):
                    st.subheader(f"🎵 {track['title']}")
                    st.write(track['text'])
                    fname = f"track_{i+1}.mp3"
                    asyncio.run(gen_audio(track['text'], fname))
                    st.audio(fname)

            except Exception as e:
                st.error("❌ エラーが発生しました")
                st.write("考えられる原因:")
                st.write("1. APIキーが古い、または無効 (AI Studioで作り直してください)")
                st.write("2. 画像が大きすぎる")
                st.code(f"エラー詳細: {e}")
