import { useState, useEffect, useCallback } from 'react';
import { Button } from '../components/ui/button';
import { systemApi } from '../api';
import { AlertCircle, RefreshCw } from 'lucide-react';
import { useToast } from '../components/ui/toast';
import { ComponentDetailsCard } from '../components/ComponentDetails';
import { SystemStatus } from '../api/types';
import { RedisStatsCard } from '../components/RedisStatsCard';
import { MainProcessCard } from '../components/MainProcessCard';

// 简单的Spinner组件
const Spinner = () => (
  <div className="animate-spin h-5 w-5 border-2 border-current border-t-transparent rounded-full" 
       aria-label="正在加载"></div>
);

type BasicComponentStatus = {
  id: string;
  type: string;
  status: string;
  total_memory_rss_mb: number;
  total_cpu_percent: number;
  active_processes: number;
};

export function MonitorPage() {
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [restartingProcesses, setRestartingProcesses] = useState<string[]>([]);
  const [scalingProcesses, setScalingProcesses] = useState<string[]>([]);
  const [viewMode, setViewMode] = useState<'basic' | 'detailed'>('basic');
  const { toast } = useToast();
  
  // 获取所有监控数据
  const fetchMonitoringData = useCallback(async () => {
    try {
      if (!loading) {
        setIsRefreshing(true);
      }
      
      const statusData = await systemApi.getSystemStatus();
      setSystemStatus(statusData);
      setError(null);

    } catch (err) {
      console.error('获取监控数据失败', err);
      setError('无法获取监控数据，请稍后重试');
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  }, [loading]);
  
  // 首次加载时获取监控数据
  useEffect(() => {
    fetchMonitoringData();
    
    // 设置定时刷新
    const interval = setInterval(fetchMonitoringData, 1500); // 每3秒刷新一次
    
    return () => clearInterval(interval);
  }, [fetchMonitoringData]);
  
  // 格式化内存使用
  const formatMemory = (mb: number): string => {
    if (mb === undefined || mb === null) return 'N/A';
    
    if (mb >= 1024) {
      return `${(mb / 1024).toFixed(1)}GB`;
    }
    
    return `${Math.round(mb)}MB`;
  };
  
  // 重启进程
  const restartProcess = async (componentId: string, componentType: string) => {
    try {
      setRestartingProcesses(prev => [...prev, componentId]);
      
      // 调用系统API重启组件
      const response = await systemApi.manageComponents({
        action: 'restart',
        component: componentId
      });
      
      if (response.success) {
        toast({
          title: "重启成功",
          description: `${componentType} 进程已重启，正在恢复服务...`,
          variant: "success"
        });
        
        // 立即刷新监控数据
        await fetchMonitoringData();
      } else {
        toast({
          title: "重启失败",
          description: `无法重启 ${componentType} 进程，请稍后再试`,
          variant: "error"
        });
      }
    } catch (error) {
      console.error('重启进程失败:', error);
      toast({
        title: "重启失败",
        description: `发生错误: ${error instanceof Error ? error.message : '未知错误'}`,
        variant: "error"
      });
    } finally {
      setRestartingProcesses(prev => prev.filter(id => id !== componentId));
    }
  };
  
  // 扩缩容进程
  const scaleProcess = async (componentId: string, count: number) => {
    try {
      setScalingProcesses(prev => [...prev, componentId]);
      
      // 获取当前组件信息
      const component = systemStatus?.components[componentId];
      if (!component) {
        throw new Error('找不到组件信息');
      }
      
      const currentCount = component.active_processes;
      const actionText = count > currentCount ? "扩容" : "缩容";
      
      // 调用系统API扩缩容组件
      const response = await systemApi.scaleWorkers({
        component_type: component.type,
        target_count: count // 使用 target_count
      });
      
      if (response.success) {
        toast({
          title: `${actionText}成功`,
          description: `${component.type} 进程已${actionText}，实例数: ${currentCount} → ${count}`,
          variant: "success"
        });
        
        // 立即刷新监控数据
        await fetchMonitoringData();
      } else {
        toast({
          title: `${actionText}失败`,
          description: `无法${actionText} ${component.type} 进程，请稍后再试`,
          variant: "error"
        });
      }
    } catch (error) {
      console.error('扩缩容进程失败:', error);
      toast({
        title: "操作失败",
        description: `发生错误: ${error instanceof Error ? error.message : '未知错误'}`,
        variant: "error"
      });
    } finally {
      setScalingProcesses(prev => prev.filter(id => id !== componentId));
    }
  };
  
  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Spinner />
        <span className="ml-2">加载监控数据...</span>
      </div>
    );
  }
  
  if (error || !systemStatus) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-md">
        <p>{error || "无法加载系统状态"}</p>
        <Button 
          variant="outline" 
          className="mt-2" 
          onClick={fetchMonitoringData}
        >
          重试
        </Button>
      </div>
    );
  }

  const { components, queues } = systemStatus;
  const basicComponents: BasicComponentStatus[] = Object.entries(components).map(([id, data]) => ({
      id,
      type: data.type,
      status: data.status,
      total_memory_rss_mb: data.total_memory_rss_mb,
      total_cpu_percent: data.total_cpu_percent,
      active_processes: data.active_processes,
    }));
  
  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">流水线监控</h1>
        <div className="flex items-center gap-2">
          <div className="flex items-center rounded-md overflow-hidden border">
            <button 
              className={`px-3 py-1.5 text-sm ${viewMode === 'basic' ? 'bg-primary text-primary-foreground' : 'bg-transparent'}`}
              onClick={() => setViewMode('basic')}
            >
              基础视图
            </button>
            <button 
              className={`px-3 py-1.5 text-sm ${viewMode === 'detailed' ? 'bg-primary text-primary-foreground' : 'bg-transparent'}`}
              onClick={() => setViewMode('detailed')}
            >
              详细视图
            </button>
          </div>
          <Button 
            variant="outline" 
            onClick={fetchMonitoringData}
            disabled={isRefreshing}
          >
            {isRefreshing ? (
              <span className="flex items-center">
                <Spinner />
                <span className="ml-2">刷新中...</span>
              </span>
            ) : <><RefreshCw size={14} className="mr-2"/> 刷新数据</>}
          </Button>
        </div>
      </div>
      
      {viewMode === 'basic' ? (
        // 基础视图
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          <div className="bg-card border border-border rounded-md p-4">
            <h2 className="text-lg font-medium mb-4">队列状态</h2>
            {Object.keys(queues).length === 0 ? (
              <p className="text-muted-foreground text-center py-4">暂无队列数据</p>
            ) : (
              <div className="space-y-4">
                {Object.entries(queues).map(([queueName, metrics]) => (
                  <div key={queueName} className="space-y-2">
                    <div className="flex justify-between items-center">
                      <h3 className="font-medium capitalize overflow-hidden text-ellipsis whitespace-nowrap" title={queueName}>
                        {queueName.replace("sitesearch:task:", "任务 ").replace(":queue", "")}
                      </h3>
                      <span className="text-xs px-2 py-1 bg-muted rounded-full flex-shrink-0">
                        {metrics.processing} 处理中
                      </span>
                    </div>
                    <div className="h-2 bg-muted rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-primary rounded-full"
                        style={{ 
                          width: `${Math.min(100, 
                            (metrics.completed / 
                              Math.max(1, metrics.completed + metrics.pending + metrics.processing + metrics.failed)
                            ) * 100
                          )}%` 
                        }}
                      ></div>
                    </div>
                    <div className="flex justify-between text-xs text-muted-foreground">
                      <span>待处理: {metrics.pending}</span>
                      <span>已完成: {metrics.completed}</span>
                      <span>失败: {metrics.failed}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          
          <div className="bg-card border border-border rounded-md p-4">
            <h2 className="text-lg font-medium mb-4">组件状态</h2>
            {basicComponents.length === 0 ? (
              <p className="text-muted-foreground text-center py-4">暂无组件数据</p>
            ) : (
              <div className="space-y-3">
                {basicComponents.map((process) => (
                  <div key={process.id} className="flex items-center justify-between border-b border-border pb-2 last:border-0 last:pb-0">
                    <div>
                      <div className="flex items-center">
                        <span className={`w-2 h-2 rounded-full mr-2 ${process.status === 'running' ? 'bg-green-500' : 'bg-red-500'}`}></span>
                        <span className="font-medium capitalize">{process.type}</span>
                        {process.status !== 'running' && (
                          <span className="ml-2 text-xs text-red-500 flex items-center">
                            <AlertCircle size={12} className="mr-1" />
                            已停止
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground">活跃进程: {process.active_processes}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="text-right">
                        <p className="text-sm">内存: {formatMemory(process.total_memory_rss_mb)}</p>
                        <p className="text-xs text-muted-foreground">CPU: {process.total_cpu_percent.toFixed(1)}%</p>
                      </div>
                      {process.status !== 'running' && (
                        <Button 
                          size="sm" 
                          variant="outline" 
                          className="ml-2"
                          disabled={restartingProcesses.includes(process.id)}
                          onClick={() => restartProcess(process.id, process.type)}
                        >
                          {restartingProcesses.includes(process.id) ? (
                            <span className="flex items-center">
                              <Spinner />
                              <span className="ml-1">重启中</span>
                            </span>
                          ) : (
                            <span className="flex items-center">
                              <RefreshCw size={14} className="mr-1" />
                              重启
                            </span>
                          )}
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          <RedisStatsCard stats={systemStatus.redis_stats} />
          {systemStatus.main_process_resources && <MainProcessCard stats={systemStatus.main_process_resources} />}
        </div>
      ) : (
        // 详细视图
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-8">
          {Object.keys(components).length === 0 ? (
            <div className="col-span-full text-center p-8 border border-dashed rounded-md">
              <p className="text-muted-foreground">暂无组件数据</p>
            </div>
          ) : (
            Object.entries(components).map(([id, component]) => (
              <ComponentDetailsCard 
                key={id}
                id={id}
                component={component}
                onRestartComponent={
                  component.status !== 'running' 
                    ? (id) => restartProcess(id, component.type) 
                    : undefined
                }
                onScaleComponent={(id, count) => scaleProcess(id, count)}
                isRestarting={restartingProcesses.includes(id)}
                isScaling={scalingProcesses.includes(id)}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
} 