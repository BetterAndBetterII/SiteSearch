import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { siteApi, refreshApi } from '../api';
import { RefreshPolicyFormModal } from '../components/RefreshPolicyFormModal';

// 简单的Spinner组件
const Spinner = () => (
  <div className="animate-spin h-5 w-5 border-2 border-current border-t-transparent rounded-full" 
       aria-label="正在加载"></div>
);

// 刷新策略类型定义
interface RefreshPolicy {
  id: number;
  name: string;
  description: string;
  strategy: string;
  refresh_interval_days: number;
  url_patterns: string[];
  exclude_patterns: string[];
  max_age_days: number;
  priority_patterns: string[];
  enabled: boolean;
  last_refresh: string | null;
  next_refresh: string | null;
  created_at: string;
  updated_at: string;
}

// 站点信息类型
interface Site {
  id: string;
  name: string;
  baseUrl: string;
  description: string;
}

export function RefreshPolicyPage() {
  // 从React Router获取siteId参数
  const { siteId } = useParams<{ siteId: string }>();
  
  const [site, setSite] = useState<Site | null>(null);
  const [policy, setPolicy] = useState<RefreshPolicy | null>(null);
  const [loading, setLoading] = useState(true);
  const [executing, setExecuting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  
  // 加载站点和刷新策略数据
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
        
        // 获取刷新策略
        try {
          const policyResponse = await refreshApi.getRefreshPolicy(siteId);
          setPolicy(policyResponse);
        } catch (policyErr: any) {
          // 如果是404错误，说明还没有创建刷新策略，这不是错误
          if (policyErr.message && policyErr.message.includes('404')) {
            setPolicy(null);
          } else {
            throw policyErr;
          }
        }
        
      } catch (err) {
        console.error('获取数据失败', err);
        setError('无法加载站点和刷新策略数据');
      } finally {
        setLoading(false);
      }
    };
    
    fetchData();
  }, [siteId]);
  
  // 执行内容刷新
  const executeRefresh = async () => {
    if (!siteId) return;
    
    try {
      setExecuting(true);
      await refreshApi.executeRefresh(siteId);
      
      // 更新策略以反映最新刷新时间
      await refreshPolicy();
      
      // 显示成功消息
      alert('内容刷新任务已成功启动');
    } catch (err) {
      console.error('执行内容刷新失败', err);
      setError('启动内容刷新任务失败，请稍后重试');
    } finally {
      setExecuting(false);
    }
  };
  
  // 切换刷新策略启用状态
  const togglePolicyEnabled = async () => {
    if (!siteId || !policy) return;
    
    try {
      await refreshApi.updateRefreshPolicy(siteId, {
        ...policy,
        enabled: !policy.enabled
      });
      
      // 刷新策略数据
      await refreshPolicy();
      
    } catch (err) {
      console.error('更新刷新策略失败', err);
      setError('更新策略状态失败');
    }
  };
  
  // 刷新策略数据
  const refreshPolicy = async () => {
    if (!siteId) return;
    
    try {
      const policyResponse = await refreshApi.getRefreshPolicy(siteId);
      setPolicy(policyResponse);
    } catch (err) {
      console.error('刷新策略数据失败', err);
    }
  };
  
  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Spinner />
        <span className="ml-2">加载刷新策略数据...</span>
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
          <h1 className="text-2xl font-bold">内容刷新策略</h1>
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
            setShowModal(true);
          }}>
            {policy ? '编辑策略' : '添加策略'}
          </Button>
        </div>
      </div>
      
      {!policy ? (
        <div className="text-center p-8 bg-muted rounded-lg">
          <p className="text-muted-foreground">暂无内容刷新策略</p>
          <Button 
            className="mt-4" 
            onClick={() => {
              setShowModal(true);
            }}
          >
            添加刷新策略
          </Button>
        </div>
      ) : (
        <div className="bg-card border border-border rounded-md p-4">
          <div className="flex justify-between items-start mb-4">
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-medium">{policy.name}</h3>
                <span className={`px-2 py-0.5 text-xs rounded-full ${
                  policy.enabled ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                }`}>
                  {policy.enabled ? '已启用' : '已禁用'}
                </span>
              </div>
              <p className="text-sm text-muted-foreground">{policy.description || '无描述'}</p>
            </div>
            <div className="flex space-x-2">
              <Button 
                variant="outline" 
                size="sm"
                onClick={executeRefresh}
                disabled={executing || !policy.enabled}
              >
                {executing ? (
                  <span className="flex items-center">
                    <Spinner />
                    <span className="ml-1">执行中</span>
                  </span>
                ) : '执行刷新'}
              </Button>
              <Button 
                variant={policy.enabled ? 'destructive' : 'default'}
                size="sm"
                onClick={togglePolicyEnabled}
              >
                {policy.enabled ? '禁用' : '启用'}
              </Button>
              <Button 
                variant="outline" 
                size="sm"
                onClick={() => setShowModal(true)}
              >
                编辑
              </Button>
            </div>
          </div>
          
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <div>
                <p className="text-sm font-medium">刷新策略类型</p>
                <p className="text-sm text-muted-foreground capitalize">
                  {policy.strategy === 'incremental' && '增量刷新'}
                  {policy.strategy === 'all' && '全量刷新'}
                  {policy.strategy === 'selective' && '选择性刷新'}
                </p>
              </div>
              
              <div>
                <p className="text-sm font-medium">刷新间隔</p>
                <p className="text-sm text-muted-foreground">
                  {policy.refresh_interval_days} 天
                </p>
              </div>
              
              <div>
                <p className="text-sm font-medium">内容最大有效期</p>
                <p className="text-sm text-muted-foreground">
                  {policy.max_age_days} 天
                </p>
              </div>
            </div>
            
            <div className="space-y-2">
              <div>
                <p className="text-sm font-medium">上次刷新时间</p>
                <p className="text-sm text-muted-foreground">
                  {policy.last_refresh 
                    ? new Date(policy.last_refresh).toLocaleString() 
                    : '从未刷新'}
                </p>
              </div>
              
              <div>
                <p className="text-sm font-medium">下次计划刷新时间</p>
                <p className="text-sm text-muted-foreground">
                  {policy.next_refresh 
                    ? new Date(policy.next_refresh).toLocaleString() 
                    : '未计划'}
                </p>
              </div>
              
              <div>
                <p className="text-sm font-medium">创建时间</p>
                <p className="text-sm text-muted-foreground">
                  {new Date(policy.created_at).toLocaleString()}
                </p>
              </div>
            </div>
            
            <div className="space-y-2">
              <p className="text-sm font-medium">URL匹配模式</p>
              <div className="bg-muted p-2 rounded text-xs max-h-32 overflow-y-auto">
                {policy.url_patterns.length > 0 ? (
                  policy.url_patterns.map((pattern, index) => (
                    <div key={index} className="mb-1 font-mono break-all">{pattern}</div>
                  ))
                ) : (
                  <p className="text-muted-foreground">未指定URL模式</p>
                )}
              </div>
            </div>
            
            <div className="space-y-2">
              <p className="text-sm font-medium">排除URL模式</p>
              <div className="bg-muted p-2 rounded text-xs max-h-32 overflow-y-auto">
                {policy.exclude_patterns.length > 0 ? (
                  policy.exclude_patterns.map((pattern, index) => (
                    <div key={index} className="mb-1 font-mono break-all">{pattern}</div>
                  ))
                ) : (
                  <p className="text-muted-foreground">未指定排除模式</p>
                )}
              </div>
            </div>
            
            <div className="space-y-2 md:col-span-2">
              <p className="text-sm font-medium">优先刷新URL模式</p>
              <div className="bg-muted p-2 rounded text-xs max-h-24 overflow-y-auto">
                {policy.priority_patterns.length > 0 ? (
                  policy.priority_patterns.map((pattern, index) => (
                    <div key={index} className="mb-1 font-mono break-all">{pattern}</div>
                  ))
                ) : (
                  <p className="text-muted-foreground">未指定优先刷新模式</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
      
      {/* 添加/编辑刷新策略模态框 */}
      {siteId && (
        <RefreshPolicyFormModal
          isOpen={showModal}
          onClose={() => {
            setShowModal(false);
          }}
          onSuccess={() => {
            refreshPolicy();
            setShowModal(false);
          }}
          siteId={siteId}
          editPolicy={policy || undefined}
        />
      )}
    </div>
  );
} 