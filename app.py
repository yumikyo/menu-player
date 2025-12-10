import streamlit as st
import google.generativeai as genai
import edge_tts
import asyncio
import json
import os
import nest_asyncio

# 非同期処理のパッチ
nest_asyncio.apply()

# ページ設定
st.set_page_config(page_title="Menu Player", layout="wide")

# タイトル
st.title("🎧 Menu Player")
st.markdown("""
**視覚障害のある方のための「聴くメニュー」アプリ**
メニューの写真（複数枚OK）をアップロードすると、AIが全体を整理してトラック分けし、音声化します。
""")

# サイドバー
with st.sidebar:
    st.header("設定")
    api_key = st.text_input("Gemini APIキーを入力", type="password")
    st.markdown("[APIキーの取得はこちら(無料)](https://aistudio.google.com/app/apikey)")
    
    voice_options = {
        "女性（七海）": "ja-JP-NanamiNeural",
        "男性（慶太）": "ja-JP-KeitaNeural"
    }
    selected_voice = st.selectbox("音声の声", list(voice_options.keys()))
    voice_code = voice_options[selected_voice]

# メイン処理：複数ファイルのアップロードを許可
uploaded_files = st.file_uploader(
    "メニューの写真を撮影またはアップロード（複数選択可）", 
    type=['png', 'jpg', 'jpeg'], 
    accept_multiple_files=True
)

if uploaded_files and api_key:
    # アップロードされた画像を並べて表示
    st.image(uploaded_files, caption=[f"{file.name}" for file in uploaded_files], width=200)

    if st.button("🎙️ まとめて音声メニューを作成する"):
        with st.spinner('AIが全ページを読んで、構成を考えています...'):
            try:
                # Geminiの設定
                genai.configure(api_key=api_key)
                # モデル指定（最新バージョン対応）
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                # 複数の画像をAIへの入力形式に変換
                content_parts = []
                # プロンプトを最初に追加
                prompt_text = """
                あなたは視覚障害者のためにレストランのメニューを読み上げるプロのナレーターです。
                提供された【複数のメニュー画像】をすべて解析し、お店全体のメニューとして統合して、以下のルールで「聴きやすい音声台本」を作成してください。

                【ルール】
                1. メニュー全体を論理的なカテゴリー（トラック）に整理してください。（例：ドリンク、前菜、メイン、デザートなど）
                   ※ページごとではなく、内容でカテゴリー分けしてください。
                2. トラック1は必ず「はじめに」として、店名の紹介やお店の雰囲気を伝えてください。
                3. 価格は「円」まではっきり読み上げてください。
                4. 画像が複数ある場合も、重複を避け、自然な流れで一つのコースのように案内してください。
                
                【出力フォーマット】
                以下のJSON形式のみを出力してください。余計な解説やマークダウン記法(```json)は不要です。
                [
                    {"title": "トラック1：はじめに", "text": "読み上げ原稿..."},
                    {"title": "トラック2：ドリンク", "text": "読み上げ原稿..."},
                    {"title": "トラック3：おすすめ料理", "text": "読み上げ原稿..."}
                ]
                """
                content_parts.append(prompt_text)

                # 画像データを順に追加
                for file in uploaded_files:
                    image_data = {
                        "mime_type": file.type,
                        "data": file.getvalue()
                    }
                    content_parts.append(image_data)

                # AIへ送信
                response = model.generate_content(content_parts)
                
                # JSON抽出処理
                text_response = response.text
                start_index = text_response.find('[')
                end_index = text_response.rfind(']') + 1
                if start_index == -1:
                     raise ValueError("AIがメニューをうまく読み取れませんでした。")
                
                json_str = text_response[start_index:end_index]
                menu_data = json.loads(json_str)
                
                st.success(f"✅ 全{len(uploaded_files)}ページから、{len(menu_data)}つのトラックを作成しました！")

                # 音声生成関数
                async def generate_audio_file(text, filename):
                    communicate = edge_tts.Communicate(text, voice_code)
                    await communicate.save(filename)

                # トラック生成ループ
                for i, track in enumerate(menu_data):
                    st.subheader(f"🎵 {track['title']}")
                    st.write(track['text'])
                    
                    filename = f"track_{i+1}.mp3"
                    asyncio.run(generate_audio_file(track['text'], filename))
                    
                    st.audio(filename, format='audio/mp3')

            except Exception as e:
                st.error(f"エラーが発生しました: {e}")
                st.info("APIキーが正しいか、画像が鮮明か確認してください。")

elif not api_key:
    st.warning("左側のサイドバーにGemini APIキーを入力してください。")
