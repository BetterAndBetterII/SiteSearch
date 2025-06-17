import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { MainProcessResources } from '../api/types';
import { Server, Cpu, MemoryStick, AlertCircle } from 'lucide-react';

interface MainProcessCardProps {
  stats: MainProcessResources;
}

const formatMemory = (mb: number): string => {
    if (mb === undefined || mb === null) return 'N/A';
    
    if (mb >= 1024) {
      return `${(mb / 1024).toFixed(1)}GB`;
    }
    
    return `${Math.round(mb)}MB`;
};

export function MainProcessCard({ stats }: MainProcessCardProps) {
  if (stats.error) {
    return (
        <Card className="bg-destructive/10 border-destructive/30">
        <CardHeader>
          <CardTitle className="text-lg flex items-center">
            <Server size={18} className="mr-2" />
            主进程状态
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-destructive flex items-center">
            <AlertCircle size={16} className="mr-2" />
            <p>{stats.error}</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center">
            <Server size={18} className="mr-2" />
            主进程状态
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
            <div className="flex justify-between items-center text-sm">
                <span className="text-muted-foreground flex items-center"><Cpu size={14} className="mr-2" /> CPU 使用率</span>
                <span className="font-medium">{stats.cpu_percent.toFixed(2)}%</span>
            </div>
            <div className="flex justify-between items-center text-sm">
                <span className="text-muted-foreground flex items-center"><MemoryStick size={14} className="mr-2" /> 内存使用</span>
                <span className="font-medium">{formatMemory(stats.memory_rss_mb)}</span>
            </div>
            <div className="flex justify-between items-center text-sm">
                <span className="text-muted-foreground">进程名称</span>
                <span className="font-medium">{stats.name}</span>
            </div>
            <div className="flex justify-between items-center text-sm">
                <span className="text-muted-foreground">PID</span>
                <span className="font-medium">{stats.pid}</span>
            </div>
        </div>
      </CardContent>
    </Card>
  );
} 