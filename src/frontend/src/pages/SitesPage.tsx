import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { siteApi, crawlPolicyApi, systemApi, documentApi } from '../api';
import { SiteAddModal } from '../components/SiteAddModal';
import { SiteDeleteModal } from '../components/SiteDeleteModal';  
import { useToast } from '../components/ui/toast';

// 简单的Spinner组件
const Spinner = () => (
  <div className="animate-spin h-5 w-5 border-2 border-current border-t-transparent rounded-full" 
       aria-label="正在加载"></div>
);

// 定义站点类型
interface Site {
  id: string;
  name: string;
  baseUrl: string;
  description: string;
  enabled: boolean;
  lastCrawlTime: string | null;
  pagesCrawled: number;
  status: string;
}

export function SitesPage() {
  const { toast } = useToast();
  const [sites, setSites] = useState<Site[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [deletingSite, setDeletingSite] = useState<string | null>(null);
  const [showDeleteConfirmation, setShowDeleteConfirmation] = useState(false);
  
  // 加载站点数据
  const fetchSites = async () => {
    try {
      setLoading(true);
      const response = await siteApi.getSites();
      
      // 将API响应转换为站点列表
      const formattedSites = response.results.map((site: any) => ({
        id: site.id,
        name: site.name,
        baseUrl: site.base_url,
        description: site.description,
        enabled: site.enabled,
        lastCrawlTime: site.last_crawl_time,
        pagesCrawled: site.total_documents || 0,
        status: 'idle' // 默认状态，稍后会检查并更新
      }));
      
      // 获取每个站点的状态
      const sitesWithStatus = await Promise.all(
        formattedSites.map(async (site: Site) => {
          try {
            const statusResponse = await siteApi.getSiteStatus(site.id);
            // 根据队列状态判断站点是否正在爬取
            const hasActiveTasks = statusResponse.tasks && 
              statusResponse.tasks.some((task: any) => task.status === 'running');
            
            return {
              ...site,
              status: hasActiveTasks ? 'active' : 'idle'
            };
          } catch (err) {
            console.error(`获取站点${site.id}状态失败`, err);
            return site;
          }
        })
      );
      
      setSites(sitesWithStatus);
    } catch (err) {
      console.error('获取站点列表失败', err);
      setError('获取站点数据失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  // 手动索引未索引的文档
  const indexDocuments = async () => {
    try {
      await documentApi.indexDocument();
      toast({
        title: '手动索引未索引的文档成功',
      });
    } catch (err) {
      console.error('手动索引未索引的文档失败', err);
      toast({
        title: '手动索引未索引的文档失败',
        description: err instanceof Error ? err.message : '未知错误',
      });
    }
  };

  // 首次加载时获取站点列表
  useEffect(() => {
    fetchSites();
  }, []);
  
  const startCrawling = async (siteId: string) => {
    try {
      // 获取站点的爬取策略
      const policiesResponse = await crawlPolicyApi.getCrawlPolicies(siteId);
      
      if (policiesResponse.results && policiesResponse.results.length > 0) {
        // 使用第一个爬取策略
        const policyId = policiesResponse.results[0].id;
        
        // 执行爬取策略
        await crawlPolicyApi.executeCrawlPolicy(siteId, policyId);
        
        // 更新站点状态
        setSites(prevSites => 
          prevSites.map(site => 
            site.id === siteId ? { ...site, status: 'active' } : site
          )
        );
      } else {
        setError(`站点 ${siteId} 没有可用的爬取策略`);
      }
    } catch (err) {
      console.error(`开始爬取站点 ${siteId} 失败`, err);
      setError('启动爬取失败，请稍后重试');
    }
  };
  
  const stopCrawling = async (siteId: string) => {
    try {
      // 获取站点状态以查找正在运行的任务
      const statusResponse = await siteApi.getSiteStatus(siteId);
      
      if (statusResponse.tasks) {
        const runningTasks = statusResponse.tasks.filter((task: any) => task.status === 'running');
        
        // 停止所有正在运行的任务
        await Promise.all(
          runningTasks.map((task: any) => 
            systemApi.manageTask(task.id, { action: 'stop' })
          )
        );
        
        // 更新站点状态
        setSites(prevSites => 
          prevSites.map(site => 
            site.id === siteId ? { ...site, status: 'idle' } : site
          )
        );
      }
    } catch (err) {
      console.error(`停止爬取站点 ${siteId} 失败`, err);
      setError('停止爬取失败，请稍后重试');
    }
  };
  
  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Spinner />
        <span className="ml-2">加载站点数据...</span>
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
        <h1 className="text-2xl font-bold">站点管理</h1>
        <div className="flex space-x-2">
          <Button onClick={() => setShowModal(true)}>添加站点</Button>
          <Button onClick={indexDocuments}>手动索引未索引的文档</Button>
        </div>
      </div>
      
      {sites.length === 0 ? (
        <div className="text-center p-8 bg-muted rounded-lg">
          <p className="text-muted-foreground">暂无站点数据</p>
          <Button className="mt-4" onClick={() => setShowModal(true)}>
            添加第一个站点
          </Button>
        </div>
      ) : (
        <div className="grid gap-4">
          {sites.map((site) => (
            <div key={site.id} className="bg-card border border-border rounded-md p-4">
              <div className="flex justify-between items-start mb-2">
                <div>
                  <h3 className="text-lg font-medium">{site.name}</h3>
                  <p className="text-sm text-muted-foreground">{site.baseUrl}</p>
                </div>
                <div className="flex space-x-2">
                  {site.status === 'active' ? (
                    <Button 
                      variant="outline" 
                      size="sm" 
                      className="text-red-500 border-red-200 hover:bg-red-50 hover:text-red-600"
                      onClick={() => stopCrawling(site.id)}
                    >
                      停止爬取
                    </Button>
                  ) : (
                    <Button 
                      variant="outline" 
                      size="sm"
                      onClick={() => startCrawling(site.id)}
                      disabled={!site.enabled}
                    >
                      开始爬取
                    </Button>
                  )}
                  <Button 
                    variant="ghost" 
                    size="sm"
                    asChild
                  >
                    <Link to={`/sites/${site.id}/policy`}>爬取策略</Link>
                  </Button>
                  <Button 
                    variant="ghost" 
                    size="sm"
                    asChild
                  >
                    <Link to={`/sites/${site.id}/refresh`}>刷新策略</Link>
                  </Button>
                  <Button 
                    variant="ghost" 
                    size="sm"
                    asChild
                  >
                    <Link to={`/sites/${site.id}/documents`}>文档</Link>
                  </Button>
                  <Button 
                    variant="ghost" 
                    size="sm"
                    onClick={() => {
                      setDeletingSite(site.id);
                      setShowDeleteConfirmation(true);
                    }}
                    className="text-red-500 border-red-200 hover:bg-red-50 hover:text-red-600"
                  >
                    删除
                  </Button>
                </div>
              </div>
              
              <p className="text-sm mb-3">{site.description}</p>
              
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-muted-foreground">状态</p>
                  <p>
                    <span className={`inline-block w-2 h-2 rounded-full mr-1 ${
                      site.status === 'active' ? 'bg-green-500' : 
                      site.enabled ? 'bg-yellow-500' : 'bg-gray-500'
                    }`}></span>
                    {site.status === 'active' ? '正在爬取' : 
                     site.enabled ? '待机中' : '已禁用'}
                  </p>
                </div>
                <div>
                  <p className="text-muted-foreground">已索引页面</p>
                  <p>{site.pagesCrawled} 页</p>
                </div>
                <div>
                  <p className="text-muted-foreground">上次爬取</p>
                  <p>{site.lastCrawlTime ? new Date(site.lastCrawlTime).toLocaleString() : '从未爬取'}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
      
      {/* 添加站点的模态框 */}
      <SiteAddModal
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        onSuccess={() => {
          setShowModal(false);
          fetchSites(); // 刷新站点列表
        }}
      />
      {showDeleteConfirmation && (
        <SiteDeleteModal
          isOpen={showDeleteConfirmation}
          onClose={() => setShowDeleteConfirmation(false)}
          onSuccess={() => {
            setShowDeleteConfirmation(false);
            fetchSites(); // 刷新站点列表
          }}
          siteId={deletingSite || ''}
        />
      )}
    </div>
  );
} 