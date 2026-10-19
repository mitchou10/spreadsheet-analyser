import { useState } from 'react'
import { deleteFeedback, putFeedback } from '@/api/conversations'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import type { Feedback, FeedbackRating, FeedbackReason } from '@/types/conversation'
import { ThumbsDown, ThumbsUp } from 'lucide-react'

const REASONS: { value: FeedbackReason; label: string }[] = [
  { value: 'wrong_result', label: 'Résultat faux' },
  { value: 'wrong_files', label: 'Mauvais fichiers' },
  { value: 'incomplete', label: 'Incomplet' },
  { value: 'unclear', label: 'Peu clair' },
  { value: 'other', label: 'Autre' },
]

interface MessageFeedbackProps {
  conversationId: string
  messageId: string
  initial: Feedback | null
}

/** 👍 / 👎 under an answer. A 👎 opens, right under the answer (not in a dialog), an optional form to say why. */
export function MessageFeedback({ conversationId, messageId, initial }: MessageFeedbackProps) {
  const [feedback, setFeedback] = useState<Feedback | null>(initial)
  const [detailsOpen, setDetailsOpen] = useState(false)
  const [reason, setReason] = useState<FeedbackReason | null>(initial?.reason ?? null)
  const [comment, setComment] = useState(initial?.comment ?? '')
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [thanks, setThanks] = useState(false)

  const save = async (next: Feedback | null) => {
    setIsSaving(true)
    setError(null)
    try {
      if (next) setFeedback(await putFeedback(conversationId, messageId, next))
      else {
        await deleteFeedback(conversationId, messageId)
        setFeedback(null)
      }
      return true
    } catch (e) {
      setError(e instanceof Error ? e.message : "Le retour n'a pas pu être enregistré")
      return false
    } finally {
      setIsSaving(false)
    }
  }

  const vote = async (rating: FeedbackRating) => {
    setThanks(false)
    if (feedback?.rating === rating) {
      // Same thumb again: take the vote back.
      if (await save(null)) {
        setDetailsOpen(false)
        setReason(null)
        setComment('')
      }
      return
    }
    const saved = await save({ rating, reason: null, comment: null })
    if (!saved) return
    setReason(null)
    setComment('')
    setDetailsOpen(rating === 'down')
  }

  const sendDetails = async () => {
    if (!feedback) return
    if (await save({ rating: feedback.rating, reason, comment: comment.trim() || null })) {
      setDetailsOpen(false)
      setThanks(true)
    }
  }

  const thumb = (rating: FeedbackRating, label: string, Icon: typeof ThumbsUp) => (
    <Button
      type="button"
      size="icon-sm"
      variant="ghost"
      disabled={isSaving}
      aria-pressed={feedback?.rating === rating}
      aria-label={label}
      title={label}
      className={cn('text-muted-foreground', feedback?.rating === rating && 'bg-muted text-foreground')}
      onClick={() => vote(rating)}
    >
      <Icon className="size-4" aria-hidden />
    </Button>
  )

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-1" role="group" aria-label="Votre avis sur cette réponse">
        {thumb('up', 'Bonne réponse', ThumbsUp)}
        {thumb('down', 'Mauvaise réponse', ThumbsDown)}
        {feedback?.rating === 'down' && !detailsOpen && (
          <Button
            type="button"
            size="sm"
            variant="link"
            className="text-muted-foreground"
            onClick={() => setDetailsOpen(true)}
          >
            {feedback.reason || feedback.comment ? 'Modifier ma remarque' : 'Préciser'}
          </Button>
        )}
        {thanks && (
          <span className="text-xs text-muted-foreground" role="status">
            Merci pour votre retour.
          </span>
        )}
      </div>

      {detailsOpen && feedback?.rating === 'down' && (
        <div className="flex flex-col gap-2 rounded-lg border bg-background p-3 text-sm">
          <p className="font-medium">Qu'est-ce qui n'allait pas ? (facultatif)</p>
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="Motif">
            {REASONS.map((item) => (
              <Button
                key={item.value}
                type="button"
                size="sm"
                variant={reason === item.value ? 'default' : 'outline'}
                aria-pressed={reason === item.value}
                onClick={() => setReason(reason === item.value ? null : item.value)}
              >
                {item.label}
              </Button>
            ))}
          </div>
          <Textarea
            value={comment}
            maxLength={2000}
            placeholder="Dites-nous ce qui aurait dû être répondu…"
            aria-label="Commentaire"
            onChange={(event) => setComment(event.target.value)}
          />
          <div className="flex justify-end gap-2">
            <Button type="button" size="sm" variant="ghost" onClick={() => setDetailsOpen(false)}>
              Fermer
            </Button>
            <Button type="button" size="sm" disabled={isSaving} onClick={sendDetails}>
              Envoyer
            </Button>
          </div>
        </div>
      )}
      {error && (
        <p className="text-xs text-destructive" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
