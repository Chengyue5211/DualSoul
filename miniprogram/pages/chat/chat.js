const api = require('../../utils/api')
const util = require('../../utils/util')
const app = getApp()

Page({
  data: {
    friendId: '',
    friendName: '',
    friendMode: 'real',
    myUserId: '',
    messages: [],
    inputText: '',
    chatMode: 'real-real',   // 当前对话模式
    senderMode: 'real',
    receiverMode: 'real',
    inputPlaceholder: '发消息...',
    scrollTo: 'msg-end',
    pollTimer: null
  },

  onLoad(options) {
    this.setData({
      friendId: options.friendId || '',
      friendName: decodeURIComponent(options.friendName || ''),
      friendMode: options.friendMode || 'real',
      myUserId: app.globalData.userInfo ? app.globalData.userInfo.user_id : ''
    })
    wx.setNavigationBarTitle({ title: this.data.friendName })
    this.loadMessages()
    // 轮询新消息
    this._pollTimer = setInterval(() => this.loadMessages(), 5000)
  },

  onUnload() {
    if (this._pollTimer) clearInterval(this._pollTimer)
  },

  async loadMessages() {
    try {
      const res = await api.getMessages(this.data.friendId, 100)
      if (res.success) {
        // 标注对话模式变化
        const msgs = res.messages.map((m, i) => {
          const key = m.sender_mode + '-' + m.receiver_mode
          const prev = i > 0 ? res.messages[i-1] : null
          const prevKey = prev ? prev.sender_mode + '-' + prev.receiver_mode : ''
          m.showModeChange = (i === 0 || key !== prevKey)
          m.modeDesc = util.getChatModeDesc(m.sender_mode, m.receiver_mode)
          return m
        })
        this.setData({ messages: msgs })
        this.scrollToBottom()
      }
    } catch (err) {
      console.error('loadMessages error:', err)
    }
  },

  scrollToBottom() {
    setTimeout(() => {
      this.setData({ scrollTo: 'msg-end' })
    }, 100)
  },

  // 设置对话模式
  setChatMode(e) {
    const mode = e.currentTarget.dataset.mode
    const parts = mode.split('-')
    const placeholders = {
      'real-real': '以真我身份发消息...',
      'real-twin': '向对方的分身提问...',
      'twin-real': '让你的分身代你说...',
      'twin-twin': '让两个分身对话...'
    }
    this.setData({
      chatMode: mode,
      senderMode: parts[0],
      receiverMode: parts[1],
      inputPlaceholder: placeholders[mode] || '发消息...'
    })
  },

  onMsgInput(e) {
    this.setData({ inputText: e.detail.value })
  },

  // 发送消息
  async onSend() {
    const content = this.data.inputText.trim()
    if (!content) return

    this.setData({ inputText: '' })

    try {
      const res = await api.sendMessage(
        this.data.friendId,
        content,
        this.data.senderMode,
        this.data.receiverMode
      )

      if (res.success) {
        // 立即刷新消息
        await this.loadMessages()

        // 如果有AI回复，再刷新一次
        if (res.ai_reply) {
          setTimeout(() => this.loadMessages(), 500)
        }
      } else {
        wx.showToast({ title: res.error || '发送失败', icon: 'none' })
      }
    } catch (err) {
      wx.showToast({ title: '网络错误', icon: 'none' })
    }
  }
})
