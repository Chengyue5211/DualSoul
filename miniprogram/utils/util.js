/**
 * 工具函数
 */

// 格式化时间
function formatTime(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now - date

  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return Math.floor(diff / 60000) + '分钟前'
  if (diff < 86400000) return Math.floor(diff / 3600000) + '小时前'

  const month = date.getMonth() + 1
  const day = date.getDate()
  const hour = String(date.getHours()).padStart(2, '0')
  const min = String(date.getMinutes()).padStart(2, '0')
  return month + '/' + day + ' ' + hour + ':' + min
}

// 获取模式显示名
function getModeName(mode) {
  return mode === 'twin' ? '分身' : '真我'
}

// 获取对话模式描述
function getChatModeDesc(senderMode, receiverMode) {
  const map = {
    'real-real': '真人对真人',
    'real-twin': '真人对分身',
    'twin-real': '分身对真人',
    'twin-twin': '分身对分身'
  }
  return map[senderMode + '-' + receiverMode] || ''
}

// 获取默认头像
function getAvatar(avatar, mode) {
  if (avatar) return avatar
  return mode === 'twin' ? '/images/default-twin.png' : '/images/default-real.png'
}

module.exports = { formatTime, getModeName, getChatModeDesc, getAvatar }
