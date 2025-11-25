export type WritingModelAvatarStatus =
  | 'idle'
  | 'selected'
  | 'queued'
  | 'generating'
  | 'stopping'
  | 'completed'
  | 'stopped'
  | 'error'

export interface WritingModelAvatarItem {
  key: string
  displayName: string
  isPrimary: boolean
  selected: boolean
  status: WritingModelAvatarStatus
  targetVariants: number
  currentVariant: number
  startedAt: number | null
  finishedAt: number | null
  canStop: boolean
  canToggle: boolean
  avatarColor: string
  avatarAccent: string
  initials: string
  errorMessage?: string | null
}
