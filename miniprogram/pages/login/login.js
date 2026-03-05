const api = require('../../utils/api')
const app = getApp()

Page({
  data: {
    isRegister: false,
    username: '',
    password: '',
    displayName: '',
    loading: false
  },

  onUsernameInput(e) { this.setData({ username: e.detail.value }) },
  onPasswordInput(e) { this.setData({ password: e.detail.value }) },
  onDisplayNameInput(e) { this.setData({ displayName: e.detail.value }) },

  toggleMode() {
    this.setData({ isRegister: !this.data.isRegister })
  },

  async onSubmit() {
    const { username, password, displayName, isRegister } = this.data
    if (!username.trim() || !password) {
      wx.showToast({ title: '请填写用户名和密码', icon: 'none' })
      return
    }

    this.setData({ loading: true })
    try {
      let res
      if (isRegister) {
        res = await api.register(username.trim(), password, displayName.trim())
      } else {
        res = await api.login(username.trim(), password)
      }

      if (res.success) {
        // 获取完整的用户信息
        app.setLogin(res.data.token, res.data)

        // 获取profile
        const profile = await api.getProfile()
        if (profile.success) {
          app.globalData.userInfo = profile.data
          app.globalData.currentMode = profile.data.current_mode || 'real'
          wx.setStorageSync('userInfo', profile.data)
        }

        wx.switchTab({ url: '/pages/contacts/contacts' })
      } else {
        wx.showToast({ title: res.error || '操作失败', icon: 'none' })
      }
    } catch (err) {
      wx.showToast({ title: '网络错误，请重试', icon: 'none' })
    }
    this.setData({ loading: false })
  },

  onLoad() {
    // 已登录直接跳转
    if (app.globalData.token) {
      wx.switchTab({ url: '/pages/contacts/contacts' })
    }
  }
})
