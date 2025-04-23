// 基础URL配置
const API_BASE_URL = '/api';

// 统一请求处理函数
const request = async (endpoint: string, options: RequestInit = {}) => {
  const defaultHeaders = {
    'Content-Type': 'application/json',
  };

  const config: RequestInit = {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  };

  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, config);
    
    if (!response.ok) {
      throw new Error(`请求失败: ${response.status} ${response.statusText}`);
    }
    
    // 检查是否有内容返回
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
      return await response.json();
    }
    
    return await response.text();
  } catch (error) {
    console.error('API请求错误:', error);
    throw error;
  }
};

// 系统管理API
export const systemApi = {
  // 获取系统状态
  getSystemStatus: () => request('/status/'),
  
  // 获取工作进程数量
  getWorkersCount: () => request('/workers/'),
  
  // 获取队列指标
  getQueueMetrics: (queueName?: string) => {
    const endpoint = queueName ? `/queues/${queueName}/` : '/queues/';
    return request(endpoint);
  },
  
  // 获取组件状态
  getComponentStatus: (componentType?: string) => {
    const endpoint = componentType ? `/components/${componentType}/` : '/components/';
    return request(endpoint);
  },
  
  // 管理组件
  manageComponents: (data: any) => request('/manage/components/', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  
  // 扩展工作进程
  scaleWorkers: (data: any) => request('/manage/scale/', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  
  // 切换监控状态
  toggleMonitoring: (data: any) => request('/manage/monitoring/', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  
  // 获取所有任务
  getAllTasks: () => request('/tasks/'),
  
  // 创建任务
  createTask: (data: any) => request('/tasks/create/', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  
  // 管理任务
  manageTask: (taskId: string, data: any) => request(`/tasks/${taskId}/`, {
    method: 'POST',
    body: JSON.stringify(data),
  }),
};

// 站点管理API
export const siteApi = {
  // 获取站点列表
  getSites: () => request('/sites/'),
  
  // 创建站点
  createSite: (data: any) => request('/sites/', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  
  // 获取站点详情
  getSiteDetail: (siteId: string) => request(`/sites/${siteId}/`),
  
  // 更新站点
  updateSite: (siteId: string, data: any) => request(`/sites/${siteId}/`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  
  // 删除站点
  deleteSite: (siteId: string) => request(`/sites/${siteId}/`, {
    method: 'DELETE',
  }),
  
  // 获取站点状态
  getSiteStatus: (siteId: string) => request(`/sites/${siteId}/status/`),
  
  // 获取站点爬取历史
  getSiteCrawlHistory: (siteId: string) => request(`/sites/${siteId}/crawl-history/`),
};

// 爬取策略管理API
export const crawlPolicyApi = {
  // 获取爬取策略列表
  getCrawlPolicies: (siteId: string) => request(`/sites/${siteId}/crawl-policies/`),
  
  // 创建爬取策略
  createCrawlPolicy: (siteId: string, data: any) => request(`/sites/${siteId}/crawl-policies/`, {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  
  // 获取爬取策略详情
  getCrawlPolicyDetail: (siteId: string, policyId: number) => request(`/sites/${siteId}/crawl-policies/${policyId}/`),
  
  // 更新爬取策略
  updateCrawlPolicy: (siteId: string, policyId: number, data: any) => request(`/sites/${siteId}/crawl-policies/${policyId}/`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  
  // 删除爬取策略
  deleteCrawlPolicy: (siteId: string, policyId: number) => request(`/sites/${siteId}/crawl-policies/${policyId}/`, {
    method: 'DELETE',
  }),
  
  // 执行爬取策略
  executeCrawlPolicy: (siteId: string, policyId: number, data?: any) => request(`/sites/${siteId}/crawl-policies/${policyId}/execute/`, {
    method: 'POST',
    body: data ? JSON.stringify(data) : undefined,
  }),
};

// 文档管理API
export const documentApi = {
  // 获取文档列表
  getDocuments: (siteId: string, params?: any) => {
    const queryString = params ? `?${new URLSearchParams(params).toString()}` : '';
    return request(`/sites/${siteId}/documents/${queryString}`);
  },
  
  // 获取文档详情
  getDocumentDetail: (siteId: string, docId: number) => request(`/sites/${siteId}/documents/${docId}/`),
  
  // 刷新文档
  refreshDocument: (siteId: string, docId: number) => request(`/sites/${siteId}/documents/${docId}/refresh/`, {
    method: 'POST',
  }),
};

// 搜索API
export const searchApi = {
  // 基本搜索
  search: (params: any) => {
    const queryString = `?${new URLSearchParams(params).toString()}`;
    return request(`/search/${queryString}`);
  },
  
  // 语义搜索
  semanticSearch: (params: any) => {
    const queryString = `?${new URLSearchParams(params).toString()}`;
    return request(`/semantic-search/${queryString}`);
  },
  
  // 聊天搜索
  chat: (data: any) => request('/chat/', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  
  // 搜索反馈
  submitSearchFeedback: (searchLogId: number, data: any) => request(`/search-feedback/${searchLogId}/`, {
    method: 'POST',
    body: JSON.stringify(data),
  }),
};

// 定时任务API
export const scheduleApi = {
  // 创建定时任务
  createSchedule: (siteId: string, policyId: number, data: any) => request(`/sites/${siteId}/crawl-policies/${policyId}/schedule/`, {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  
  // 获取定时任务列表
  getSchedules: (siteId: string) => request(`/sites/${siteId}/schedules/`),
  
  // 获取定时任务详情
  getScheduleDetail: (siteId: string, scheduleId: number) => request(`/sites/${siteId}/schedules/${scheduleId}/`),
  
  // 更新定时任务
  updateSchedule: (siteId: string, scheduleId: number, data: any) => request(`/sites/${siteId}/schedules/${scheduleId}/`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  
  // 删除定时任务
  deleteSchedule: (siteId: string, scheduleId: number) => request(`/sites/${siteId}/schedules/${scheduleId}/`, {
    method: 'DELETE',
  }),
  
  // 切换定时任务启用状态
  toggleSchedule: (siteId: string, scheduleId: number) => request(`/sites/${siteId}/schedules/${scheduleId}/toggle/`, {
    method: 'POST',
  }),
};

// 内容刷新API
export const refreshApi = {
  // 获取刷新策略
  getRefreshPolicy: (siteId: string) => request(`/sites/${siteId}/refresh-policy/`),
  
  // 设置刷新策略
  setRefreshPolicy: (siteId: string, data: any) => request(`/sites/${siteId}/refresh-policy/`, {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  
  // 执行刷新
  executeRefresh: (siteId: string, data?: any) => request(`/sites/${siteId}/refresh/`, {
    method: 'POST',
    body: data ? JSON.stringify(data) : undefined,
  }),
};

// 导出所有API
export default {
  system: systemApi,
  site: siteApi,
  crawlPolicy: crawlPolicyApi,
  document: documentApi,
  search: searchApi,
  schedule: scheduleApi,
  refresh: refreshApi,
};