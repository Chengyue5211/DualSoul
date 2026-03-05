App({
  globalData: {
    baseUrl: 'https://47.93.149.187:8080',  // TODO: 上线后换成正式域名
    token: '',
    userInfo: null,
    currentMode: 'real'  // 'real' or 'twin'
  },

  onLaunch() {
    // 读取本地缓存的登录信息
    const token = wx.getStorageSync('token')
    const userInfo = wx.getStorageSync('userInfo')
    if (token && userInfo) {
      this.globalData.token = token
      this.globalData.userInfo = userInfo
      this.globalData.currentMode = userInfo.current_mode || 'real'
    }
  },

  // 保存登录状态
  setLogin(token, userInfo) {
    this.globalData.token = token
    this.globalData.userInfo = userInfo
    this.globalData.currentMode = userInfo.current_mode || 'real'
    wx.setStorageSync('token', token)
    wx.setStorageSync('userInfo', userInfo)
  },

  // 退出登录
  logout() {
    this.globalData.token = ''
    this.globalData.userInfo = null
    this.globalData.currentMode = 'real'
    wx.clearStorageSync()
    wx.reLaunch({ url: '/pages/login/login' })
  },

  // 检查是否登录
  checkLogin() {
    if (!this.globalData.token) {
      wx.reLaunch({ url: '/pages/login/login' })
      return false
    }
    return true
  }
})
