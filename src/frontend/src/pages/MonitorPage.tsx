import { useState, useEffect, useCallback } from 'react';
import { Button } from '../components/ui/button';
import { systemApi } from '../api';
import { AlertCircle, RefreshCw } from 'lucide-react';
import { useToast } from '../components/ui/toast';
import { ComponentDetailsCard, type ComponentDetails } from '../components/ComponentDetails';

// 简单的Spinner组件
const Spinner = () => (
  <div className="animate-spin h-5 w-5 border-2 border-current border-t-transparent rounded-full" 
       aria-label="正在加载"></div>
);

// 类型定义
type QueueMetric = {
  pending: number;
  processing: number;
  completed: number;
  failed: number;
};

type QueueMetrics = {
  [key: string]: QueueMetric;
};

type ProcessStatus = {
  id: string;
  type: string;
  status: string;
  uptime: string;
  memory: string;
  cpu: string;
};

type Log = {
  timestamp: string;
  level: string;
  message: string;
};

type ComponentData = {
  [key: string]: {
    type: string;
    total_processes: number;
    active_processes: number;
    status: string;
    config: any;
    uptime_seconds?: number;
    memory_usage_mb?: number;
    cpu_usage?: number;
    queue_metrics: {
      pending: number;
      processing: number;
      completed: number;
      failed: number;
      avg_processing_time: number;
      last_activity: string | null;
    };
  };
};

