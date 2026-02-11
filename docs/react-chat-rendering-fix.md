# React チャット表示崩れの修正（Gemini 出力）

症状（スクリーンショットの状態）:

- `###` が見出しとして解釈されず、そのまま表示される
- `**bold**` がそのまま表示される
- `\bar{x}` などの LaTeX が文字列のまま表示される

原因:

現在の実装は `dangerouslySetInnerHTML` で **改行・`$...$`・`[...]` だけ** 置換しています。
そのため Markdown (`###`, `**`, 箇条書き) はパースされません。

## 推奨修正

Markdown と数式を正式にレンダリングしてください。

### 1) パッケージ追加

```bash
npm i react-markdown remark-gfm remark-math rehype-katex katex
```

### 2) レンダラーを追加

```jsx
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';

function TutorMessage({ content }) {
  return (
    <div className="prose prose-slate max-w-none text-sm md:text-base leading-relaxed prose-headings:my-2 prose-p:my-2 prose-li:my-1">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
```

### 3) 既存の `dangerouslySetInnerHTML` を置き換え

以下を:

```jsx
<div dangerouslySetInnerHTML={{ __html: ... }} />
```

以下に変更:

```jsx
<TutorMessage content={msg.content} />
```

## 補足（今の実装が崩れる理由）

- `replace(/\n/g, '<br>')` は改行しか処理しない
- `replace(/\$(.*?)\$/g, ...)` はインライン `$...$` にしか対応しない
- Markdown 記法を HTML へ変換していないため `###` や `**` が素通り
- 文字列置換ベースは XSS/表示崩れの温床になりやすい

## 追加の安定化ポイント

- Gemini 側の system prompt に「Markdown + LaTeX で返す」ことを明記
- 数式は `$...$`（インライン）と `$$...$$`（ブロック）を使わせる
- 角括弧タグ `[EXPLAIN]` は Markdown 上で強調に変える（例: `**[EXPLAIN]**`）

