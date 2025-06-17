import { useState, useEffect } from 'react';
import { 
  Card, 
  CardContent,
  CardDescription, 
  CardHeader, 
  CardTitle 
} from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { ChevronDown, ChevronUp, Clock, MinusCircle, PlusCircle, RefreshCw, Settings, Users, Server, Cpu, MemoryStick, Info } from 'lucide-react';
import { ComponentStatus } from '../api/types';

interface ComponentDetailsCardProps {
  component: ComponentStatus;
  id: string;
  onRestartComponent?: (componentId: string) => Promise<void>;
  onScaleComponent?: (componentId: string, count: number) => Promise<void>;
  isRestarting?: boolean;
  isScaling?: boolean;
}

export function ComponentDetailsCard({ 
  component, 
  id,
  onRestartComponent,
  onScaleComponent,
  isRestarting = false,
  isScaling = false
}: ComponentDetailsCardProps) {
  const [showConfig, setShowConfig] = useState(false);
  const [showMetrics, setShowMetrics] = useState(false);
  const [showWorkers, setShowWorkers] = useState(false);
  const [scaleCount, setScaleCount] = useState<number>(component.active_processes);
  
  useEffect(() => {
    setScaleCount(component.active_processes);
  }, [component.active_processes]);

  console.log(component);

  // 格式化时间
  const formatDate = (dateString: string | null) => {
    if (!dateString) return '无数据';
    
    try {
      const date = new Date(dateString);
      return date.toLocaleString('zh-CN');
    } catch (e) {
      return '无效日期';
    }
  };

  // 格式化处理时间
  const formatProcessingTime = (time: number) => {
    if (time < 0.001) {
      return `${(time * 1000000).toFixed(2)}µs`;
    } else if (time < 1) {
      return `${(time * 1000).toFixed(2)}ms`;
    } else if (time < 60) {
      return `${time.toFixed(2)}秒`;
    } else {
      const minutes = Math.floor(time / 60);
      const seconds = time % 60;
      return `${minutes}分${seconds.toFixed(0)}秒`;
    }
  };
  
  // 计算处理百分比
  const calculateProgressPercentage = () => {
    const { pending, processing, completed, failed } = component.queue_metrics;
    const total = pending + processing + completed + failed;
    if (total === 0) return 0;
    return (completed / total) * 100;
  };

  // 处理扩缩容
  const handleScaleChange = (increment: boolean) => {
    let newCount = increment ? scaleCount + 1 : scaleCount - 1;
    // 防止小于0
    newCount = Math.max(0, newCount);
    setScaleCount(newCount);
  };
  
  // 应用扩缩容
  const applyScale = async () => {
    if (onScaleComponent && scaleCount !== component.active_processes) {
      await onScaleComponent(id, scaleCount);
    }
  };

  return (
    <Card className="w-full">
      <CardHeader className="pb-2">
        <div className="flex justify-between items-start">
          <div>
            <div className="flex items-center">
              <span className={`w-2 h-2 rounded-full mr-2 ${component.status === 'running' ? 'bg-green-500' : 'bg-red-500'}`}></span>
              <CardTitle className="text-lg capitalize">{component.type}</CardTitle>
              <Badge variant={component.status === 'running' ? "success" : "destructive"} className="ml-2">
                {component.status === 'running' ? '运行中' : '已停止'}
              </Badge>
            </div>
            <CardDescription className="mt-1">
              进程: {component.active_processes} 活跃
            </CardDescription>
          </div>
          
          <div className="flex items-center gap-2">
            {component.status !== 'running' && onRestartComponent && (
              <Button 
                size="sm" 
                variant="outline"
                disabled={isRestarting}
                onClick={() => onRestartComponent(id)}
              >
                {isRestarting ? (
                  <span className="flex items-center">
                    <div className="animate-spin h-4 w-4 border-2 border-current border-t-transparent rounded-full mr-1"></div>
                    重启中
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
      </CardHeader>
      
      <CardContent>
        {/* 进度条 */}
        <div className="mb-4">
          <div className="flex justify-between text-xs text-muted-foreground mb-1">
            <span>队列进度</span>
            <span>{calculateProgressPercentage().toFixed(1)}%</span>
          </div>
          <div className="h-2 bg-muted rounded-full overflow-hidden">
            <div 
              className="h-full bg-primary rounded-full transition-all duration-300"
              style={{ width: `${Math.min(100, calculateProgressPercentage())}%` }}
            ></div>
          </div>
        </div>
        
        {/* 总资源使用 */}
        <div className="flex justify-around text-center mb-4 p-3 border rounded-md bg-muted/30">
            <div>
              <p className="text-muted-foreground text-xs flex items-center justify-center"><MemoryStick size={12} className="mr-1" />总内存</p>
              <p className="font-bold text-lg">{component.total_memory_rss_mb.toFixed(2)} <span className="text-sm font-normal">MB</span></p>
            </div>
            <div>
              <p className="text-muted-foreground text-xs flex items-center justify-center"><Cpu size={12} className="mr-1" />总CPU</p>
              <p className="font-bold text-lg">{component.total_cpu_percent.toFixed(2)} <span className="text-sm font-normal">%</span></p>
            </div>
        </div>
        
        {/* 扩缩容控制 */}
        {onScaleComponent && (
          <div className="mb-4 p-3 border border-border rounded-md">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center text-sm font-medium">
                <Users size={16} className="mr-1.5" />
                <span>实例数量</span>
              </div>
              <Badge variant="secondary">
                当前: {component.active_processes}
              </Badge>
            </div>
            
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center">
                <Button 
                  size="sm" 
                  variant="outline" 
                  className="rounded-full p-0 w-8 h-8 flex items-center justify-center"
                  onClick={() => handleScaleChange(false)}
                  disabled={scaleCount <= 0 || isScaling}
                >
                  <MinusCircle size={16} />
                </Button>
                
                <div className="w-12 text-center font-semibold mx-2">
                  {scaleCount}
                </div>
                
                <Button 
                  size="sm" 
                  variant="outline" 
                  className="rounded-full p-0 w-8 h-8 flex items-center justify-center"
                  onClick={() => handleScaleChange(true)}
                  disabled={isScaling}
                >
                  <PlusCircle size={16} />
                </Button>
              </div>
              
              <Button 
                size="sm" 
                variant="default" 
                className="ml-auto"
                disabled={isScaling || scaleCount === component.active_processes}
                onClick={applyScale}
              >
                {isScaling ? (
                  <span className="flex items-center">
                    <div className="animate-spin h-4 w-4 border-2 border-current border-t-transparent rounded-full mr-1"></div>
                    处理中
                  </span>
                ) : scaleCount > component.active_processes ? (
                  <span>扩容 (+{scaleCount - component.active_processes})</span>
                ) : scaleCount < component.active_processes ? (
                  <span>缩容 (-{component.active_processes - scaleCount})</span>
                ) : (
                  <span>应用变更</span>
                )}
              </Button>
            </div>
          </div>
        )}
        
        {/* 工作进程列表 */}
        <div className="mb-3">
          <Button 
            variant="ghost" 
            size="sm" 
            className="w-full flex justify-between items-center p-2 h-auto mb-2"
            onClick={() => setShowWorkers(!showWorkers)}
          >
            <span className="font-medium flex items-center">
              <Server size={14} className="mr-1" />
              工作进程 ({component.workers ? component.workers.length : 0})
            </span>
            {showWorkers ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </Button>
          
          {showWorkers && (
            <div className="bg-muted/50 rounded-md p-3 text-sm space-y-2">
              {component.workers && component.workers.length > 0 ? (
                component.workers.map(worker => (
                  <div key={worker.pid} className="p-2 border-b last:border-b-0">
                    <div className="flex justify-between items-center font-semibold">
                      <span>{worker.name} (PID: {worker.pid})</span>
                    </div>
                    <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs mt-1">
                      <div className="flex items-center">
                        <MemoryStick size={12} className="mr-1 text-muted-foreground" />
                        <span>内存: {worker.memory_rss_mb.toFixed(2)} MB</span>
                      </div>
                      <div className="flex items-center">
                        <Cpu size={12} className="mr-1 text-muted-foreground" />
                        <span>CPU: {worker.cpu_percent.toFixed(2)} %</span>
                      </div>
                      <div className="flex items-center col-span-2">
                        <Clock size={12} className="mr-1 text-muted-foreground" />
                        <span>启动于: {formatDate(worker.create_time)}</span>
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center text-muted-foreground p-2">
                   <Info size={14} className="inline-block mr-1" />
                   没有活动的进程
                </div>
              )}
            </div>
          )}
        </div>

        {/* 队列指标 */}
        <div className="mb-3">
          <Button 
            variant="ghost" 
            size="sm" 
            className="w-full flex justify-between items-center p-2 h-auto mb-2"
            onClick={() => setShowMetrics(!showMetrics)}
          >
            <span className="font-medium">队列指标</span>
            {showMetrics ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </Button>
          
          {showMetrics && (
            <div className="bg-muted/50 rounded-md p-3 text-sm space-y-2">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <p className="text-muted-foreground text-xs">待处理</p>
                  <p className="font-medium">{component.queue_metrics.pending}</p>
                </div>
                <div>
                  <p className="text-muted-foreground text-xs">处理中</p>
                  <p className="font-medium">{component.queue_metrics.processing}</p>
                </div>
                <div>
                  <p className="text-muted-foreground text-xs">已完成</p>
                  <p className="font-medium">{component.queue_metrics.completed}</p>
                </div>
                <div>
                  <p className="text-muted-foreground text-xs">失败</p>
                  <p className="font-medium">{component.queue_metrics.failed}</p>
                </div>
              </div>
              
              <div className="pt-1 border-t border-border">
                <div className="mb-1">
                  <p className="text-muted-foreground text-xs">平均处理时间</p>
                  <p className="font-medium">{formatProcessingTime(component.queue_metrics.avg_processing_time)}</p>
                </div>
                <div>
                  <p className="text-muted-foreground text-xs">最后活动时间</p>
                  <p className="font-medium">{formatDate(component.queue_metrics.last_activity)}</p>
                </div>
              </div>
            </div>
          )}
        </div>
        
        {/* 配置信息 */}
        <div>
          <Button 
            variant="ghost" 
            size="sm" 
            className="w-full flex justify-between items-center p-2 h-auto mb-2"
            onClick={() => setShowConfig(!showConfig)}
          >
            <span className="font-medium flex items-center">
              <Settings size={14} className="mr-1" />
              配置信息
            </span>
            {showConfig ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </Button>
          
          {showConfig && (
            <div className="bg-muted/50 rounded-md p-3 text-sm space-y-2">
              <div className="grid grid-cols-2 gap-2">
                {component.config.batch_size !== undefined && (
                  <div>
                    <p className="text-muted-foreground text-xs">批处理大小</p>
                    <p className="font-medium">{component.config.batch_size}</p>
                  </div>
                )}
                
                {component.config.sleep_time !== undefined && (
                  <div>
                    <p className="text-muted-foreground text-xs">休眠时间</p>
                    <p className="font-medium">{component.config.sleep_time}秒</p>
                  </div>
                )}
              </div>
              
              {/* 其他配置项 */}
              {Object.entries(component.config).map(([key, value]) => {
                // 跳过已经显示的通用配置
                if (key === 'batch_size' || key === 'sleep_time') return null;
                
                // 对象类型的配置
                if (typeof value === 'object' && value !== null) {
                  return (
                    <div key={key} className="pt-1 border-t border-border">
                      <p className="text-muted-foreground text-xs capitalize">{key.replace(/_/g, ' ')}</p>
                      <pre className="text-xs bg-muted p-2 rounded-sm mt-1 overflow-x-auto">
                        {JSON.stringify(value, null, 2) || '{}'}
                      </pre>
                    </div>
                  );
                }
                
                // 简单类型的配置
                return (
                  <div key={key} className="pt-1 border-t border-border">
                    <p className="text-muted-foreground text-xs capitalize">{key.replace(/_/g, ' ')}</p>
                    <p className="font-medium">{value?.toString() || '未设置'}</p>
                  </div>
                );
              })}
            </div>
          )}
        </div>
        
      </CardContent>
    </Card>
  );
} 