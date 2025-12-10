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
メニューの写真をアップロードすると、AIがカテゴリーごとにトラック分けして音声化します。
""")

# サイドバー
with st.sidebar:
    st.header("設定")
    # APIキーはユーザーに入力してもらう（セキュリティとコストのため）
    api_key = st.text_input("Gemini APIキーを入力", type="password")
    st.markdown("[APIキーの取得はこちら(無料)](https://aistudio.google.com/app/apikey)")
    st.info("※入力したキーは保存されず、この場でのみ使用されます。")
    
    voice_options = {
        "女性（七海）": "ja-JP-NanamiNeural",
        "男性（慶太）": "ja-JP-KeitaNeural"
    }
    selected_voice = st.selectbox("音声の声", list(voice_options.keys()))
    voice_code = voice_options[selected_voice]

# メイン処理
uploaded_file = st.file_uploader("メニューの写真を撮影またはアップロード", type=['png', 'jpg', 'jpeg'])

if uploaded_file and api_key:
    st.image(uploaded_file, caption='アップロードされたメニュー', use_column_width=True)

    if st.button("🎙️ 音声メニューを作成する"):
        with st.spinner('AIがメニューを読んで、構成を考えています...'):
            try:
                # Geminiの設定
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                image_parts = [
                    {
                        "mime_type": uploaded_file.type,
                        "data": uploaded_file.getvalue()
                    }
                ]

                # プロンプト
                prompt = """
                あなたは視覚障害者のためにレストランのメニューを読み上げる優秀なナレーター兼編集者です。
                提供されたメニュー画像を解析し、以下のルールで「聴きやすい音声台本」を作成してください。

                【ルール】
                1. メニュー全体を論理的なカテゴリー（トラック）に分けてください。（例：ドリンク、前菜、メイン、デザートなど）
                2. トラック1は必ず「はじめに」として、店名の紹介（画像にある場合）や、お店の雰囲気を伝えてください。
                3. 価格は「円」まではっきり読み上げ、税込みかどうかわかる場合は補足してください。
                4. 単なる羅列ではなく、「次は〇〇です」「おすすめは〜」のように自然な話し言葉にしてください。
                
                【出力フォーマット】
                以下のJSON形式のみを出力してください。余計な解説やマークダウン記法は不要です。
                [
                    {"title": "トラック1：はじめに", "text": "読み上げ原稿..."},
                    {"title": "トラック2：ドリンク", "text": "読み上げ原稿..."}
                ]
                """

                response = model.generate_content([prompt, image_parts[0]])
                
                # JSON抽出処理
                text_response = response.text
                start_index = text_response.find('[')
                end_index = text_response.rfind(']') + 1
                if start_index == -1:
                     raise ValueError("AIがメニューをうまく読み取れませんでした。")
                
                json_str = text_response[start_index:end_index]
                menu_data = json.loads(json_str)
                
                st.success("✅ 音声の生成が完了しました！")

                # 音声生成関数
                async def generate_audio_file(text, filename):
                    communicate = edge_tts.Communicate(text, voice_code)
                    await communicate.save(filename)

                # トラック生成ループ
                for i, track in enumerate(menu_data):
                    st.subheader(f"🎵 {track['title']}")
                    st.write(track['text'])
                    
                    # 一時ファイルとして音声を保存
                    filename = f"track_{i+1}.mp3"
                    asyncio.run(generate_audio_file(track['text'], filename))
                    
                    # 音声プレーヤーを表示
                    st.audio(filename, format='audio/mp3')

            except Exception as e:
                st.error(f"エラーが発生しました: {e}")
                st.info("APIキーが正しいか、画像が鮮明か確認してください。")

elif not api_key:
    st.warning("左側のサイドバーにGemini APIキーを入力してください。")
