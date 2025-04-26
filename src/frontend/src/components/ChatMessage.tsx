import { ChatMessageInterface, Reference } from '../types/search';

type ChatMessageProps = {
  message: ChatMessageInterface;
  isSearching?: string[] | null;
  isInvestigating?: string[] | null;
  isStreaming?: boolean;
  onReferenceClicked?: (reference: Reference) => void;
};

export function ChatMessage({
  message,
  isSearching,
  isInvestigating,
  isStreaming,
  onReferenceClicked
}: ChatMessageProps) {
  const isAssistant = message.role === 'assistant';
  const text = message.content[0]?.text || '';
  const references = message.metadata.references || [];

  return (
    <div className={`my-4 ${isAssistant ? 'ml-4' : 'mr-4'}`}>
      <div className="flex gap-2">
        <div className={`p-4 rounded-lg max-w-[80%] text-gray-900 ${
          isAssistant 
            ? 'bg-gray-900/80 text-primary-foreground rounded-tl-none' 
            : 'bg-muted ml-auto rounded-tr-none'
        }`}>
          {text}
          
          {isStreaming && <span className="animate-pulse">▍</span>}
          
          {isSearching && (
            <div className="mt-2 text-sm opacity-70">
              <span>正在搜索: {isSearching.join(', ')}</span>
            </div>
          )}
          
          {isInvestigating && (
            <div className="mt-2 text-sm opacity-70">
              <span>正在查看参考资料...</span>
            </div>
          )}
          
          {references.length > 0 && (
            <div className="mt-4 border-t pt-2">
              <h4 className="font-medium mb-2">参考资料:</h4>
              <ul className="space-y-1">
                {references.map((ref, index) => (
                  <li key={index}>
                    <button
                      className="text-primary hover:underline text-left"
                      onClick={() => onReferenceClicked?.(ref)}
                    >
                      {ref.title || ref.url}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
      <div className="text-xs text-muted-foreground mt-1 ml-2">
        {message.metadata.timestamp}
      </div>
    </div>
  );
} 