/**
 * DualSoul API 封装
 * 统一处理请求、认证、错误
 */

const app = getApp()

function request(url, method, data) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: app.globalData.baseUrl + url,
      method: method || 'GET',
      data: data || {},
      header: {
        'Content-Type': 'application/json',
        'Authorization': app.globalData.token ? 'Bearer ' + app.globalData.token : ''
      },
      success(res) {
        if (res.statusCode === 401) {
          app.logout()
          reject(new Error('登录已过期'))
          return
        }
        resolve(res.data)
      },
      fail(err) {
        reject(err)
      }
    })
  })
}

// ========== 认证 ==========

function register(username, password, displayName) {
  return request('/api/auth/register', 'POST', {
    username, password, display_name: displayName || username
  })
}

function login(username, password) {
  return request('/api/auth/login', 'POST', { username, password })
}

// ========== 身份 ==========

function getProfile() {
  return request('/api/identity/me')
}

function switchMode(mode) {
  return request('/api/identity/switch', 'POST', { mode })
}

function updateProfile(data) {
  return request('/api/identity/profile', 'PUT', data)
}

// ========== 社交 ==========

function addFriend(friendUsername) {
  return request('/api/social/friends/add', 'POST', { friend_username: friendUsername })
}

function respondFriend(connId, action) {
  return request('/api/social/friends/respond', 'POST', { conn_id: connId, action })
}

function getFriends() {
  return request('/api/social/friends')
}

function getMessages(friendId, limit) {
  return request('/api/social/messages?friend_id=' + friendId + '&limit=' + (limit || 50))
}

function sendMessage(toUserId, content, senderMode, receiverMode) {
  return request('/api/social/messages/send', 'POST', {
    to_user_id: toUserId,
    content,
    sender_mode: senderMode || 'real',
    receiver_mode: receiverMode || 'real',
    msg_type: 'text'
  })
}

function getUnread() {
  return request('/api/social/unread')
}

module.exports = {
  register, login,
  getProfile, switchMode, updateProfile,
  addFriend, respondFriend, getFriends,
  getMessages, sendMessage, getUnread
}
