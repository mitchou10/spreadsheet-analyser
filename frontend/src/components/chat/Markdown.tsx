import { cn } from '@/lib/utils'
import { createElement, type ComponentProps } from 'react'
import ReactMarkdown, { type Components, type ExtraProps } from 'react-markdown'
import remarkGfm from 'remark-gfm'

type Tag = 'p' | 'h1' | 'h2' | 'h3' | 'h4' | 'ul' | 'ol' | 'a' | 'blockquote' | 'pre' | 'th' | 'td'

// One element with fixed classes. react-markdown also passes the syntax-tree `node`, which must not reach the DOM.
function styled<T extends Tag>(tag: T, classes: string, extra?: ComponentProps<T>) {
  return function Styled(props: ComponentProps<T> & ExtraProps) {
    const { node: _node, className, ...rest } = props as ComponentProps<'div'> & ExtraProps
    return createElement(tag, { ...extra, ...rest, className: cn(classes, className) })
  }
}

// Styled per element (no typography plugin). Raw HTML in the answer is not rendered: react-markdown escapes it.
const components: Components = {
  p: styled('p', 'my-2 first:mt-0 last:mb-0'),
  h1: styled('h1', 'mt-4 mb-2 text-lg font-semibold first:mt-0'),
  h2: styled('h2', 'mt-4 mb-2 text-base font-semibold first:mt-0'),
  h3: styled('h3', 'mt-3 mb-1.5 text-sm font-semibold first:mt-0'),
  h4: styled('h4', 'mt-3 mb-1.5 text-sm font-semibold first:mt-0'),
  ul: styled('ul', 'my-2 list-disc space-y-1 pl-5'),
  ol: styled('ol', 'my-2 list-decimal space-y-1 pl-5'),
  a: styled('a', 'underline underline-offset-2', { target: '_blank', rel: 'noreferrer noopener' }),
  blockquote: styled('blockquote', 'my-2 border-l-2 border-border pl-3 text-muted-foreground'),
  pre: styled('pre', 'my-2 overflow-x-auto rounded-md bg-background/60 p-3 text-xs'),
  th: styled('th', 'border border-border bg-background/40 px-2 py-1 text-left font-medium'),
  td: styled('td', 'border border-border px-2 py-1'),
  hr: () => <hr className="my-3 border-border" />,
  // Inline code gets a chip; inside a <pre> (a fenced block) the chip look is reset.
  code: ({ node, className, ...rest }: ComponentProps<'code'> & ExtraProps) => {
    void node
    return <code className={cn('rounded bg-background/60 px-1 py-0.5 text-[0.85em] [pre_&]:bg-transparent [pre_&]:p-0', className)} {...rest} />
  },
  table: ({ node, ...rest }: ComponentProps<'table'> & ExtraProps) => {
    void node
    return (
      <div className="my-2 overflow-x-auto">
        <table className="w-full border-collapse text-xs" {...rest} />
      </div>
    )
  },
}

export function Markdown({ children }: { children: string }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
      {children}
    </ReactMarkdown>
  )
}
