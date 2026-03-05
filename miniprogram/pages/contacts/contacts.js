const api = require('../../utils/api')
const app = getApp()

Page({
  data: {
    userInfo: {},
    currentMode: 'real',
    friends: [],
    pendingRequests: [],
    searchText: ''
  },

  onShow() {
    if (!app.checkLogin()) return
    this.setData({
      userInfo: app.globalData.userInfo || {},
      currentMode: app.globalData.currentMode || 'real'
    })
    this.loadFriends()
  },

  async loadFriends() {
    try {
      const res = await api.getFriends()
      if (res.success) {
        const friends = []
        const pending = []
        res.friends.forEach(f => {
          if (f.status === 'accepted') {
            friends.push(f)
          } else if (f.status === 'pending' && f.is_incoming) {
            pending.push(f)
          }
        })
        this.setData({ friends, pendingRequests: pending })
      }
    } catch (err) {
      console.error('loadFriends error:', err)
    }
  },

  // 切换身份
  async switchIdentity() {
    const newMode = this.data.currentMode === 'real' ? 'twin' : 'real'
    try {
      const res = await api.switchMode(newMode)
      if (res.success) {
        app.globalData.currentMode = newMode
        this.setData({ currentMode: newMode })
        wx.showToast({
          title: newMode === 'real' ? '已切换为真我' : '已切换为分身',
          icon: 'none'
        })
      }
    } catch (err) {
      wx.showToast({ title: '切换失败', icon: 'none' })
    }
  },

  onSearchInput(e) {
    this.setData({ searchText: e.detail.value })
  },

  // 添加好友
  async onAddFriend() {
    const username = this.data.searchText.trim()
    if (!username) return
    try {
      const res = await api.addFriend(username)
      if (res.success) {
        wx.showToast({ title: '好友请求已发送', icon: 'success' })
        this.setData({ searchText: '' })
      } else {
        wx.showToast({ title: res.error || '添加失败', icon: 'none' })
      }
    } catch (err) {
      wx.showToast({ title: '网络错误', icon: 'none' })
    }
  },

  // 接受好友
  async onAccept(e) {
    const connId = e.currentTarget.dataset.conn
    try {
      const res = await api.respondFriend(connId, 'accept')
      if (res.success) {
        wx.showToast({ title: '已添加好友', icon: 'success' })
        this.loadFriends()
      }
    } catch (err) {
      wx.showToast({ title: '操作失败', icon: 'none' })
    }
  },

  // 拒绝好友
  async onBlock(e) {
    const connId = e.currentTarget.dataset.conn
    try {
      await api.respondFriend(connId, 'block')
      this.loadFriends()
    } catch (err) {
      wx.showToast({ title: '操作失败', icon: 'none' })
    }
  },

  // 进入聊天
  onChat(e) {
    const friend = e.currentTarget.dataset.friend
    wx.navigateTo({
      url: '/pages/chat/chat?friendId=' + friend.user_id +
           '&friendName=' + encodeURIComponent(friend.display_name) +
           '&friendMode=' + friend.current_mode
    })
  }
})
