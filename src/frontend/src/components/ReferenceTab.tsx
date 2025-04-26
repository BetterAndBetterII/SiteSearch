import { Reference } from '../types/search';
import { Button } from './ui/button';
import { X } from 'lucide-react';

interface ReferenceTabProps {
  reference: Reference;
  onClose: () => void;
}

export function ReferenceTab({ reference, onClose }: ReferenceTabProps) {
  return (
    <div className="fixed top-0 right-0 w-96 h-full bg-background border-l border-border shadow-lg p-4 overflow-y-auto">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold">参考资料</h3>
        <Button variant="ghost" size="icon" onClick={onClose}>
          <X className="h-5 w-5" />
        </Button>
      </div>
      
      <div className="space-y-4">
        <h4 className="font-medium">{reference.title}</h4>
        
        <div className="text-sm">
          <a 
            href={reference.url} 
            target="_blank" 
            rel="noopener noreferrer"
            className="text-primary hover:underline"
          >
            查看原文
          </a>
        </div>
        
        <div className="mt-4 border-t pt-4">
          <div className="prose prose-sm max-w-none">
            {reference.content}
          </div>
        </div>
      </div>
    </div>
  );
} 