import { extractApiErrorMessage } from '@utils/apiError'

export function createPublicNoteComments({ getCsrfToken, renderCommentUbb, hydrateRuntimeWidgets, scrollToLinkedComment, showToast }) {
  function decorateComment(comment) {
    return {
      ...comment,
      rendered_content: renderCommentUbb(comment.content || ''),
      replies: (comment.replies || []).map(reply => ({
        ...reply,
        rendered_content: renderCommentUbb(reply.content || '')
      }))
    }
  }

  async function fetchComments(ctx, reset = true) {
    if (!ctx.note) return
    if (reset) {
      ctx.commentsPage = 1
    }
    ctx.isLoadingComments = true
    try {
      const res = await fetch(`/api/notes/${ctx.note.id}/comments/?page=${ctx.commentsPage}&page_size=${ctx.commentsPageSize}`)
      const data = await res.json()
      const incomingComments = (data.comments || []).map(decorateComment)
      ctx.comments = reset ? incomingComments : [...ctx.comments, ...incomingComments]
      ctx.totalComments = data.total || 0
      const pagination = data.pagination || {}
      ctx.commentsTotalPages = pagination.top_level_total_pages || 1
      ctx.hasMoreComments = ctx.commentsPage < ctx.commentsTotalPages
    } catch (e) {
      console.error('加载评论失败:', e)
    } finally {
      ctx.isLoadingComments = false
      ctx.$nextTick(() => {
        hydrateRuntimeWidgets()
        scrollToLinkedComment()
      })
    }
  }

  async function loadMoreComments(ctx) {
    if (ctx.isLoadingComments || !ctx.hasMoreComments) return
    ctx.commentsPage += 1
    await fetchComments(ctx, false)
  }

  async function submitComment(ctx) {
    if (!ctx.commentContent.trim() || ctx.isSubmittingComment) return
    ctx.isSubmittingComment = true
    try {
      const res = await fetch(`/api/notes/${ctx.note.id}/comments/create/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body: JSON.stringify({ content: ctx.commentContent.trim() })
      })
      if (res.status === 201) {
        const newComment = decorateComment(await res.json())
        newComment.replies = []
        ctx.comments.push(newComment)
        ctx.totalComments++
        ctx.hasMoreComments = ctx.commentsPage < ctx.commentsTotalPages
        ctx.commentContent = ''
        ctx.$nextTick(() => hydrateRuntimeWidgets())
        showToast('评论发表成功！', 'success')
      } else {
        const err = await res.json()
        showToast(extractApiErrorMessage(err, '发表失败'), 'error')
      }
    } catch (e) {
      showToast('网络错误，请稍后重试', 'error')
    } finally {
      ctx.isSubmittingComment = false
    }
  }

  async function submitReply(ctx, parentId) {
    if (!ctx.replyContent.trim() || ctx.isSubmittingComment) return
    ctx.isSubmittingComment = true
    try {
      const res = await fetch(`/api/notes/${ctx.note.id}/comments/create/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body: JSON.stringify({ content: ctx.replyContent.trim(), parent_id: parentId })
      })
      if (res.status === 201) {
        const reply = decorateComment(await res.json())
        const parent = ctx.comments.find(c => c.id === parentId)
        if (parent) parent.replies.push(reply)
        ctx.totalComments++
        ctx.replyContent = ''
        ctx.replyingToId = null
        ctx.$nextTick(() => hydrateRuntimeWidgets())
        showToast('回复成功！', 'success')
      } else {
        const err = await res.json()
        showToast(extractApiErrorMessage(err, '回复失败'), 'error')
      }
    } catch (e) {
      showToast('网络错误，请稍后重试', 'error')
    } finally {
      ctx.isSubmittingComment = false
    }
  }

  function openDeleteConfirm(ctx, target, parentComment = null) {
    ctx.deleteConfirm = {
      visible: true,
      deleting: false,
      commentId: target.id,
      kind: parentComment ? 'reply' : 'comment',
      replyCount: parentComment ? 0 : ((target.replies || []).length),
      preview: ctx.getCommentPreview(target.content || '')
    }
  }

  function closeDeleteConfirm(ctx) {
    if (ctx.deleteConfirm.deleting) return
    ctx.deleteConfirm.visible = false
  }

  async function confirmDeleteComment(ctx) {
    const commentId = ctx.deleteConfirm.commentId
    if (!commentId) return
    ctx.deleteConfirm.deleting = true
    try {
      const res = await fetch(`/api/comments/${commentId}/delete/`, {
        method: 'DELETE',
        headers: { 'X-CSRFToken': getCsrfToken() }
      })
      if (res.ok) {
        const idx = ctx.comments.findIndex(c => c.id === commentId)
        if (idx !== -1) {
          const removed = ctx.comments.splice(idx, 1)[0]
          ctx.totalComments -= 1 + (removed.replies ? removed.replies.length : 0)
        } else {
          ctx.comments.forEach(c => {
            const ri = (c.replies || []).findIndex(r => r.id === commentId)
            if (ri !== -1) {
              c.replies.splice(ri, 1)
              ctx.totalComments--
            }
          })
        }
        showToast('评论已删除', 'success')
      }
    } catch (e) {
      showToast('删除失败', 'error')
    } finally {
      ctx.deleteConfirm = {
        visible: false,
        deleting: false,
        commentId: null,
        kind: 'comment',
        replyCount: 0,
        preview: ''
      }
    }
  }

  function startReply(ctx, comment) {
    ctx.replyingToId = comment.id
    ctx.replyContent = ''
  }

  function cancelReply(ctx) {
    ctx.replyingToId = null
    ctx.replyContent = ''
  }

  return {
    decorateComment,
    fetchComments,
    loadMoreComments,
    submitComment,
    submitReply,
    openDeleteConfirm,
    closeDeleteConfirm,
    confirmDeleteComment,
    startReply,
    cancelReply,
  }
}
