const api = require('../../utils/api')
const app = getApp()

Page({
  data: {
    userInfo: {},
    currentMode: 'real',
    twinPersonality: '',
    twinSpeechStyle: ''
  },

  onShow() {
    if (!app.checkLogin()) return
    this.loadProfile()
  },

  async loadProfile() {
    try {
      const res = await api.getProfile()
      if (res.success) {
        this.setData({
          userInfo: res.data,
          currentMode: res.data.current_mode || 'real',
          twinPersonality: res.data.twin_personality || '',
          twinSpeechStyle: res.data.twin_speech_style || ''
        })
        app.globalData.userInfo = res.data
        app.globalData.currentMode = res.data.current_mode || 'real'
      }
    } catch (err) {
      console.error('loadProfile error:', err)
    }
  },

  // 切换到真我
  switchToReal() { this.doSwitch('real') },

  // 切换到分身
  switchToTwin() { this.doSwitch('twin') },

  // 切换模式
  toggleMode() {
    const newMode = this.data.currentMode === 'real' ? 'twin' : 'real'
    this.doSwitch(newMode)
  },

  async doSwitch(mode) {
    if (mode === this.data.currentMode) return
    try {
      const res = await api.switchMode(mode)
      if (res.success) {
        this.setData({ currentMode: mode })
        app.globalData.currentMode = mode
        wx.showToast({
          title: mode === 'real' ? '已切换为真我' : '已切换为分身',
          icon: 'none'
        })
      }
    } catch (err) {
      wx.showToast({ title: '切换失败', icon: 'none' })
    }
  },

  onPersonalityInput(e) {
    this.setData({ twinPersonality: e.detail.value })
  },

  onSpeechStyleInput(e) {
    this.setData({ twinSpeechStyle: e.detail.value })
  },

  async saveProfile() {
    try {
      const res = await api.updateProfile({
        twin_personality: this.data.twinPersonality,
        twin_speech_style: this.data.twinSpeechStyle
      })
      if (res.success) {
        wx.showToast({ title: '保存成功', icon: 'success' })
      } else {
        wx.showToast({ title: res.error || '保存失败', icon: 'none' })
      }
    } catch (err) {
      wx.showToast({ title: '网络错误', icon: 'none' })
    }
  },

  openAbout() {
    wx.showModal({
      title: 'DualSoul 双魂',
      content: '双身份社交协议 (DISP) v1.0\n\n每个人同时拥有真我和AI数字分身两个身份，产生四种全新对话模式。\n\n开源项目：github.com/Chengyue5211/DualSoul\n\nMIT License',
      showCancel: false
    })
  },

  onLogout() {
    wx.showModal({
      title: '确认退出',
      content: '确定要退出登录吗？',
      success(res) {
        if (res.confirm) {
          app.logout()
        }
      }
    })
  }
})