export function MonitorPage() {
  const [queueMetrics, setQueueMetrics] = useState<QueueMetrics>({});
  const [processes, setProcesses] = useState<ProcessStatus[]>([]);
  const [logs, setLogs] = useState<Log[]>([]);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [restartingProcesses, setRestartingProcesses] = useState<string[]>([]);
  const [scalingProcesses, setScalingProcesses] = useState<string[]>([]);
  const [components, setComponents] = useState<ComponentDetails[]>([]);
  const [viewMode, setViewMode] = useState<'basic' | 'detailed'>('basic');
  const { toast } = useToast();
  
  // 获取所有监控数据
  const fetchMonitoringData = useCallback(async () => {
    try {
      setIsRefreshing(true);
      
      // 获取队列指标
      const queueResponse = await systemApi.getQueueMetrics();
      
      // 格式化队列指标 - 修改这里适配新的API格式
      const formattedQueues: QueueMetrics = {};
      if (queueResponse.queues) {
        // 新API格式
        Object.entries(queueResponse.queues).forEach(([queueName, queueData]: [string, any]) => {
          formattedQueues[queueName] = {
            pending: queueData.pending || 0,
            processing: queueData.processing || 0,
            completed: queueData.completed || 0,
            failed: queueData.failed || 0
          };
        });
      } else {
        // 兼容旧格式
        Object.entries(queueResponse).forEach(([queueName, queueData]: [string, any]) => {
          if (queueName !== 'count' && queueName !== 'page' && queueName !== 'page_size') {
            formattedQueues[queueName] = {
              pending: queueData.pending || 0,
              processing: queueData.processing || 0,
              completed: queueData.completed || 0,
              failed: queueData.failed || 0
            };
          }
        });
      }
      
      setQueueMetrics(formattedQueues);
      
      // 获取组件状态（进程状态）
      const componentResponse = await systemApi.getComponentStatus();
      
      // 格式化进程状态
      // 将对象格式转换为数组格式
      const formattedProcesses: ProcessStatus[] = Object.entries(componentResponse.components)
        .map(([id, component]: [string, any]) => ({
          id,
          type: component.type,
          status: component.status,
          uptime: formatUptime(component.uptime_seconds || 0),
          memory: formatMemory(component.memory_usage_mb || 0),
          cpu: component.cpu_usage ? (component.cpu_usage * 100).toFixed(1) : '0.0'
        }));
      
      setProcesses(formattedProcesses);
      
      // 处理组件详情数据
      if (componentResponse.components) {
        const componentData: ComponentData = componentResponse.components;
        const formattedComponents: ComponentDetails[] = Object.entries(componentData).map(
          ([id, data]) => ({
            id,
            type: data.type,
            total_processes: data.total_processes,
            active_processes: data.active_processes,
            status: data.status,
            config: data.config || {},
            queue_metrics: data.queue_metrics || {
              pending: 0,
              processing: 0,
              completed: 0,
              failed: 0,
              avg_processing_time: 0,
              last_activity: null
            },
            // 添加现有进程信息
            uptime: formatUptime(data.uptime_seconds || 0),
            memory: formatMemory(data.memory_usage_mb || 0),
            cpu: data.cpu_usage ? (data.cpu_usage * 100).toFixed(1) : '0.0'
          })
        );
        
        setComponents(formattedComponents);
      }
      
      // 获取系统日志
      const logsResponse = await systemApi.getSystemStatus();
      
      // 格式化日志
      if (logsResponse.logs && Array.isArray(logsResponse.logs)) {
        const formattedLogs: Log[] = logsResponse.logs.map((log: any) => ({
          timestamp: new Date(log.timestamp).toLocaleString(),
          level: log.level,
          message: log.message
        }));
        
        setLogs(formattedLogs);
      }
      
      // 清除可能存在的错误
      setError(null);
    } catch (err) {
      console.error('获取监控数据失败', err);
      setError('无法获取监控数据，请稍后重试');
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  }, []);
  
  // 首次加载时获取监控数据
  useEffect(() => {
    fetchMonitoringData();
    
    // 设置定时刷新
    const interval = setInterval(() => {
      fetchMonitoringData();
    }, 2000); // 每2秒刷新一次
    
    return () => clearInterval(interval);
  }, [fetchMonitoringData]);
  
  // 格式化运行时间
  const formatUptime = (seconds: number): string => {
    if (!seconds) return '未知';
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    
    return `${hours}h ${minutes}m`;
  };
  
  // 格式化内存使用
  const formatMemory = (mb: number): string => {
    if (!mb) return '未知';
    
    if (mb >= 1024) {
      return `${(mb / 1024).toFixed(1)}GB`;
    }
    
    return `${Math.round(mb)}MB`;
  };
  
  // 手动刷新数据
  const refreshData = () => {
    fetchMonitoringData();
  };
  
  // 重启进程
  const restartProcess = async (processId: string, processType: string) => {
    try {
      setRestartingProcesses(prev => [...prev, processId]);
      
      // 调用系统API重启组件
      const response = await systemApi.manageComponents({
        action: 'restart',
        component: processId
      });
      
      if (response.success) {
        toast({
          title: "重启成功",
          description: `${processType} 进程已重启，正在恢复服务...`,
          variant: "success"
        });
        
        // 立即刷新监控数据
        await fetchMonitoringData();
      } else {
        toast({
          title: "重启失败",
          description: `无法重启 ${processType} 进程，请稍后再试`,
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
      setRestartingProcesses(prev => prev.filter(id => id !== processId));
    }
  };
  
  // 扩缩容进程
  const scaleProcess = async (processId: string, count: number) => {
    try {
      setScalingProcesses(prev => [...prev, processId]);
      
      // 获取当前组件信息
      const component = components.find(c => c.id === processId);
      if (!component) {
        throw new Error('找不到组件信息');
      }
      
      // 计算变化数量
      const currentCount = component.total_processes;
      
      // 调用系统API扩缩容组件
      const response = await systemApi.scaleWorkers({
        component_type: component.type,
        worker_count: count // 总实例数
      });
      
      if (response.success) {
        toast({
          title: count > currentCount ? "扩容成功" : "缩容成功",
          description: `${component.type} 进程已${count > currentCount ? '扩容' : '缩容'}，实例数: ${currentCount} → ${count}`,
          variant: "success"
        });
        
        // 立即刷新监控数据
        await fetchMonitoringData();
      } else {
        toast({
          title: count > currentCount ? "扩容失败" : "缩容失败",
          description: `无法${count > currentCount ? '扩容' : '缩容'} ${component.type} 进程，请稍后再试`,
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
      setScalingProcesses(prev => prev.filter(id => id !== processId));
    }
  };
  
  // 获取日志级别对应的颜色类
  const getLogLevelClass = (level: string): string => {
    switch (level.toLowerCase()) {
      case 'info':
        return 'text-green-500';
      case 'warning':
        return 'text-yellow-500';
      case 'error':
        return 'text-red-500';
      case 'debug':
        return 'text-blue-500';
      default:
        return 'text-muted-foreground';
    }
  };
  
  if (loading && !isRefreshing) {
    return (
      <div className="flex justify-center items-center h-64">
        <Spinner />
        <span className="ml-2">加载监控数据...</span>
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
          onClick={refreshData}
        >
          重试
        </Button>
      </div>
    );
  }
  
  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">爬取监控</h1>
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
            onClick={refreshData}
            disabled={isRefreshing}
          >
            {isRefreshing ? (
              <span className="flex items-center">
                <Spinner />
                <span className="ml-2">刷新中...</span>
              </span>
            ) : '刷新数据'}
          </Button>
        </div>
      </div>
      
      {viewMode === 'basic' ? (
        // 基础视图
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          <div className="bg-card border border-border rounded-md p-4">
            <h2 className="text-lg font-medium mb-4">队列状态</h2>
            {Object.keys(queueMetrics).length === 0 ? (
              <p className="text-muted-foreground text-center py-4">暂无队列数据</p>
            ) : (
              <div className="space-y-4">
                {Object.entries(queueMetrics).map(([queueName, metrics]) => (
                  <div key={queueName} className="space-y-2">
                    <div className="flex justify-between items-center">
                      <h3 className="font-medium capitalize">{queueName} 队列</h3>
                      <span className="text-xs px-2 py-1 bg-muted rounded-full">
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
            <h2 className="text-lg font-medium mb-4">进程状态</h2>
            {processes.length === 0 ? (
              <p className="text-muted-foreground text-center py-4">暂无进程数据</p>
            ) : (
              <div className="space-y-3">
                {processes.map((process) => (
                  <div key={process.id} className="flex items-center justify-between border-b border-border pb-2 last:border-0 last:pb-0">
                    <div>
                      <div className="flex items-center">
                        <span className={`w-2 h-2 rounded-full mr-2 ${process.status === 'running' ? 'bg-green-500' : 'bg-red-500'}`}></span>
                        <span className="font-medium capitalize">{process.type} {process.id.split('-')[1] || ''}</span>
                        {process.status !== 'running' && (
                          <span className="ml-2 text-xs text-red-500 flex items-center">
                            <AlertCircle size={12} className="mr-1" />
                            已停止
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground">运行时间: {process.uptime}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="text-right">
                        <p className="text-sm">内存: {process.memory}</p>
                        <p className="text-xs text-muted-foreground">CPU: {process.cpu}%</p>
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
        </div>
      ) : (
        // 详细视图
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-8">
          {components.length === 0 ? (
            <div className="col-span-2 text-center p-8 border border-dashed rounded-md">
              <p className="text-muted-foreground">暂无组件数据</p>
            </div>
          ) : (
            components.map(component => (
              <ComponentDetailsCard 
                key={component.id}
                component={component}
                onRestartComponent={
                  component.status !== 'running' 
                    ? (id) => restartProcess(id, component.type) 
                    : undefined
                }
                onScaleComponent={(id, count) => scaleProcess(id, count)}
                isRestarting={restartingProcesses.includes(component.id)}
                isScaling={scalingProcesses.includes(component.id)}
              />
            ))
          )}
        </div>
      )}
      
      <div className="bg-card border border-border rounded-md p-4">
        <h2 className="text-lg font-medium mb-4">爬取日志</h2>
        <div className="bg-muted p-3 rounded-md font-mono text-xs h-60 overflow-y-auto">
          {logs.length === 0 ? (
            <p className="text-muted-foreground text-center py-4">暂无日志数据</p>
          ) : (
            logs.map((log, index) => (
              <p key={index} className={getLogLevelClass(log.level)}>
                [{log.timestamp}] {log.level.toUpperCase()}: {log.message}
              </p>
            ))
          )}
        </div>
      </div>
    </div>
  );
} 