import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { siteApi, crawlPolicyApi, scheduleApi } from '../api';
import { CrawlPolicyFormModal } from '../components/CrawlPolicyFormModal';

// 简单的Spinner组件
const Spinner = () => (
  <div className="animate-spin h-5 w-5 border-2 border-current border-t-transparent rounded-full" 
       aria-label="正在加载"></div>
);

// 爬取策略类型定义
interface CrawlPolicy {
  id: number;
  name: string;
  description: string;
  start_urls: string[];
  url_patterns: string[];
  exclude_patterns: string[];
  max_depth: number;
  max_urls: number;
  crawler_type: string;
  enabled: boolean;
  last_executed: string | null;
}

// 站点信息类型
interface Site {
  id: string;
  name: string;
  baseUrl: string;
  description: string;
}

// 定时任务类型定义
interface Schedule {
  id: number;
  name: string;
  schedule_type: string;
  interval_seconds?: number;
  enabled: boolean;
  policy_id: number;
}

export function CrawlPoliciesPage() {
  // 从React Router获取siteId参数
  const { siteId } = useParams<{ siteId: string }>();
  
  const [site, setSite] = useState<Site | null>(null);
  const [policies, setPolicies] = useState<CrawlPolicy[]>([]);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [executing, setExecuting] = useState<number | null>(null);
  const [savingSchedule, setSavingSchedule] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [editingPolicy, setEditingPolicy] = useState<CrawlPolicy | null>(null);
  
  // 加载站点和爬取策略数据
  useEffect(() => {
    const fetchData = async () => {
      if (!siteId) {
        setError('未提供站点ID');
        setLoading(false);
        return;
      }
      
      try {
        setLoading(true);
        
        // 获取站点信息
        const siteResponse = await siteApi.getSiteDetail(siteId);
        setSite({
          id: siteResponse.id,
          name: siteResponse.name,
          baseUrl: siteResponse.base_url,
          description: siteResponse.description
        });
        
        // 获取爬取策略列表
        const policiesResponse = await crawlPolicyApi.getCrawlPolicies(siteId);
        setPolicies(policiesResponse.results || []);
        
        // 获取定时任务列表
        const schedulesResponse = await scheduleApi.getSchedules(siteId);
        setSchedules(schedulesResponse.results || []);
        
      } catch (err) {
        console.error('获取数据失败', err);
        setError('无法加载站点和爬取策略数据');
      } finally {
        setLoading(false);
      }
    };
    
    fetchData();
  }, [siteId]);
  
  // 执行爬取策略
  const executeCrawlPolicy = async (policyId: number) => {
    if (!siteId) return;
    
    try {
      setExecuting(policyId);
      await crawlPolicyApi.executeCrawlPolicy(siteId, policyId);
      
      // 更新策略列表以反映最新执行时间
      const updatedPolicies = [...policies];
      const index = updatedPolicies.findIndex(policy => policy.id === policyId);
      
      if (index !== -1) {
        updatedPolicies[index] = {
          ...updatedPolicies[index],
          last_executed: new Date().toISOString()
        };
        
        setPolicies(updatedPolicies);
      }
      
      // 显示成功消息
      alert('爬取任务已成功启动');
    } catch (err) {
      console.error('执行爬取策略失败', err);
      setError('启动爬取任务失败，请稍后重试');
    } finally {
      setExecuting(null);
    }
  };
  
  // 切换爬取策略启用状态
  const togglePolicyEnabled = async (policyId: number, currentEnabled: boolean) => {
    if (!siteId) return;
    
    try {
      await crawlPolicyApi.updateCrawlPolicy(siteId, policyId, {
        enabled: !currentEnabled
      });
      
      // 更新本地策略状态
      setPolicies(policies.map(policy => 
        policy.id === policyId 
          ? { ...policy, enabled: !currentEnabled }
          : policy
      ));
      
    } catch (err) {
      console.error('更新爬取策略失败', err);
      setError('更新策略状态失败');
    }
  };
  
  // 删除爬取策略
  const deletePolicy = async (policyId: number) => {
    if (!siteId) return;
    
    if (!confirm('确定要删除此爬取策略吗？此操作无法撤销。')) {
      return;
    }
    
    try {
      await crawlPolicyApi.deleteCrawlPolicy(siteId, policyId);
      
      // 从列表中移除已删除的策略
      setPolicies(policies.filter(policy => policy.id !== policyId));
      
    } catch (err) {
      console.error('删除爬取策略失败', err);
      setError('删除策略失败');
    }
  };
  
  // 编辑爬取策略
  const editPolicy = (policy: CrawlPolicy) => {
    setEditingPolicy(policy);
    setShowModal(true);
  };
  
  // 刷新策略列表
  const refreshPolicies = async () => {
    if (!siteId) return;
    
    try {
      const policiesResponse = await crawlPolicyApi.getCrawlPolicies(siteId);
      setPolicies(policiesResponse.results || []);
      
      // 刷新定时任务列表
      const schedulesResponse = await scheduleApi.getSchedules(siteId);
      setSchedules(schedulesResponse.results || []);
    } catch (err) {
      console.error('刷新策略列表失败', err);
    }
  };
  
  // 更新定时任务
  const updateSchedule = async (policyId: number, scheduleOption: string) => {
    if (!siteId) return;
    
    try {
      setSavingSchedule(policyId);
      
      // 查找策略的已有定时任务
      const existingSchedule = schedules.find(s => s.policy_id === policyId);
      
      // 根据选项创建或更新定时任务
      if (scheduleOption === 'never') {
        // 如果有现有任务，禁用或删除它
        if (existingSchedule) {
          if (existingSchedule.enabled) {
            await scheduleApi.toggleSchedule(siteId, existingSchedule.id);
          }
        }
      } else {
        // 计算间隔秒数
        let intervalSeconds = 0;
        if (scheduleOption === 'daily') {
          intervalSeconds = 24 * 60 * 60; // 每天
        } else if (scheduleOption === 'weekly') {
          intervalSeconds = 7 * 24 * 60 * 60; // 每7天
        }
        
        if (existingSchedule) {
          // 更新现有任务
          await scheduleApi.updateSchedule(siteId, existingSchedule.id, {
            schedule_type: 'interval',
            interval_seconds: intervalSeconds,
            enabled: true
          });
        } else {
          // 创建新任务
          const policy = policies.find(p => p.id === policyId);
          if (policy) {
            await scheduleApi.createSchedule(siteId, policyId, {
              name: `${policy.name}的定时执行`,
              description: `自动创建的定时执行计划`,
              schedule_type: 'interval',
              interval_seconds: intervalSeconds,
              enabled: true
            });
          }
        }
      }
      
      // 刷新任务列表
      const schedulesResponse = await scheduleApi.getSchedules(siteId);
      setSchedules(schedulesResponse.results || []);
      
    } catch (err) {
      console.error('更新定时任务失败', err);
      setError('更新定时任务失败，请稍后重试');
    } finally {
      setSavingSchedule(null);
    }
  };
  
  // 获取策略的定时任务选项值
  const getScheduleOption = (policyId: number) => {
    const schedule = schedules.find(s => s.policy_id === policyId);
    if (!schedule || !schedule.enabled) {
      return 'never';
    }
    
    if (schedule.schedule_type === 'interval') {
      if (schedule.interval_seconds === 24 * 60 * 60) {
        return 'daily';
      } else if (schedule.interval_seconds === 7 * 24 * 60 * 60) {
        return 'weekly';
      }
    }
    
    return 'never';
  };
  
  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Spinner />
        <span className="ml-2">加载爬取策略数据...</span>
      </div>
    );
  }
  
  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-md">
        <p>{error}</p>
        <Button 
          variant="outline" 
          className="mt-2" 
          onClick={() => window.location.reload()}
        >
          重试
        </Button>
      </div>
    );
  }
  
  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold">爬取策略管理</h1>
          {site && (
            <p className="text-muted-foreground">
              站点: <span className="font-medium">{site.name}</span>
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <Button 
            variant="outline"
            asChild
          >
            <Link to="/sites">返回站点列表</Link>
          </Button>
          <Button onClick={() => {
            setEditingPolicy(null);
            setShowModal(true);
          }}>
            添加策略
          </Button>
        </div>
      </div>
      
      {policies.length === 0 ? (
        <div className="text-center p-8 bg-muted rounded-lg">
          <p className="text-muted-foreground">暂无爬取策略</p>
          <Button 
            className="mt-4" 
            onClick={() => {
              setEditingPolicy(null);
              setShowModal(true);
            }}
          >
            添加第一个爬取策略
          </Button>
        </div>
      ) : (
        <div className="grid gap-4">
          {policies.map((policy) => (
            <div key={policy.id} className="bg-card border border-border rounded-md p-4">
              <div className="flex justify-between items-start mb-2">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-lg font-medium">{policy.name}</h3>
                    <span className={`px-2 py-0.5 text-xs rounded-full ${
                      policy.enabled ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                    }`}>
                      {policy.enabled ? '已启用' : '已禁用'}
                    </span>
                  </div>
                  <p className="text-sm text-muted-foreground">{policy.description}</p>
                </div>
                <div className="flex space-x-2">
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={() => executeCrawlPolicy(policy.id)}
                    disabled={executing === policy.id || !policy.enabled}
                  >
                    {executing === policy.id ? (
                      <span className="flex items-center">
                        <Spinner />
                        <span className="ml-1">执行中</span>
                      </span>
                    ) : '执行爬取'}
                  </Button>
                  <Button 
                    variant={policy.enabled ? 'destructive' : 'default'}
                    size="sm"
                    onClick={() => togglePolicyEnabled(policy.id, policy.enabled)}
                  >
                    {policy.enabled ? '禁用' : '启用'}
                  </Button>
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={() => editPolicy(policy)}
                  >
                    编辑
                  </Button>
                  <Button 
                    variant="ghost" 
                    size="sm"
                    onClick={() => deletePolicy(policy.id)}
                  >
                    删除
                  </Button>
                </div>
              </div>
              
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <p className="text-sm font-medium">起始URL</p>
                  <div className="bg-muted p-2 rounded text-xs max-h-24 overflow-y-auto">
                    {policy.start_urls.map((url, index) => (
                      <div key={index} className="mb-1 break-all">{url}</div>
                    ))}
                  </div>
                </div>
                
                <div className="space-y-2">
                  <p className="text-sm font-medium">URL模式</p>
                  <div className="bg-muted p-2 rounded text-xs max-h-24 overflow-y-auto">
                    {policy.url_patterns.length > 0 ? (
                      policy.url_patterns.map((pattern, index) => (
                        <div key={index} className="mb-1 font-mono break-all">{pattern}</div>
                      ))
                    ) : (
                      <p className="text-muted-foreground">未指定URL模式</p>
                    )}
                  </div>
                </div>
                
                <div>
                  <p className="text-sm font-medium">排除模式</p>
                  <div className="bg-muted p-2 rounded text-xs max-h-24 overflow-y-auto">
                    {policy.exclude_patterns.length > 0 ? (
                      policy.exclude_patterns.map((pattern, index) => (
                        <div key={index} className="mb-1 font-mono break-all">{pattern}</div>
                      ))
                    ) : (
                      <p className="text-muted-foreground">未指定排除模式</p>
                    )}
                  </div>
                </div>
                
                <div className="space-y-2">
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <p className="text-sm font-medium">爬取限制</p>
                      <p className="text-xs text-muted-foreground">
                        最大深度: {policy.max_depth}, 最大URL: {policy.max_urls}
                      </p>
                    </div>
                    <div>
                      <p className="text-sm font-medium">爬虫类型</p>
                      <p className="text-xs text-muted-foreground capitalize">
                        {policy.crawler_type}
                      </p>
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <p className="text-sm font-medium">上次执行</p>
                      <p className="text-xs text-muted-foreground">
                        {policy.last_executed 
                          ? new Date(policy.last_executed).toLocaleString() 
                          : '从未执行'}
                      </p>
                    </div>
                    <div>
                      <p className="text-sm font-medium">定时执行</p>
                      <div className="flex items-center gap-2">
                        <select
                          className="text-xs border border-gray-300 rounded p-1"
                          value={getScheduleOption(policy.id)}
                          onChange={(e) => updateSchedule(policy.id, e.target.value)}
                          disabled={savingSchedule === policy.id || !policy.enabled}
                        >
                          <option value="never">从不</option>
                          <option value="daily">每天</option>
                          <option value="weekly">每7天</option>
                        </select>
                        {savingSchedule === policy.id && (
                          <Spinner />
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
      
      {/* 添加/编辑爬取策略模态框 */}
      {siteId && (
        <CrawlPolicyFormModal
          isOpen={showModal}
          onClose={() => {
            setShowModal(false);
            setEditingPolicy(null);
          }}
          onSuccess={() => {
            refreshPolicies();
            setShowModal(false);
            setEditingPolicy(null);
          }}
          siteId={siteId}
          editPolicy={editingPolicy || undefined}
        />
      )}
    </div>
  );
} 