# React チャット表示崩れの修正（Gemini 出力）

> 「まだエラーが出る」場合の、**実運用で壊れにくい方法**をまとめています。

## まず結論（よい方法）

一番安定するのは次の2段構えです。

1. **AIには“表示用Markdown”だけ返させる**（HTML禁止）
2. **フロント側で正規化 → Markdown/Mathレンダリング**する

これで `###` / `**` / 箇条書き / LaTeX の崩れをかなり防げます。

---

## なぜまだ崩れるのか

以前の修正案は方向性として正しいですが、実際には次の入力揺れで壊れます。

- AIが `\( ... \)` や `\[ ... \]` を返す（`$...$` ではない）
- AIがコードフェンス ```markdown ... ``` を混ぜる
- AIが `<br>` や `<b>` などのHTMLを混ぜる
- `\bar{x}` のような式を **数式デリミタなし** で返す

この状態だと `react-markdown + rehype-katex` を入れても表示が不安定になります。

---

## 推奨実装（そのまま使える）

### 1) 依存関係

```bash
npm i react-markdown remark-gfm remark-math rehype-katex katex
```

```jsx
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
```

### 2) 受信テキスト正規化（重要）

```jsx
const normalizeTutorText = (raw = '') => {
  let t = String(raw);

  // 1) コードフェンス除去
  t = t.replace(/^```(?:markdown|md)?\s*/i, '').replace(/```\s*$/i, '');

  // 2) 危険/不要HTMLを無効化（タグを文字として扱う）
  t = t.replace(/</g, '&lt;').replace(/>/g, '&gt;');

  // 3) Math delimiters を統一: \(...\) -> $...$, \[...\] -> $$...$$
  t = t
    .replace(/\\\((.*?)\\\)/gs, (_, m) => `$${m}$`)
    .replace(/\\\[(.*?)\\\]/gs, (_, m) => `$$${m}$$`);

  // 4) 式だけ裸で来るケースの軽い救済（必要ならON）
  // 例: \bar{x} : The mean -> $\bar{x}$ : The mean
  t = t.replace(/(^|\s)(\\[a-zA-Z]+\{[^}]*\})(?=\s*[:：])/g, '$1$$$2$$');

  return t.trim();
};
```

### 3) メッセージ描画

```jsx
function TutorMessage({ content }) {
  const normalized = normalizeTutorText(content);

  return (
    <div className="prose prose-slate max-w-none text-sm md:text-base leading-relaxed">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        skipHtml
      >
        {normalized}
      </ReactMarkdown>
    </div>
  );
}
```

> `skipHtml` を有効にしておくと、AIがHTMLを混ぜてもそのまま解釈しません。

### 4) 既存差し替え

```jsx
// before
<div dangerouslySetInnerHTML={{ __html: ... }} />

// after
<TutorMessage content={msg.content} />
```

---

## プロンプト側も固定する（かなり効く）

`systemPrompt` に以下を追加してください。

```text
Output format rules (MUST):
- Use Markdown only. Do NOT output any HTML tags.
- Use LaTeX only inside $...$ (inline) or $$...$$ (block).
- Never use \( \) or \[ \].
- Do not wrap the answer in code fences.
```

---

## さらに安定させる最善策（本命）

長期運用は、自由文ではなく**構造化レスポンス**にするのが最強です。

例：AIからJSONで返す

```json
{
  "sections": [
    {"type": "heading", "text": "Measures of Central Tendency"},
    {"type": "paragraph", "text": "In statistics..."},
    {"type": "math", "display": false, "latex": "\\bar{x}=\\frac{\\sum x_i}{n}"}
  ]
}
```

UI側で `type` ごとに安全に描画すれば、Markdown崩れ・HTML混入・正規表現事故を避けられます。

---

## うまくいっているかのチェック項目

- `### Heading` が見出しとして表示される
- `**bold**` が太字になる
- `$\\bar{x}$` が数式として表示される
- `$$...$$` のブロック数式が改行されて表示される
- AIが `<b>` を返してもHTMLとしては解釈されない

---

## それでも崩れる場合の切り分け

1. `console.log(raw)` と `console.log(normalized)` を比較
2. `normalized` に `$...$` / `$$...$$` が残っているか確認
3. CSSで `.katex` が `display:none` になっていないか確認
4. `import 'katex/dist/katex.min.css'` が読み込まれているか確認
5. `rehype-katex` が `ReactMarkdown` に渡っているか確認

