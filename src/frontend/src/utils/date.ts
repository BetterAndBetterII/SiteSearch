/**
 * 将时间戳或日期对象格式化为易读的日期格式
 * @param input 时间戳（毫秒）或日期对象
 * @returns 格式化后的日期字符串
 */
export const formatDate = (input: number | Date): string => {
  const date = input instanceof Date ? input : new Date(input);
  
  // 获取当前日期
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  
  // 如果是今天
  if (date >= today) {
    return '今天 ' + date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  }
  
  // 如果是昨天
  if (date >= yesterday) {
    return '昨天 ' + date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  }
  
  // 如果是今年
  if (date.getFullYear() === now.getFullYear()) {
    return date.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' });
  }
  
  // 其他情况显示完整日期
  return date.toLocaleDateString('zh-CN', { year: 'numeric', month: 'numeric', day: 'numeric' });
}; 