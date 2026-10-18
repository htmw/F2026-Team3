import { errorText } from './api.js'

// Optimistic action with an Undo toast (spec 00 §5). `apply` / `revert` are setData updaters;
// `request` performs the action and `undo` its reverse endpoint. Failures roll the local change back.
//   optimisticAction({ setData, toast, apply, revert, message: 'Plan approved',
//     request: () => api(`/advisor/approvals/${id}/approve`, { method: 'POST' }),
//     undo: () => api(`/advisor/approvals/${id}/reopen`, { method: 'POST' }) })
export async function optimisticAction({ setData, toast, apply, revert, request, undo, message }) {
  setData(apply)
  try {
    await request()
  } catch (err) {
    setData(revert)
    toast.show({ message: errorText(err) })
    return false
  }
  toast.show({
    message,
    ...(undo && {
      actionLabel: 'Undo',
      onAction: async () => {
        setData(revert)
        try {
          await undo()
        } catch (err) {
          setData(apply)
          toast.show({ message: errorText(err) })
        }
      },
    }),
  })
  return true
}
